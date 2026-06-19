"""
agent_deko.py — Tracker de positions Polymarket (sailor82 + onlylucknobrain)

Cycle toutes les 10 min :
  - Détecte les nouvelles positions ouvertes
  - Récupère la prévision météo Open-Meteo
  - Génère une explication "pourquoi" via Claude Haiku
  - Stocke dans Supabase : positions_tracker

Toutes les 6h : génère un rapport de stratégie complet par trader → tracker_rapports
"""

import os, re, json, time, datetime, requests
from collections import defaultdict
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
UTC   = ZoneInfo("UTC")

TRADERS = {
    "sailor82":        "0xbbb72a812cfbc5217d77c0a0018c71f174d3a11a",
    "onlylucknobrain": "0x6a8d1709bfb718d8555d315a983c4816278350f9",
}

DATA_API  = "https://data-api.polymarket.com"
METEO_API = "https://api.open-meteo.com/v1/forecast"
INTERVAL  = 10        # minutes entre cycles
REPORT_EVERY = 36     # cycles avant rapport (36 × 10min = 6h)
TIMEOUT   = 12

SB_URL        = os.getenv("SUPABASE_URL", "https://obqkqhlqlowxrxbyvktl.supabase.co")
SB_KEY        = os.getenv("SUPABASE_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MISTRAL_KEY   = os.getenv("MISTRAL_API_KEY", "")

CITY_COORDS = {
    "new york city":  (40.7128,  -74.0060),
    "new york":       (40.7128,  -74.0060),
    "san francisco":  (37.7749, -122.4194),
    "los angeles":    (34.0522, -118.2437),
    "seattle":        (47.6062, -122.3321),
    "houston":        (29.7604,  -95.3698),
    "austin":         (30.2672,  -97.7431),
    "atlanta":        (33.7490,  -84.3880),
    "miami":          (25.7617,  -80.1918),
    "dallas":         (32.7767,  -96.7970),
    "chicago":        (41.8781,  -87.6298),
    "denver":         (39.7392, -104.9903),
    "boston":         (42.3601,  -71.0589),
    "phoenix":        (33.4484, -112.0740),
    "las vegas":      (36.1699, -115.1398),
    "minneapolis":    (44.9778,  -93.2650),
    "nashville":      (36.1627,  -86.7816),
    "philadelphia":   (39.9526,  -75.1652),
    "portland":       (45.5051, -122.6750),
    "san diego":      (32.7157, -117.1611),
    "kuala lumpur":   (3.1390,  101.6869),
    "chongqing":      (29.4316,  106.9123),
    "jeddah":         (21.5433,   39.1728),
    "panama city":    (8.9936,   -79.5197),
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
    try:
        r = requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
        if r.status_code in (200, 201):
            try: return r.json()
            except: return []
    except Exception as e:
        log(f"⚠️  Supabase {method} {table}: {e}")
    return []

def sb_get(table: str, params: dict = None) -> list:
    return _sb("GET", table, params=params) or []

def sb_insert(table: str, data):
    headers = {
        "apikey":        SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }
    try:
        requests.post(f"{SB_URL}/rest/v1/{table}", headers=headers,
                      json=data, timeout=TIMEOUT)
    except Exception as e:
        log(f"⚠️  Supabase insert {table}: {e}")

def sb_upsert(table: str, data, on_conflict: str = None):
    params = {"on_conflict": on_conflict} if on_conflict else None
    _sb("POST", table, json=data, params=params)

# ── Polymarket ─────────────────────────────────────────────────────────────────

def fetch_positions(address: str) -> list:
    try:
        r = requests.get(f"{DATA_API}/positions",
            params={"user": address, "sizeThreshold": "0.01", "limit": "500"},
            timeout=TIMEOUT)
        if r.status_code == 200:
            d = r.json()
            return d if isinstance(d, list) else []
    except Exception as e:
        log(f"⚠️  fetch_positions: {e}")
    return []

# ── Parsing ────────────────────────────────────────────────────────────────────

def parse_city(title: str) -> str:
    m = re.search(r'temperature in ([\w\s\-]+?)(?:\s+be|\s+on)', title, re.I)
    return m.group(1).strip().lower() if m else ""

def parse_range(title: str):
    m = re.search(r'between\s+(\d+(?:\.\d+)?)[–\-](\d+(?:\.\d+)?)', title, re.I)
    if not m:
        m = re.search(r'between\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)', title, re.I)
    return (float(m.group(1)), float(m.group(2))) if m else None

def parse_date(title: str) -> str:
    m = re.search(r'on\s+(\w+ \d+(?:,?\s*\d{4})?)', title, re.I)
    if m:
        raw = re.sub(r'\?$', '', m.group(1).strip())
        if not re.search(r'\d{4}', raw):
            raw += f" {datetime.datetime.now().year}"
        for fmt in ("%B %d %Y", "%B %d, %Y"):
            try:
                return datetime.datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except: pass
    return datetime.datetime.now().strftime("%Y-%m-%d")

# ── Météo ──────────────────────────────────────────────────────────────────────

def fetch_forecast(city: str, date_str: str):
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
    except: pass
    return None

# ── Analyse Claude Haiku ───────────────────────────────────────────────────────

def explain_position(trader, outcome, city, r_low, r_high, price, amount, forecast):
    gap = round(forecast - (r_low + r_high) / 2, 1) if forecast and r_low else None

    # Explication sans API si données insuffisantes
    if not city or r_low is None:
        return f"{outcome} à {price:.0%} — fourchette non parsée."
    if not forecast:
        return f"{outcome} {r_low}-{r_high}°F à {price:.0%} — prévision météo indisponible."

    # Explication locale rapide (fallback)
    def local():
        if outcome.lower() == "no":
            if abs(gap) >= 5:
                return (f"NO à {price:.0%} : prévision {forecast}°F, soit {abs(gap):.0f}°F "
                        f"{'sous' if gap < 0 else 'au-dessus de'} la fourchette {r_low}-{r_high}°F. "
                        f"Fourchette très improbable, marge solide.")
            else:
                return (f"NO à {price:.0%} : prévision {forecast}°F très proche de la fourchette "
                        f"{r_low}-{r_high}°F (écart {abs(gap):.1f}°F). Position risquée.")
        else:
            if abs(gap) <= 2:
                return (f"YES à {price:.0%} : prévision {forecast}°F cible exactement "
                        f"{r_low}-{r_high}°F. Signal météo aligné.")
            else:
                return (f"YES à {price:.0%} : prévision {forecast}°F vs fourchette "
                        f"{r_low}-{r_high}°F (écart {abs(gap):.1f}°F). Pari spéculatif.")

    if not ANTHROPIC_KEY:
        return local()

    prompt = f"""Trader Polymarket : @{trader}
Position : {outcome} sur {city.title()} entre {r_low}-{r_high}°F
Prix : {price:.0%}  |  Mise : ${amount:.0f}
Prévision météo : {forecast}°F  |  Écart avec fourchette : {gap:+.1f}°F

En 2 phrases max, explique pourquoi ce trader a pris cette position. Sois factuel et précis. Français."""

    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_KEY,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 120,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=15)
        if r.status_code == 200:
            return r.json()["content"][0]["text"].strip()
    except: pass
    return local()

# ── Détection nouvelles positions ──────────────────────────────────────────────

def known_condition_ids(trader: str) -> set:
    rows = sb_get("positions_tracker", params={
        "trader": f"eq.{trader}", "select": "condition_id", "limit": "2000"})
    return {r["condition_id"] for r in rows if r.get("condition_id")}

def detect_new_positions(trader: str, address: str) -> int:
    positions = fetch_positions(address)
    if not positions:
        return 0

    known   = known_condition_ids(trader)
    new_pos = [p for p in positions
               if float(p.get("currentValue") or 0) > 0.01
               and p.get("conditionId") not in known]

    count = 0
    for p in new_pos:
        cid     = p.get("conditionId", "")
        title   = p.get("title", "")
        outcome = p.get("outcome", "")
        price   = float(p.get("avgPrice") or 0)
        amount  = float(p.get("initialValue") or 0)
        city    = parse_city(title)
        bounds  = parse_range(title)
        date_s  = parse_date(title)
        r_low   = bounds[0] if bounds else None
        r_high  = bounds[1] if bounds else None

        forecast = fetch_forecast(city, date_s) if city and bounds else None
        gap      = round(forecast - (r_low + r_high) / 2, 1) if forecast and bounds else None
        analysis = explain_position(trader, outcome, city, r_low, r_high, price, amount, forecast)

        if outcome.lower() == "no":
            certainty = "high" if price >= 0.85 else "medium" if price >= 0.75 else "low"
        else:
            certainty = "moonshot" if price <= 0.15 else "speculative" if price <= 0.45 else "standard"

        sb_upsert("positions_tracker", {
            "trader":        trader,
            "condition_id":  cid,
            "title":         title[:300],
            "city":          city,
            "range_low":     r_low,
            "range_high":    r_high,
            "market_date":   date_s,
            "outcome":       outcome,
            "price":         price,
            "amount_usdc":   amount,
            "forecast_temp": forecast,
            "gap":           gap,
            "analysis":      analysis,
            "certainty":     certainty,
            "detected_at":   datetime.datetime.now(UTC).isoformat(),
        }, on_conflict="trader,condition_id")
        count += 1
        gap_s = f" | gap={gap:+.1f}°F" if gap is not None else ""
        log(f"  🆕 [{trader}] {outcome} {city or '?'} {r_low}-{r_high}°F "
            f"@ {price:.0%} ${amount:.0f}{gap_s} [{certainty}]")
        if analysis:
            log(f"     💬 {analysis[:130]}")

    return count

# ── Rapport de stratégie ───────────────────────────────────────────────────────

def generate_report(trader: str):
    positions = sb_get("positions_tracker", params={
        "trader": f"eq.{trader}", "limit": "500",
        "order": "detected_at.desc"})
    if len(positions) < 3:
        log(f"[{trader}] Pas assez de positions pour un rapport ({len(positions)})")
        return

    nos  = [p for p in positions if (p.get("outcome") or "").lower() == "no"]
    yess = [p for p in positions if (p.get("outcome") or "").lower() == "yes"]
    vol  = sum(float(p.get("amount_usdc") or 0) for p in positions)

    # Stats par ville
    by_city = defaultdict(lambda: {"no": 0, "yes": 0, "vol": 0})
    for p in positions:
        c = p.get("city") or "?"
        side = (p.get("outcome") or "").lower()
        by_city[c]["no" if side == "no" else "yes"] += 1
        by_city[c]["vol"] += float(p.get("amount_usdc") or 0)
    top_cities = sorted(by_city.items(), key=lambda x: -x[1]["vol"])[:6]

    # Prix moyens
    no_prices  = [float(p["price"]) for p in nos  if p.get("price")]
    yes_prices = [float(p["price"]) for p in yess if p.get("price")]
    no_avg  = round(sum(no_prices)  / len(no_prices),  2) if no_prices  else 0
    yes_avg = round(sum(yes_prices) / len(yes_prices), 2) if yes_prices else 0

    # Gaps météo
    gaps = [float(p["gap"]) for p in positions if p.get("gap") is not None]
    gap_avg = round(sum(gaps) / len(gaps), 1) if gaps else None

    # Positions risquées (gap < 3°F)
    risky = [p for p in positions
             if p.get("gap") is not None and abs(float(p["gap"])) < 3
             and (p.get("outcome") or "").lower() == "no"]

    # Lignes pour le prompt
    lines = []
    for p in positions[:40]:
        g = f"gap={float(p['gap']):+.1f}°F" if p.get("gap") is not None else "gap=?"
        lines.append(
            f"- {p.get('outcome','')} {(p.get('city') or '?').title()} "
            f"{p.get('range_low','?')}-{p.get('range_high','?')}°F "
            f"@ {float(p.get('price',0)):.0%} ${float(p.get('amount_usdc',0)):.0f} "
            f"| prévision={p.get('forecast_temp','?')}°F {g} | {p.get('certainty','?')}"
        )

    villes_str = ", ".join(
        f"{c.title()}(NO×{s['no']} YES×{s['yes']} ${s['vol']:.0f})"
        for c, s in top_cities)

    prompt = f"""Tu analyses le profil de trading de @{trader} sur Polymarket (marchés météo US).
L'objectif est de RÉPLIQUER sa stratégie dans notre bot ProfitWeather V2.

DONNÉES GLOBALES :
- {len(positions)} positions trackées | ${vol:.0f} volume total
- NO : {len(nos)} positions (prix moyen {no_avg:.0%})
- YES : {len(yess)} positions (prix moyen {yes_avg:.0%})
- Écart météo moyen (prévision vs fourchette) : {f'{gap_avg:+.1f}°F' if gap_avg else 'N/A'}
- Positions risquées (gap < 3°F) : {len(risky)}
- Top villes : {villes_str}

DERNIÈRES 40 POSITIONS :
{chr(10).join(lines)}

Génère un rapport ACTIONNABLE en français avec ces sections :
## 🎯 Stratégie principale
(Comment il sélectionne ses marchés, ses critères d'entrée)

## 🏙️ Villes et fourchettes cibles
(Quelles villes, quelles fourchettes il évite ou cible, pourquoi)

## 💰 Gestion des mises et prix d'entrée
(À quel prix il entre, quelle taille de mise, comment il scale)

## ⚠️ Signaux d'alarme à éviter
(Ses erreurs, positions risquées, ce qui peut mal tourner)

## ✅ Règles concrètes à copier dans notre bot
(5 règles précises et chiffrées à implémenter immédiatement)

Sois précis, utilise les chiffres réels. 20-25 phrases."""

    analyse = ""
    # Essaie Claude d'abord
    if ANTHROPIC_KEY:
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_KEY,
                         "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": "claude-haiku-4-5-20251001", "max_tokens": 800,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=30)
            if r.status_code == 200:
                analyse = r.json()["content"][0]["text"].strip()
        except Exception as e:
            log(f"⚠️  Claude rapport: {e}")

    # Fallback Mistral
    if not analyse and MISTRAL_KEY:
        try:
            r = requests.post("https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {MISTRAL_KEY}",
                         "Content-Type": "application/json"},
                json={"model": "mistral-small-latest", "max_tokens": 800,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=30)
            if r.status_code == 200:
                analyse = r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log(f"⚠️  Mistral rapport: {e}")

    if not analyse:
        log(f"[{trader}] Aucune API disponible pour le rapport")
        return

    sb_insert("tracker_rapports", {
        "trader":        trader,
        "analyse_text":  analyse,
        "nb_positions":  len(positions),
        "nb_no":         len(nos),
        "nb_yes":        len(yess),
        "vol_total":     round(vol, 2),
        "villes_top":    villes_str,
        "prix_no_moyen": no_avg,
        "prix_yes_moyen": yes_avg,
        "created_at":    datetime.datetime.now(UTC).isoformat(),
    })
    log(f"📊 [{trader}] Rapport généré ({len(positions)} positions analysées)")
    log(f"\n{'='*60}\n{analyse[:400]}…\n{'='*60}")

# ── Boucle principale ──────────────────────────────────────────────────────────

def run_cycle(cycle: int):
    log(f"─── Cycle #{cycle} ───")
    total = 0
    for trader, address in TRADERS.items():
        n = detect_new_positions(trader, address)
        total += n
    log(f"  {total} nouvelle(s) position(s) détectée(s)")

    # Rapport toutes les REPORT_EVERY cycles
    if cycle > 0 and cycle % REPORT_EVERY == 0:
        log("📊 Génération des rapports de stratégie…")
        for trader in TRADERS:
            generate_report(trader)

if __name__ == "__main__":
    log("🔍 Tracker de positions démarré")
    for t, a in TRADERS.items():
        log(f"   → {t} ({a[:12]}…)")
    log(f"   Cycle : {INTERVAL} min | Rapport : toutes les {INTERVAL * REPORT_EVERY // 60}h")

    # Rapport immédiat au démarrage si données existantes
    log("📊 Rapport initial…")
    for trader in TRADERS:
        generate_report(trader)

    cycle = 0
    while True:
        try:
            run_cycle(cycle)
        except KeyboardInterrupt:
            log("Arrêté")
            break
        except Exception as e:
            import traceback
            log(f"Erreur cycle #{cycle}: {e}\n{traceback.format_exc()}")
        cycle += 1
        log(f"Prochain cycle dans {INTERVAL} min…")
        time.sleep(INTERVAL * 60)
