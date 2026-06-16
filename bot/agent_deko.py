"""
agent_deko.py — Tracker de positions Polymarket

Surveille les nouvelles positions ouvertes par sailor82 et onlylucknobrain.
Pour chaque nouvelle position détectée :
  - Récupère la prévision météo Open-Meteo pour la ville/date concernée
  - Calcule l'écart entre la prévision et la fourchette tradée
  - Génère une explication automatique du "pourquoi"

Table Supabase : positions_tracker
"""

import os, re, json, time, datetime, requests
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
UTC   = ZoneInfo("UTC")

TRADERS = {
    "sailor82":        "0xbbb72a812cfbc5217d77c0a0018c71f174d3a11a",
    "onlylucknobrain": "0x6a8d1709bfb718d8555d315a983c4816278350f9",
}

DATA_API    = "https://data-api.polymarket.com"
METEO_API   = "https://api.open-meteo.com/v1/forecast"
INTERVAL    = 10   # minutes entre chaque cycle
TIMEOUT     = 12

SB_URL = os.getenv("SUPABASE_URL", "https://obqkqhlqlowxrxbyvktl.supabase.co")
SB_KEY = os.getenv("SUPABASE_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Coordonnées des villes
CITY_COORDS = {
    "new york city":  (40.7128, -74.0060),
    "new york":       (40.7128, -74.0060),
    "san francisco":  (37.7749, -122.4194),
    "los angeles":    (34.0522, -118.2437),
    "seattle":        (47.6062, -122.3321),
    "houston":        (29.7604, -95.3698),
    "austin":         (30.2672, -97.7431),
    "atlanta":        (33.7490, -84.3880),
    "miami":          (25.7617, -80.1918),
    "dallas":         (32.7767, -96.7970),
    "chicago":        (41.8781, -87.6298),
    "denver":         (39.7392, -104.9903),
    "boston":         (42.3601, -71.0589),
    "phoenix":        (33.4484, -112.0740),
    "las vegas":      (36.1699, -115.1398),
    "minneapolis":    (44.9778, -93.2650),
}

# ── Logging ────────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[DEKO][{datetime.datetime.now(PARIS).strftime('%d/%m %H:%M')}] {msg}", flush=True)

# ── Supabase ───────────────────────────────────────────────────────────────────

def _sb(method: str, table: str, **kwargs):
    url = f"{SB_URL}/rest/v1/{table}"
    headers = {
        "apikey":        SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }
    r = requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
    if r.status_code in (200, 201):
        try: return r.json()
        except: return []
    return []

def sb_get(table: str, params: dict = None) -> list:
    return _sb("GET", table, params=params) or []

def sb_upsert(table: str, data):
    _sb("POST", table, json=data)

# ── Polymarket API ─────────────────────────────────────────────────────────────

def fetch_positions(address: str) -> list:
    try:
        r = requests.get(f"{DATA_API}/positions",
            params={"user": address, "sizeThreshold": "0.01", "limit": "200"},
            timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else []
    except Exception as e:
        log(f"⚠️  fetch_positions {address[:10]}: {e}")
    return []

# ── Parsing ────────────────────────────────────────────────────────────────────

def parse_city(title: str) -> str:
    m = re.search(r'temperature in ([\w\s]+?)(?:\s+be|\s+on)', title, re.I)
    if m:
        return m.group(1).strip().lower()
    return ""

def parse_range(title: str) -> tuple | None:
    m = re.search(r'between\s+(\d+(?:\.\d+)?)[–\-](\d+(?:\.\d+)?)', title, re.I)
    if not m:
        m = re.search(r'between\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)', title, re.I)
    return (float(m.group(1)), float(m.group(2))) if m else None

def parse_date(title: str) -> str:
    # "on June 16?" ou "on June 16, 2026?"
    m = re.search(r'on\s+(\w+ \d+(?:,\s*\d{4})?)', title, re.I)
    if m:
        raw = m.group(1).strip().rstrip('?')
        # Ajouter l'année si absente
        if not re.search(r'\d{4}', raw):
            raw += f", {datetime.datetime.now().year}"
        try:
            dt = datetime.datetime.strptime(raw, "%B %d, %Y")
            return dt.strftime("%Y-%m-%d")
        except:
            pass
    return datetime.datetime.now().strftime("%Y-%m-%d")

# ── Météo Open-Meteo ───────────────────────────────────────────────────────────

def fetch_forecast(city: str, date_str: str) -> float | None:
    coords = CITY_COORDS.get(city.lower())
    if not coords:
        return None
    try:
        r = requests.get(METEO_API, params={
            "latitude":         coords[0],
            "longitude":        coords[1],
            "daily":            "temperature_2m_max",
            "temperature_unit": "fahrenheit",
            "timezone":         "America/New_York",
            "start_date":       date_str,
            "end_date":         date_str,
        }, timeout=TIMEOUT)
        if r.status_code == 200:
            temps = r.json().get("daily", {}).get("temperature_2m_max", [])
            return round(temps[0], 1) if temps else None
    except Exception as e:
        log(f"⚠️  météo {city}: {e}")
    return None

# ── Analyse automatique ────────────────────────────────────────────────────────

def explain_position(trader: str, outcome: str, city: str, range_low: float,
                     range_high: float, price: float, amount: float,
                     forecast: float | None) -> str:
    """Génère une explication courte du 'pourquoi' de cette position."""
    if not ANTHROPIC_KEY:
        return _explain_local(outcome, city, range_low, range_high, price, forecast)

    range_center = (range_low + range_high) / 2
    gap = round(forecast - range_center, 1) if forecast else None

    context = f"""Trader Polymarket : {trader}
Position : {outcome} sur "{city.title()}" entre {range_low}-{range_high}°F
Prix d'entrée : {price:.0%} ({price:.2f}¢)
Mise : ${amount:.0f}
Prévision Open-Meteo : {f'{forecast}°F' if forecast else 'inconnue'}
Écart prévision/fourchette : {f'{gap:+.1f}°F' if gap else 'N/A'}"""

    prompt = f"""{context}

En 2-3 phrases max, explique POURQUOI ce trader a pris cette position.
Sois direct et factuel. Exemples :
- "NO à 93¢ : la prévision est 73°F, soit 8°F sous la fourchette. Fourchette très improbable, marge solide."
- "YES à 36¢ : la prévision pointe exactement sur 76-77°F. Pari spéculatif mais ciblé sur la bonne fourchette."
Réponds en français."""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 150,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()["content"][0]["text"].strip()
    except Exception as e:
        log(f"⚠️  Claude analyse: {e}")

    return _explain_local(outcome, city, range_low, range_high, price, forecast)

def _explain_local(outcome: str, city: str, range_low: float, range_high: float,
                   price: float, forecast: float | None) -> str:
    """Analyse sans LLM si API indisponible."""
    if forecast is None:
        return f"{outcome} à {price:.0%} — prévision météo indisponible."
    center = (range_low + range_high) / 2
    gap = forecast - center
    if outcome.lower() == "no":
        if abs(gap) >= 5:
            return (f"NO à {price:.0%} : prévision {forecast}°F, soit {abs(gap):.0f}°F "
                    f"{'sous' if gap < 0 else 'au-dessus de'} la fourchette {range_low}-{range_high}°F. "
                    f"Fourchette très improbable — marge confortable.")
        else:
            return (f"NO à {price:.0%} : prévision {forecast}°F proche de la fourchette "
                    f"{range_low}-{range_high}°F (écart {abs(gap):.0f}°F). Pari risqué.")
    else:
        if abs(gap) <= 2:
            return (f"YES à {price:.0%} : prévision {forecast}°F tombe dans/près de "
                    f"{range_low}-{range_high}°F. Pari ciblé sur la bonne fourchette.")
        else:
            return (f"YES à {price:.0%} : prévision {forecast}°F, fourchette "
                    f"{range_low}-{range_high}°F (écart {abs(gap):.0f}°F). Pari spéculatif.")

# ── Détection nouvelles positions ──────────────────────────────────────────────

def known_positions(trader: str) -> set:
    rows = sb_get("positions_tracker", params={
        "trader": f"eq.{trader}",
        "select": "condition_id",
        "limit":  "1000",
    })
    return {r["condition_id"] for r in rows if r.get("condition_id")}

def detect_new_positions(trader: str, address: str) -> int:
    positions = fetch_positions(address)
    if not positions:
        log(f"  {trader}: aucune position récupérée")
        return 0

    known = known_positions(trader)
    new_count = 0

    # Ne garder que les positions OUVERTES (currentValue > 0)
    open_positions = [p for p in positions if float(p.get("currentValue") or 0) > 0.01]

    for p in open_positions:
        cid = p.get("conditionId", "")
        if not cid or cid in known:
            continue

        title    = p.get("title", "")
        outcome  = p.get("outcome", "")
        price    = float(p.get("avgPrice") or 0)
        amount   = float(p.get("initialValue") or 0)
        city     = parse_city(title)
        bounds   = parse_range(title)
        date_str = parse_date(title)

        range_low  = bounds[0] if bounds else None
        range_high = bounds[1] if bounds else None

        # Prévision météo
        forecast = None
        if city and bounds:
            forecast = fetch_forecast(city, date_str)

        # Gap prévision / fourchette
        gap = None
        if forecast and bounds:
            center = (bounds[0] + bounds[1]) / 2
            gap = round(forecast - center, 1)

        # Analyse automatique
        analysis = ""
        if city and bounds:
            analysis = explain_position(trader, outcome, city, range_low, range_high,
                                        price, amount, forecast)

        # Certitude
        if outcome.lower() == "no":
            certainty = "high" if price >= 0.85 else "medium" if price >= 0.75 else "low"
        else:
            certainty = "speculative" if price <= 0.45 else "standard"

        row = {
            "trader":       trader,
            "condition_id": cid,
            "title":        title[:300],
            "city":         city,
            "range_low":    range_low,
            "range_high":   range_high,
            "market_date":  date_str,
            "outcome":      outcome,
            "price":        price,
            "amount_usdc":  amount,
            "forecast_temp": forecast,
            "gap":          gap,
            "analysis":     analysis,
            "certainty":    certainty,
            "detected_at":  datetime.datetime.now(UTC).isoformat(),
        }
        sb_upsert("positions_tracker", row)
        new_count += 1

        gap_str = f" | gap={gap:+.1f}°F" if gap is not None else ""
        log(f"  🆕 [{trader}] {outcome} {city} {range_low}-{range_high}°F "
            f"@ {price:.0%} | ${amount:.0f}{gap_str} | {certainty}")
        if analysis:
            log(f"     💬 {analysis[:120]}")

    return new_count

# ── Boucle principale ──────────────────────────────────────────────────────────

def run_cycle(cycle: int):
    log(f"─── Cycle #{cycle} ───")
    total = 0
    for trader, address in TRADERS.items():
        n = detect_new_positions(trader, address)
        total += n
    log(f"  Total nouvelles positions : {total}")

if __name__ == "__main__":
    log("🔍 Tracker de positions démarré")
    for t, a in TRADERS.items():
        log(f"   → {t} ({a[:12]}…)")
    log(f"   Cycle : toutes les {INTERVAL} min")

    cycle = 0
    while True:
        try:
            run_cycle(cycle)
        except KeyboardInterrupt:
            log("Arrêté")
            break
        except Exception as e:
            import traceback
            log(f"Erreur : {e}\n{traceback.format_exc()}")
        cycle += 1
        log(f"Prochain cycle dans {INTERVAL} min…")
        time.sleep(INTERVAL * 60)
