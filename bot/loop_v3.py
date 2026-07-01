"""
loop_v3.py — ProfitWeather V3 : achat YES précoce + surveillance station officielle.

Stratégie (opposée à loop_v2.py qui achète NO tard et cher) :
  1. Détecte les marchés température Polymarket dès leur création (toutes villes)
  2. Identifie la fourchette la plus proche de la prévision Open-Meteo (source retenue
     après backtest — voir backtest_weather_sources.py, meilleure précision toutes régions)
  3. Achète YES si le prix est encore bas (≤15¢) et que Claude Haiku confirme (confiance ≥3/5)
  4. Surveille ensuite la station météo officielle de résolution (extraite du
     `resolutionSource` du marché) — vend immédiatement si la fourchette est compromise,
     ou si le prix a chuté de 30% depuis l'achat

Objectif : ~60% de réussite mais gains asymétriques (petites pertes, gros gains,
symétrique à l'inverse de sailor82/V2 qui jouent la sécurité à prix élevé).

Compte Polymarket : même que ProfitWeather V2 — partage le solde, plafond 50% chacun
(voir MAX_EXPOSURE_PCT=0.5 dans loop_v2.py). Table Supabase : profitweather_v3_trades.
Déploiement : Fly.io app "profitweather-v3", région yyz (Toronto).
"""

from __future__ import annotations
import os, sys, re, time, signal, datetime, json, requests
from zoneinfo import ZoneInfo

_PYTHON311 = os.path.expanduser("~/.pyenv/versions/3.11.9/lib/python3.11/site-packages")
if os.path.exists(_PYTHON311) and _PYTHON311 not in sys.path:
    sys.path.insert(0, _PYTHON311)

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(".env")

from weather_validator import CITY_COORDS, CITY_TZ

# ── Config ────────────────────────────────────────────────────────────────────

SCAN_INTERVAL   = 90        # 1.5 min entre les cycles (détection + surveillance)
MAX_ENTRY_PRICE = 0.15      # n'achète que si l'ask est encore ≤ 15¢ (fenêtre d'ouverture)
MAX_TRADE_PCT   = 0.10      # max 10% du capital alloué à V3 par trade
V3_EXPOSURE_CAP = 0.50      # V3 ne dépasse jamais 50% du solde total en position ouverte
STOP_LOSS_PCT   = 0.30      # vend si le prix de revente a chuté de 30% depuis l'achat
MIN_CONFIDENCE  = 3         # confiance Haiku minimum pour acheter (1-5)
MIN_BET         = 5.0       # $5 minimum par trade
LATE_DAY_HOUR   = 18        # heure locale à partir de laquelle "pic déjà passé" devient un signal fort
TIMEOUT         = 12

DATA_API  = "https://data-api.polymarket.com"
CLOB_API  = "https://clob.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
METEO_API = "https://api.open-meteo.com/v1/forecast"
METAR_API = "https://aviationweather.gov/api/data/metar"
HAIKU_API = "https://api.anthropic.com/v1/messages"

SB_URL = os.getenv("SUPABASE_URL", "https://obqkqhlqlowxrxbyvktl.supabase.co")
SB_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")

PRIVATE_KEY    = os.getenv("PRIVATE_KEY", "")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
API_KEY        = os.getenv("API_KEY", "")
API_SECRET     = os.getenv("API_SECRET", "")
API_PASSPHRASE = os.getenv("API_PASSPHRASE", "")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
DRY_RUN        = os.getenv("V3_DRY_RUN", "true").lower() == "true"

PARIS = ZoneInfo("Europe/Paris")
UTC   = ZoneInfo("UTC")

# Villes surveillées — mêmes 45 villes que pm_api._WEATHER_VILLES / weather_validator
WEATHER_VILLES = [{"slug": slug, "tz": CITY_TZ.get(slug, "UTC")} for slug in CITY_COORDS]

POLYGON_RPC   = "https://polygon-bor-rpc.publicnode.com"
PUSD_CONTRACT = "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb"

# ── Graceful shutdown ─────────────────────────────────────────────────────────

_shutdown = False

def _sigterm_handler(signum, frame):
    global _shutdown
    _shutdown = True
    log("🛑 SIGTERM — arrêt propre en cours…")

signal.signal(signal.SIGTERM, _sigterm_handler)
signal.signal(signal.SIGINT,  _sigterm_handler)

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[V3][{datetime.datetime.now(PARIS).strftime('%d/%m %H:%M:%S')}] {msg}", flush=True)

# ── Supabase ──────────────────────────────────────────────────────────────────

def _sb_headers() -> dict:
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

def sb_get(table: str, params: dict = None) -> list:
    try:
        r = requests.get(f"{SB_URL}/rest/v1/{table}", headers=_sb_headers(),
                         params=params, timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        log(f"⚠️ Supabase GET {table}: {e}")
        return []

def sb_insert(table: str, data: dict):
    try:
        requests.post(f"{SB_URL}/rest/v1/{table}", headers=_sb_headers(),
                      json=data, timeout=TIMEOUT)
    except Exception as e:
        log(f"⚠️ Supabase INSERT {table}: {e}")

def sb_upsert(table: str, data: dict):
    """Insert ou met à jour si condition_id existe déjà (ex: prix rechecké plusieurs cycles de suite)."""
    try:
        headers = _sb_headers()
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
        requests.post(f"{SB_URL}/rest/v1/{table}?on_conflict=condition_id",
                      headers=headers, json=data, timeout=TIMEOUT)
    except Exception as e:
        log(f"⚠️ Supabase UPSERT {table}: {e}")

def sb_update(table: str, condition_id: str, data: dict):
    try:
        requests.patch(f"{SB_URL}/rest/v1/{table}", headers=_sb_headers(),
                       params={"condition_id": f"eq.{condition_id}"}, json=data, timeout=TIMEOUT)
    except Exception as e:
        log(f"⚠️ Supabase UPDATE {table}: {e}")

# Statuts terminaux : une fois atteints, on ne réévalue plus jamais ce marché.
# "skipped_price_too_high" n'en fait PAS partie : beaucoup de marchés tout juste créés
# affichent un ask ~0.99 par défaut (pas encore de vraie liquidité) — le prix peut
# encore devenir intéressant à un cycle suivant, donc on continue de le rechecker.
_TERMINAL_STATUSES = {"open", "skipped_confidence", "failed", "sold_early", "sell_failed"}

def already_seen(condition_id: str) -> bool:
    rows = sb_get("profitweather_v3_trades", {
        "condition_id": f"eq.{condition_id}", "select": "status", "limit": "1",
    })
    if not rows:
        return False
    return rows[0].get("status") in _TERMINAL_STATUSES

def get_open_positions() -> list:
    return sb_get("profitweather_v3_trades", {"status": "eq.open", "select": "*"})

def get_v3_open_exposure() -> float:
    rows = get_open_positions()
    return sum(float(r.get("bet_usdc") or 0) for r in rows)

# ── Solde on-chain ────────────────────────────────────────────────────────────

def _rpc_call(method: str, params: list) -> str:
    r = requests.post(POLYGON_RPC, json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
                       timeout=TIMEOUT)
    r.raise_for_status()
    return r.json().get("result", "0x0")

def get_total_balance() -> float:
    """Solde pUSD disponible on-chain (cash réel, hors positions ouvertes)."""
    try:
        data = "0x70a08231" + WALLET_ADDRESS[2:].lower().zfill(64)
        pusd_hex = _rpc_call("eth_call", [{"to": PUSD_CONTRACT, "data": data}, "latest"])
        return round(int(pusd_hex, 16) / 1e6, 2)
    except Exception as e:
        log(f"⚠️ get_total_balance: {e}")
        return 0.0

# ── Parsing marché ────────────────────────────────────────────────────────────

def _event_slug(city: str, date: datetime.date) -> str:
    return f"highest-temperature-in-{city}-on-{date.strftime('%B').lower()}-{date.day}-{date.year}"

def _detect_unit(question: str) -> str:
    m = re.search(r"°\s*([FC])\b", question, re.IGNORECASE)
    if m:
        return "fahrenheit" if m.group(1).upper() == "F" else "celsius"
    return "fahrenheit"

def parse_range(question: str) -> tuple[float, float, str] | None:
    unit = _detect_unit(question)
    m = re.search(r"between (\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", question, re.IGNORECASE)
    if m:
        return float(m.group(1)), float(m.group(2)), unit
    m = re.search(r"(\d+(?:\.\d+)?)\s*°?[FC]?\s+or below", question, re.IGNORECASE)
    if m:
        return -200.0, float(m.group(1)), unit
    m = re.search(r"(\d+(?:\.\d+)?)\s*°?[FC]?\s+or higher", question, re.IGNORECASE)
    if m:
        return float(m.group(1)), 200.0, unit
    m = re.search(r"be (\d+(?:\.\d+)?)\s*°?[FC]\b", question, re.IGNORECASE)
    if m:
        v = float(m.group(1))
        return v, v + 1, unit
    return None

def fetch_city_day_event(city: str, date: datetime.date) -> dict | None:
    slug = _event_slug(city, date)
    try:
        r = requests.get(f"{GAMMA_API}/events", params={"slug": slug}, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        events = r.json()
        return events[0] if events else None
    except Exception as e:
        log(f"⚠️ fetch_city_day_event {city}: {e}")
        return None

# ── Météo — source retenue après backtest : Open-Meteo blend (sans modèle spécifique) ──

def fetch_forecast_max(lat: float, lon: float, date: datetime.date, unit: str) -> float | None:
    try:
        r = requests.get(METEO_API, params={
            "latitude": lat, "longitude": lon,
            "daily": "temperature_2m_max",
            "temperature_unit": unit,
            "timezone": "UTC",
            "start_date": str(date), "end_date": str(date),
        }, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        vals = r.json().get("daily", {}).get("temperature_2m_max", [])
        return round(vals[0], 1) if vals and vals[0] is not None else None
    except Exception as e:
        log(f"⚠️ fetch_forecast_max: {e}")
        return None

# ── Station officielle de résolution (extraite de resolutionSource) ──────────

def extract_station_code(resolution_source: str) -> str | None:
    """Ex: https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA -> KLGA"""
    if not resolution_source:
        return None
    code = resolution_source.rstrip("/").split("/")[-1]
    return code if code else None

def fetch_metar_observations(station: str, hours: int = 10) -> dict | None:
    """
    Relevés METAR réels des dernières `hours` heures pour la station donnée (code ICAO).
    Retourne current_c, max_observed_c, trend, peak_passed (temp en baisse de >2°C depuis le max).
    """
    try:
        r = requests.get(METAR_API, params={"ids": station, "format": "json", "hours": hours}, timeout=TIMEOUT)
        if r.status_code != 200 or not r.json():
            return None
        raw_obs = r.json()
        obs = [(d.get("obsTime") or d.get("reportTime", ""), float(d["temp"]))
               for d in raw_obs if d.get("temp") is not None]
        if not obs:
            return None
        obs_chrono = list(reversed(obs))
        temps_c = [v for _, v in obs_chrono]
        current_c = temps_c[-1]
        max_obs_c = max(temps_c)
        delta = current_c - temps_c[0] if len(temps_c) > 1 else 0
        trend = "rising" if delta > 0.5 else ("falling" if delta < -0.5 else "stable")
        peak_passed = (max_obs_c - current_c) >= 2.0
        return {"current_c": current_c, "max_observed_c": max_obs_c, "trend": trend, "peak_passed": peak_passed}
    except Exception as e:
        log(f"⚠️ fetch_metar_observations {station}: {e}")
        return None

def c_to_f(c: float) -> float:
    return c * 9 / 5 + 32

def get_local_hour(tz_name: str) -> int:
    try:
        return datetime.datetime.now(ZoneInfo(tz_name)).hour
    except Exception:
        return 12

# ── Claude Haiku — analyse d'entrée ───────────────────────────────────────────

def analyze_entry(title: str, price: float, bounds: tuple, unit: str, forecast: float) -> tuple[str, int]:
    if not ANTHROPIC_KEY:
        return "Clé Anthropic manquante", 3

    sym = "°F" if unit == "fahrenheit" else "°C"
    prompt = f"""Tu analyses une opportunité d'achat YES très précoce sur un marché météo Polymarket qui vient d'ouvrir.

MARCHÉ : {title}
Prix actuel (ask) : {price:.2f}¢ — encore proche du prix d'ouverture
Fourchette visée : {bounds[0]}-{bounds[1]}{sym}
Prévision Open-Meteo (source retenue après backtest) : {forecast}{sym}

Stratégie : acheter YES tôt et pas cher sur la fourchette la plus proche de la prévision, revendre
en cours de journée si la station météo officielle s'écarte de la fourchette. Objectif ~60% de
réussite avec des gains asymétriques (le prix bas limite la perte, la résolution à 1$ maximise le gain).

Réponds en JSON uniquement :
{{
  "reasoning": "explication en 2-3 phrases pourquoi cette fourchette est cohérente avec la prévision",
  "risk": "risque principal en 1 phrase (ex: prévision encore incertaine à J+X, marge trop faible)",
  "confidence": <entier 1-5 où 5=prévision très centrée sur la fourchette, 1=risqué>
}}

Règle : confidence >= 3 seulement si la prévision tombe clairement dans la fourchette (pas en bordure)."""

    try:
        r = requests.post(HAIKU_API, headers={
            "x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json",
        }, json={
            "model": "claude-haiku-4-5-20251001", "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }, timeout=20)
        if r.status_code != 200:
            log(f"⚠️ Haiku HTTP {r.status_code}: {r.text[:100]}")
            return "Analyse indisponible (API error)", 3
        text = r.json()["content"][0]["text"].strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            reasoning = parsed.get("reasoning", text)
            risk = parsed.get("risk", "")
            confidence = min(5, max(1, int(parsed.get("confidence", 3))))
            return f"{reasoning} | Risque : {risk}", confidence
        return text[:200], 3
    except Exception as e:
        log(f"⚠️ Haiku analyse: {e}")
        return "Analyse indisponible", 3

# ── Polymarket — infos marché & ordres ────────────────────────────────────────

def get_token_id(condition_id: str, outcome: str) -> str | None:
    try:
        r = requests.get(f"{CLOB_API}/markets/{condition_id}", timeout=TIMEOUT)
        if r.status_code == 200:
            for token in r.json().get("tokens", []):
                if token.get("outcome", "").upper() == outcome.upper():
                    return token.get("token_id")
    except Exception as e:
        log(f"⚠️ get_token_id: {e}")
    return None

def get_best_ask(token_id: str) -> float | None:
    try:
        r = requests.get(f"{CLOB_API}/book", params={"token_id": token_id}, timeout=TIMEOUT)
        if r.status_code == 200:
            asks = r.json().get("asks", [])
            if asks:
                return float(asks[0]["price"])
    except Exception as e:
        log(f"⚠️ get_best_ask: {e}")
    return None

def get_best_bid(token_id: str) -> float | None:
    try:
        r = requests.get(f"{CLOB_API}/book", params={"token_id": token_id}, timeout=TIMEOUT)
        if r.status_code == 200:
            bids = r.json().get("bids", [])
            if bids:
                return float(bids[-1]["price"])  # meilleur bid = dernier de la liste triée croissant
    except Exception as e:
        log(f"⚠️ get_best_bid: {e}")
    return None

_client = None

def _get_client():
    global _client
    if _client is None:
        from polymarket.clients.secure import SecureClient
        from polymarket.models.clob.api_key import ApiKeyCreds
        creds = ApiKeyCreds(apiKey=API_KEY, secret=API_SECRET, passphrase=API_PASSPHRASE)
        _client = SecureClient.create(private_key=PRIVATE_KEY, wallet=WALLET_ADDRESS, credentials=creds)
    return _client

def get_token_balance(token_id: str) -> float:
    try:
        client = _get_client()
        bal = client.get_balance_allowance(asset_type="CONDITIONAL", token_id=token_id)
        return float(bal.balance) / 1_000_000
    except Exception as e:
        log(f"⚠️ get_token_balance: {e}")
        return 0.0

def buy_yes(token_id: str, price: float, bet_usdc: float) -> bool:
    if DRY_RUN:
        log(f"🔵 [DRY] BUY Yes — ${bet_usdc:.2f} @ {price:.2f}")
        return True
    try:
        client = _get_client()
        resp = client.place_market_order(token_id=token_id, side="BUY", amount=bet_usdc)
        ok = getattr(resp, "ok", False)
        log(f"{'✅' if ok else '❌'} BUY Yes ${bet_usdc:.2f} @ {price:.2f} | {getattr(resp, 'status', '?')}")
        return bool(ok)
    except Exception as e:
        log(f"⚠️ buy_yes: {e}")
        return False

def sell_yes(token_id: str, shares: float) -> bool:
    if DRY_RUN:
        log(f"🔵 [DRY] SELL Yes — {shares:.2f} tokens")
        return True
    try:
        client = _get_client()
        resp = client.place_market_order(token_id=token_id, side="SELL", shares=shares)
        ok = getattr(resp, "ok", False)
        log(f"{'✅' if ok else '❌'} SELL Yes {shares:.2f} tokens | {getattr(resp, 'status', '?')}")
        return bool(ok)
    except Exception as e:
        log(f"⚠️ sell_yes: {e}")
        return False

# ── Cycle de détection ────────────────────────────────────────────────────────

_seen_events: set[str] = set()   # en mémoire — évite de retraiter le même event au sein d'un run

def _gather_candidate(city: str, tz_name: str, delta: int) -> dict | None:
    """
    Partie réseau (parallélisable, sans effet de bord) : détecte si (ville, jour) a un
    marché ouvert avec une fourchette qui matche la prévision. Retourne un dict décrivant
    soit un candidat exploitable, soit une raison de le marquer "vu" (seen=True), soit
    None si on doit retenter au prochain cycle (ex: pas encore de prix/prévision dispo).
    """
    try:
        local_date = datetime.datetime.now(UTC).astimezone(ZoneInfo(tz_name)).date()
    except Exception:
        local_date = datetime.datetime.now(UTC).date()
    target_date = local_date + datetime.timedelta(days=delta)
    slug = _event_slug(city, target_date)

    if slug in _seen_events:
        return None

    event = fetch_city_day_event(city, target_date)
    if not event or event.get("closed"):
        return {"slug": slug, "seen": True}

    markets = event.get("markets", [])
    if not markets:
        return None

    station = extract_station_code(event.get("resolutionSource", ""))
    coords = CITY_COORDS.get(city)
    if not coords:
        return {"slug": slug, "seen": True}
    lat, lon = coords

    bounds_by_cid = {}
    unit = None
    for m in markets:
        cid = m.get("conditionId", "")
        question = m.get("question", "")
        rng = parse_range(question)
        if not rng or not cid:
            continue
        bounds_by_cid[cid] = (rng[0], rng[1], m)
        unit = rng[2]

    if not bounds_by_cid or not unit:
        return {"slug": slug, "seen": True}

    forecast = fetch_forecast_max(lat, lon, target_date, unit)
    if forecast is None:
        return None

    match_cid, match_market = None, None
    for cid, (low, high, m) in bounds_by_cid.items():
        if low <= forecast <= high:
            match_cid, match_market = cid, m
            break

    if not match_cid:
        return {"slug": slug, "seen": True}

    if already_seen(match_cid):
        return {"slug": slug, "seen": True}

    title = match_market.get("question", "")
    low, high, _ = bounds_by_cid[match_cid]

    token_id = get_token_id(match_cid, "Yes")
    if not token_id:
        return {"slug": slug, "seen": True}

    price = get_best_ask(token_id)
    if price is None:
        return None

    return {
        "slug": slug, "seen": True, "candidate": True,
        "city": city, "match_cid": match_cid, "title": title,
        "low": low, "high": high, "unit": unit, "forecast": forecast,
        "station": station, "token_id": token_id, "price": price,
    }


def scan_for_new_markets():
    balance = get_total_balance()
    v3_cap = balance * V3_EXPOSURE_CAP
    v3_open = get_v3_open_exposure()
    room_left = v3_cap - v3_open

    if room_left < MIN_BET:
        log(f"💰 Plafond V3 atteint (exposition ${v3_open:.2f} / cap ${v3_cap:.2f}) — pas de nouvel achat ce cycle")
        return

    from concurrent.futures import ThreadPoolExecutor, as_completed

    jobs = [(v["slug"], v["tz"], delta) for v in WEATHER_VILLES for delta in (0, 1)]
    candidates = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(_gather_candidate, city, tz_name, delta) for city, tz_name, delta in jobs]
        for f in as_completed(futures):
            if _shutdown:
                break
            result = f.result()
            if not result:
                continue
            if result.get("seen"):
                _seen_events.add(result["slug"])
            if result.get("candidate"):
                candidates.append(result)

    for c in candidates:
        if _shutdown:
            return
        city, match_cid, title = c["city"], c["match_cid"], c["title"]
        low, high, unit, forecast = c["low"], c["high"], c["unit"], c["forecast"]
        station, token_id, price = c["station"], c["token_id"], c["price"]

        if price > MAX_ENTRY_PRICE:
            log(f"⏭ {city} {title[:50]} — prix {price:.2f}¢ déjà trop haut (>{MAX_ENTRY_PRICE:.2f})")
            sb_upsert("profitweather_v3_trades", {
                "condition_id": match_cid, "title": title, "city": city, "outcome": "Yes",
                "token_id": token_id, "forecast_source": "open_meteo_blend", "forecast_temp": forecast,
                "station_source": station, "entry_price": price, "bet_usdc": 0.0,
                "status": "skipped_price_too_high", "dry_run": DRY_RUN,
            })
            continue

        log(f"🔍 Candidat V3 : {city} — {title[:55]} | prévision {forecast} vs fourchette {low}-{high} | ask {price:.2f}¢")
        analysis, confidence = analyze_entry(title, price, (low, high), unit, forecast)
        log(f"   🤖 conf={confidence}/5 | {analysis[:100]}")

        if confidence < MIN_CONFIDENCE:
            sb_upsert("profitweather_v3_trades", {
                "condition_id": match_cid, "title": title, "city": city, "outcome": "Yes",
                "token_id": token_id, "forecast_source": "open_meteo_blend", "forecast_temp": forecast,
                "station_source": station, "entry_price": price, "bet_usdc": 0.0,
                "confidence": confidence, "analysis": analysis,
                "status": "skipped_confidence", "dry_run": DRY_RUN,
            })
            continue

        v3_allocated = balance * V3_EXPOSURE_CAP
        bet = round(min(v3_allocated * MAX_TRADE_PCT, room_left), 2)
        if bet < MIN_BET:
            log(f"   ⏭ Budget V3 insuffisant (room=${room_left:.2f})")
            continue

        ok = buy_yes(token_id, price, bet)
        sb_upsert("profitweather_v3_trades", {
            "condition_id": match_cid, "title": title, "city": city, "outcome": "Yes",
            "token_id": token_id, "forecast_source": "open_meteo_blend", "forecast_temp": forecast,
            "station_source": station, "entry_price": price, "bet_usdc": bet,
            "confidence": confidence, "analysis": analysis,
            "status": "open" if ok else "failed", "dry_run": DRY_RUN,
        })
        room_left -= bet

# ── Cycle de surveillance ─────────────────────────────────────────────────────

def monitor_open_positions():
    positions = get_open_positions()
    if not positions:
        return

    for pos in positions:
        if _shutdown:
            return
        cid        = pos["condition_id"]
        token_id   = pos.get("token_id")
        entry_price = float(pos.get("entry_price") or 0)
        bet_usdc   = float(pos.get("bet_usdc") or 0)
        city       = pos.get("city", "")
        station    = pos.get("station_source")
        title      = pos.get("title", "")

        rng = parse_range(title)
        if not rng or not token_id or entry_price <= 0:
            continue
        low, high, unit = rng

        # 1) Stop-loss prix
        bid = get_best_bid(token_id)
        if bid is not None and bid <= entry_price * (1 - STOP_LOSS_PCT):
            log(f"🔻 Stop-loss {city} — {title[:50]} : {entry_price:.2f}→{bid:.2f} (-{STOP_LOSS_PCT*100:.0f}%)")
            _close_position(pos, "stop_loss", bid, token_id, bet_usdc, entry_price)
            continue

        # 2) Divergence météo — station officielle
        if station:
            obs = fetch_metar_observations(station)
            if obs:
                max_obs = obs["max_observed_c"] if unit == "celsius" else c_to_f(obs["max_observed_c"])
                tz_name = CITY_TZ.get(city, "UTC")
                local_hour = get_local_hour(tz_name)

                if max_obs > high:
                    log(f"🌡️ Divergence météo {city} — max observé {max_obs:.1f} > borne haute {high}")
                    exit_price = bid if bid is not None else 0.0
                    _close_position(pos, "weather_divergence", exit_price, token_id, bet_usdc, entry_price)
                    continue

                if obs["peak_passed"] and local_hour >= LATE_DAY_HOUR and max_obs < low:
                    log(f"🌡️ Divergence météo {city} — pic passé, max observé {max_obs:.1f} < borne basse {low}")
                    exit_price = bid if bid is not None else 0.0
                    _close_position(pos, "weather_divergence", exit_price, token_id, bet_usdc, entry_price)
                    continue

        # sinon : on tient jusqu'à résolution naturelle

def _close_position(pos: dict, reason: str, exit_price: float, token_id: str, bet_usdc: float, entry_price: float):
    shares = bet_usdc / entry_price if entry_price > 0 else 0.0
    if not DRY_RUN:
        real_shares = get_token_balance(token_id)
        if real_shares > 0:
            shares = real_shares
    ok = sell_yes(token_id, shares)
    proceeds = shares * exit_price
    pnl = proceeds - bet_usdc
    sb_update("profitweather_v3_trades", pos["condition_id"], {
        "status": "sold_early" if ok else "sell_failed",
        "exit_reason": reason, "exit_price": exit_price, "pnl": round(pnl, 2),
        "closed_at": datetime.datetime.now(UTC).isoformat(),
    })

# ── Main ──────────────────────────────────────────────────────────────────────

def run_cycle():
    scan_for_new_markets()
    monitor_open_positions()

def main():
    log("🚀 ProfitWeather V3 démarré")
    log(f"   DRY_RUN={DRY_RUN} | MAX_ENTRY_PRICE={MAX_ENTRY_PRICE:.2f} | MAX_TRADE_PCT={MAX_TRADE_PCT*100:.0f}% de l'alloc V3")
    log(f"   V3_EXPOSURE_CAP={V3_EXPOSURE_CAP*100:.0f}% | STOP_LOSS={STOP_LOSS_PCT*100:.0f}% | MIN_CONF={MIN_CONFIDENCE}/5")
    log(f"   SCAN_INTERVAL={SCAN_INTERVAL}s | {len(WEATHER_VILLES)} villes surveillées")

    while not _shutdown:
        try:
            run_cycle()
        except Exception as e:
            log(f"⚠️ Erreur cycle: {e}")

        for _ in range(SCAN_INTERVAL):
            if _shutdown:
                break
            time.sleep(1)

    log("👋 Bot arrêté proprement")

if __name__ == "__main__":
    main()
