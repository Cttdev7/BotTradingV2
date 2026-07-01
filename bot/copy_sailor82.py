"""
copy_sailor82.py — Copy-trade sailor82 sur marchés température Polymarket.

Au démarrage : fige une baseline des positions déjà ouvertes de sailor82 (ignorées, jamais copiées).

Cycle toutes les 2s :
  1. Détecte les nouvelles positions température de sailor82 (absentes de la baseline/déjà vues)
  2. Récupère la météo Open-Meteo pour la ville/date
  3. Claude Haiku analyse pourquoi sailor82 prend ce trade + note de confiance 1-5
  4. Si dérive prix < 5¢ et confiance >= 2 → réplique l'ordre (10% de sa mise, min $5, max $20)
  5. Log tout dans Supabase : copy_sailor82_trades (incl. analyse + prévision météo)

Compte Polymarket : même que ProfitWeather V2 (PRIVATE_KEY, WALLET_ADDRESS, API_KEY…)
Déploiement : Fly.io app "sailor82-copy", région yyz (Toronto).
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

# ── Config ────────────────────────────────────────────────────────────────────

SAILOR82_ADDRESS = "0xbbb72a812cfbc5217d77c0a0018c71f174d3a11a"
POLL_INTERVAL    = 2         # 2s entre les cycles — réagir vite avant que le prix ne bouge
TRADE_SIZE       = 5.0       # $5 fixe par trade copié, quelle que soit la mise de sailor82
MIN_CONFIDENCE   = 2         # confiance Haiku minimum pour copier (1-5)
STOP_LOSS_PCT    = 0.40      # -40% depuis notre prix d'entrée → on revend
TIMEOUT          = 12

# Dérive de prix max tolérée avant de copier, selon le prix d'entrée de sailor82 —
# analyse du 01/07/2026 sur 264 marchés résolus (activity API) : plus le prix est bas,
# plus il bouge vite, donc on tolère une dérive plus large avant de considérer l'entrée ratée.
PRICE_DRIFT_TIERS = [
    (0.00, 0.50, 0.08),
    (0.50, 0.85, 0.05),
    (0.85, 0.95, 0.03),
    (0.95, 1.01, 0.03),
]

def get_max_drift(price: float) -> float:
    for lo, hi, drift in PRICE_DRIFT_TIERS:
        if lo <= price < hi:
            return drift
    return 0.05

DATA_API   = "https://data-api.polymarket.com"
CLOB_API   = "https://clob.polymarket.com"
METEO_API  = "https://api.open-meteo.com/v1/forecast"
HAIKU_API  = "https://api.anthropic.com/v1/messages"

SB_URL    = os.getenv("SUPABASE_URL", "https://obqkqhlqlowxrxbyvktl.supabase.co")
SB_KEY    = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")

PRIVATE_KEY     = os.getenv("PRIVATE_KEY", "")
WALLET_ADDRESS  = os.getenv("WALLET_ADDRESS", "")
API_KEY         = os.getenv("API_KEY", "")
API_SECRET      = os.getenv("API_SECRET", "")
API_PASSPHRASE  = os.getenv("API_PASSPHRASE", "")
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
DRY_RUN         = os.getenv("COPY_DRY_RUN", "true").lower() == "true"

PARIS = ZoneInfo("Europe/Paris")
UTC   = ZoneInfo("UTC")

# Coordonnées des villes — priorité aux villes trader par sailor82
CITY_COORDS: dict[str, tuple[float, float]] = {
    "new york city":    (40.7128,  -74.0060),
    "new york":         (40.7128,  -74.0060),
    "nyc":              (40.7128,  -74.0060),
    "houston":          (29.7604,  -95.3698),
    "san francisco":    (37.7749, -122.4194),
    "los angeles":      (34.0522, -118.2437),
    "austin":           (30.2672,  -97.7431),
    "seattle":          (47.6062, -122.3321),
    "atlanta":          (33.7490,  -84.3880),
    "miami":            (25.7617,  -80.1918),
    "dallas":           (32.7767,  -96.7970),
    "chicago":          (41.8781,  -87.6298),
    "denver":           (39.7392, -104.9903),
    "london":           (51.5074,   -0.1278),
    "paris":            (48.8566,    2.3522),
    "tokyo":            (35.6762,  139.6503),
    "toronto":          (43.6532,  -79.3832),
    "madrid":           (40.4168,   -3.7038),
    "amsterdam":        (52.3676,    4.9041),
    "singapore":        ( 1.3521,  103.8198),
    "hong kong":        (22.3193,  114.1694),
    "seoul":            (37.5665,  126.9780),
    "taipei":           (25.0330,  121.5654),
    "beijing":          (39.9042,  116.4074),
    "shanghai":         (31.2304,  121.4737),
    "chengdu":          (30.5728,  104.0668),
    "guangzhou":        (23.1291,  113.2644),
    "mexico city":      (19.4326,  -99.1332),
    "cape town":        (-33.9249,  18.4241),
    "jeddah":           (21.5433,   39.1728),
    "istanbul":         (41.0082,   28.9784),
    "moscow":           (55.7558,   37.6173),
    "milan":            (45.4642,    9.1900),
    "warsaw":           (52.2297,   21.0122),
    "karachi":          (24.8607,   67.0011),
    "kuala lumpur":     ( 3.1390,  101.6869),
    "manila":           (14.5995,  120.9842),
    "munich":           (48.1351,   11.5820),
    "helsinki":         (60.1699,   24.9384),
}

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
    print(f"[COPY][{datetime.datetime.now(PARIS).strftime('%d/%m %H:%M:%S')}] {msg}", flush=True)

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

def sb_update(table: str, condition_id: str, data: dict):
    try:
        requests.patch(f"{SB_URL}/rest/v1/{table}", headers=_sb_headers(),
                       params={"condition_id": f"eq.{condition_id}"}, json=data, timeout=TIMEOUT)
    except Exception as e:
        log(f"⚠️ Supabase UPDATE {table}: {e}")

# ── Parsing marché ────────────────────────────────────────────────────────────

def is_temperature_market(title: str) -> bool:
    return "temperature" in title.lower()

def parse_city(title: str) -> str | None:
    """Extrait la ville depuis 'Will the highest temperature in Dallas be between...'"""
    m = re.search(r"temperature in (.+?) be (?:between|above|below|\d)", title, re.IGNORECASE)
    if m:
        return m.group(1).strip().lower()
    # fallback : format "highest-temperature-in-{city} on {date}"
    m = re.search(r"temperature in (.+?) on [A-Z]", title, re.IGNORECASE)
    if m:
        return m.group(1).strip().lower()
    return None

def parse_range(title: str) -> tuple[float, float] | None:
    """Extrait la fourchette °F depuis le titre."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*[–\-]\s*(\d+(?:\.\d+)?)\s*°?[FfCc]", title)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"be (\d+(?:\.\d+)?)\s*°?[FfCc]", title, re.IGNORECASE)
    if m:
        v = float(m.group(1))
        return v, v + 1
    return None

def parse_date(title: str) -> str | None:
    """Extrait la date ISO depuis le titre."""
    months = {"january":"01","february":"02","march":"03","april":"04","may":"05",
               "june":"06","july":"07","august":"08","september":"09","october":"10",
               "november":"11","december":"12"}
    m = re.search(r"on (\w+)\s+(\d+),?\s+(\d{4})", title, re.IGNORECASE)
    if m:
        month_n = months.get(m.group(1).lower())
        if month_n:
            return f"{m.group(3)}-{month_n}-{int(m.group(2)):02d}"
    return None

# ── Météo Open-Meteo ──────────────────────────────────────────────────────────

def fetch_forecast(city: str, date_str: str | None) -> float | None:
    """Retourne la température max prévue en °F pour la ville/date."""
    coords = CITY_COORDS.get(city)
    if not coords:
        return None
    lat, lon = coords
    params = {
        "latitude": lat, "longitude": lon,
        "daily": "temperature_2m_max",
        "temperature_unit": "fahrenheit",
        "timezone": "auto",
        "forecast_days": 7,
    }
    try:
        r = requests.get(METEO_API, params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        data = r.json()
        dates = data.get("daily", {}).get("time", [])
        temps = data.get("daily", {}).get("temperature_2m_max", [])
        if date_str and date_str in dates:
            idx = dates.index(date_str)
            return round(temps[idx], 1)
        if temps:
            return round(temps[0], 1)
    except Exception as e:
        log(f"⚠️ fetch_forecast: {e}")
    return None

# ── Claude Haiku — analyse du trade ──────────────────────────────────────────

def analyze_with_haiku(title: str, outcome: str, sailor_price: float,
                       sailor_amount: float, forecast_temp: float | None,
                       bounds: tuple | None) -> tuple[str, int]:
    """
    Demande à Claude Haiku d'analyser pourquoi sailor82 prend ce trade.
    Retourne (analyse_text, confidence 1-5).
    """
    if not ANTHROPIC_KEY:
        return "Clé Anthropic manquante", 3

    forecast_info = (
        f"Prévision Open-Meteo : {forecast_temp}°F" if forecast_temp
        else "Prévision météo : indisponible"
    )
    range_info = (
        f"Fourchette tradée : {bounds[0]}-{bounds[1]}°F" if bounds
        else "Fourchette : non parsée"
    )

    prompt = f"""Tu analyses un trade de sailor82, trader météo expert sur Polymarket (profil : NO à 84-96¢ sur villes US/internationales, win rate ~86%).

TRADE DÉTECTÉ :
- Marché : {title}
- Position : {outcome} à {sailor_price:.2f}¢ (mise : ${sailor_amount:.0f})
- {range_info}
- {forecast_info}

Réponds en JSON uniquement, format exact :
{{
  "reasoning": "explication en 2-3 phrases pourquoi ce trade est logique selon la météo",
  "risk": "risque principal en 1 phrase",
  "confidence": <entier 1-5 où 5=trade évident, 1=trade risqué>
}}

Règle : confidence >= 3 si la fourchette est clairement hors de la prévision (>3°F d'écart)."""

    try:
        r = requests.post(
            HAIKU_API,
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        if r.status_code != 200:
            log(f"⚠️ Haiku HTTP {r.status_code}: {r.text[:100]}")
            return "Analyse indisponible (API error)", 3
        text = r.json()["content"][0]["text"].strip()
        if not text:
            return "Analyse indisponible (réponse vide)", 3
        # Extrait le JSON même si Haiku ajoute du texte autour
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            parsed     = json.loads(json_match.group())
            reasoning  = parsed.get("reasoning", text)
            risk       = parsed.get("risk", "")
            confidence = min(5, max(1, int(parsed.get("confidence", 3))))
            return f"{reasoning} | Risque : {risk}", confidence
        # fallback : texte libre, confiance neutre
        return text[:200], 3
    except Exception as e:
        log(f"⚠️ Haiku analyse: {e}")
    return "Analyse indisponible", 3

# ── Polymarket ────────────────────────────────────────────────────────────────

def fetch_sailor82_positions() -> list:
    try:
        r = requests.get(f"{DATA_API}/positions",
                         params={"user": SAILOR82_ADDRESS, "sizeThreshold": "0.01", "limit": "500"},
                         timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else []
    except Exception as e:
        log(f"⚠️ fetch_positions: {e}")
    return []

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
    """Meilleur ask = prix le plus BAS. L'API ne garantit pas l'ordre de la liste (vu en
    pratique triée du pire au meilleur, donc asks[0] ≠ le vrai meilleur prix) — on calcule
    le min explicitement plutôt que de faire confiance à l'ordre retourné."""
    try:
        r = requests.get(f"{CLOB_API}/book", params={"token_id": token_id}, timeout=TIMEOUT)
        if r.status_code == 200:
            asks = r.json().get("asks", [])
            if asks:
                return min(float(a["price"]) for a in asks)
    except Exception as e:
        log(f"⚠️ get_best_ask: {e}")
    return None

def get_best_bid(token_id: str) -> float | None:
    """Meilleur bid = prix le plus HAUT — calculé explicitement, même raison que get_best_ask."""
    try:
        r = requests.get(f"{CLOB_API}/book", params={"token_id": token_id}, timeout=TIMEOUT)
        if r.status_code == 200:
            bids = r.json().get("bids", [])
            if bids:
                return max(float(b["price"]) for b in bids)
    except Exception as e:
        log(f"⚠️ get_best_bid: {e}")
    return None

def already_copied(condition_id: str) -> bool:
    rows = sb_get("copy_sailor82_trades", {
        "condition_id": f"eq.{condition_id}",
        "select": "condition_id",
        "limit": "1",
    })
    return bool(rows)

def get_open_positions() -> list:
    return sb_get("copy_sailor82_trades", {"status": "eq.open", "select": "*"})

# ── Ordre ─────────────────────────────────────────────────────────────────────

_client = None

def _get_client():
    global _client
    if _client is None:
        from polymarket.clients.secure import SecureClient
        from polymarket.models.clob.api_key import ApiKeyCreds
        creds = ApiKeyCreds(apiKey=API_KEY, secret=API_SECRET, passphrase=API_PASSPHRASE)
        _client = SecureClient.create(
            private_key=PRIVATE_KEY,
            wallet=WALLET_ADDRESS,
            credentials=creds,
        )
    return _client

def get_token_balance(token_id: str) -> float:
    try:
        client = _get_client()
        bal = client.get_balance_allowance(asset_type="CONDITIONAL", token_id=token_id)
        return float(bal.balance) / 1_000_000
    except Exception as e:
        log(f"⚠️ get_token_balance: {e}")
        return 0.0

def place_order(token_id: str, outcome: str, price: float, bet_usdc: float) -> bool:
    if DRY_RUN:
        log(f"🔵 [DRY] BUY {outcome} — ${bet_usdc:.2f} @ {price:.2f}")
        return True
    try:
        client = _get_client()
        resp = client.place_market_order(token_id=token_id, side="BUY", amount=bet_usdc)
        ok = getattr(resp, "ok", False)
        log(f"{'✅' if ok else '❌'} BUY {outcome} ${bet_usdc:.2f} @ {price:.2f} | {getattr(resp, 'status', '?')}")
        return bool(ok)
    except Exception as e:
        log(f"⚠️ place_order: {e}")
        return False

def sell_position(token_id: str, outcome: str, shares: float) -> bool:
    if DRY_RUN:
        log(f"🔵 [DRY] SELL {outcome} — {shares:.2f} tokens")
        return True
    try:
        client = _get_client()
        resp = client.place_market_order(token_id=token_id, side="SELL", shares=shares)
        ok = getattr(resp, "ok", False)
        log(f"{'✅' if ok else '❌'} SELL {outcome} {shares:.2f} tokens | {getattr(resp, 'status', '?')}")
        return bool(ok)
    except Exception as e:
        log(f"⚠️ sell_position: {e}")
        return False

# ── Baseline (ignore les positions déjà ouvertes au démarrage) ────────────────

def establish_baseline():
    """
    Fige les positions température déjà ouvertes par sailor82 au démarrage du bot,
    sans les analyser ni les copier — on ne veut copier que ses futurs trades, pas
    reproduire rétroactivement des positions qu'il a peut-être déjà à moitié résolues.
    """
    positions = fetch_sailor82_positions()
    n = 0
    for pos in positions:
        title = pos.get("title", "")
        cid   = pos.get("conditionId", "")
        if not is_temperature_market(title) or not cid:
            continue
        if already_copied(cid):
            continue
        _save(cid, title, pos.get("outcome", ""), None,
              float(pos.get("avgPrice") or 0), None,
              float(pos.get("initialValue") or 0), 0.0,
              "skipped_baseline", None, "Position déjà ouverte au démarrage du bot — ignorée", 0)
        n += 1
    log(f"📌 Baseline sailor82 : {n} position(s) déjà ouverte(s) mise(s) de côté (jamais copiées)")

# ── Cycle ─────────────────────────────────────────────────────────────────────

def run_cycle():
    positions = fetch_sailor82_positions()
    if not positions:
        log("Aucune position sailor82 récupérée")
        return

    sailor_open_cids = {
        p.get("conditionId") for p in positions
        if is_temperature_market(p.get("title", "")) and p.get("conditionId")
    }

    for pos in positions:
        if _shutdown:
            return

        title    = pos.get("title", "")
        cid      = pos.get("conditionId", "")
        outcome  = pos.get("outcome", "")
        s_price  = float(pos.get("avgPrice") or 0)
        s_amount = float(pos.get("initialValue") or 0)

        if not is_temperature_market(title):
            continue
        if not cid or not outcome or s_price <= 0 or s_amount <= 0:
            continue
        if already_copied(cid):
            continue

        log(f"🔍 Nouveau trade sailor82 : {outcome} — {title[:55]}")

        # Météo + analyse Haiku
        city        = parse_city(title)
        date_str    = parse_date(title)
        bounds      = parse_range(title)
        forecast    = fetch_forecast(city, date_str) if city else None
        analysis, confidence = analyze_with_haiku(title, outcome, s_price, s_amount, forecast, bounds)

        log(f"   🌡️  Prévision {city or '?'} : {forecast}°F | range {bounds} | conf={confidence}/5")
        log(f"   🤖 {analysis[:100]}")

        # Token & prix actuel
        token_id = get_token_id(cid, outcome)
        if not token_id:
            log(f"   ⚠️ Token introuvable")
            _save(cid, title, outcome, None, s_price, None, s_amount, 0.0,
                  "no_token", forecast, analysis, confidence)
            continue

        current_price = get_best_ask(token_id)
        if current_price is None:
            log(f"   ⚠️ Prix introuvable")
            _save(cid, title, outcome, token_id, s_price, None, s_amount, 0.0,
                  "no_price", forecast, analysis, confidence)
            continue

        drift = abs(current_price - s_price)
        log(f"   ℹ️ Dérive {drift:.2f}¢ (sailor={s_price:.2f} → now={current_price:.2f}) | conf={confidence}/5 — copié quand même (filtres désactivés)")

        log(f"   💰 Copie → ${TRADE_SIZE:.2f} (mise fixe)")

        ok = place_order(token_id, outcome, current_price, TRADE_SIZE)
        _save(cid, title, outcome, token_id, s_price, current_price, s_amount, TRADE_SIZE,
              "open" if ok else "failed", forecast, analysis, confidence)

    monitor_open_positions(sailor_open_cids)

# ── Surveillance des positions ouvertes — stop-loss 40% + suivi des sorties de sailor82 ──

def monitor_open_positions(sailor_open_cids: set):
    """
    On copie tout ce que fait sailor82, y compris ses ventes : si une position qu'on a
    copiée n'apparaît plus dans ses positions actuelles, il l'a fermée → on suit et on
    revend aussi. Indépendamment de ça, un stop-loss maison à -40% protège contre une
    chute de prix pendant qu'on attend la prochaine synchro avec lui.
    """
    positions = get_open_positions()
    for pos in positions:
        if _shutdown:
            return

        cid        = pos.get("condition_id")
        token_id   = pos.get("token_id")
        outcome    = pos.get("outcome", "")
        entry_price = float(pos.get("our_price") or 0)
        bet_usdc   = float(pos.get("our_bet") or 0)
        title      = pos.get("title", "")

        if not token_id or entry_price <= 0:
            continue

        bid = get_best_bid(token_id)

        if bid is not None and bid <= entry_price * (1 - STOP_LOSS_PCT):
            log(f"🔻 Stop-loss {title[:50]} : {entry_price:.2f}→{bid:.2f} (-{STOP_LOSS_PCT*100:.0f}%)")
            _close_position(cid, token_id, outcome, "stop_loss", bid, bet_usdc, entry_price)
            continue

        if cid not in sailor_open_cids:
            log(f"🚪 sailor82 a fermé sa position — {title[:50]} : on suit et on revend")
            exit_price = bid if bid is not None else 0.0
            _close_position(cid, token_id, outcome, "sailor_exit", exit_price, bet_usdc, entry_price)
            continue

def _close_position(cid: str, token_id: str, outcome: str, reason: str,
                     exit_price: float, bet_usdc: float, entry_price: float):
    shares = bet_usdc / entry_price if entry_price > 0 else 0.0
    if not DRY_RUN:
        real_shares = get_token_balance(token_id)
        if real_shares > 0:
            shares = real_shares
    ok = sell_position(token_id, outcome, shares)
    proceeds = shares * exit_price
    pnl = proceeds - bet_usdc
    sb_update("copy_sailor82_trades", cid, {
        "status": "closed_sell_failed" if not ok else ("closed_stop_loss" if reason == "stop_loss" else "closed_sailor_exit"),
        "exit_reason": reason, "exit_price": exit_price, "pnl": round(pnl, 2),
        "closed_at": datetime.datetime.now(UTC).isoformat(),
    })

def _save(cid, title, outcome, token_id, s_price, our_price, s_amount, our_bet,
          status, forecast, analysis, confidence):
    sb_insert("copy_sailor82_trades", {
        "condition_id":  cid,
        "title":         title,
        "outcome":       outcome,
        "token_id":      token_id,
        "sailor_price":  s_price,
        "our_price":     our_price,
        "sailor_amount": s_amount,
        "our_bet":       our_bet,
        "status":        status,
        "forecast_temp": forecast,
        "analysis":      analysis,
        "confidence":    confidence,
        "dry_run":       DRY_RUN,
        "created_at":    datetime.datetime.now(UTC).isoformat(),
    })

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log("🚀 Copy-trade sailor82 démarré")
    log(f"   DRY_RUN={DRY_RUN} | TRADE_SIZE=${TRADE_SIZE} | STOP_LOSS={STOP_LOSS_PCT*100:.0f}% | MIN_CONF={MIN_CONFIDENCE}/5")
    log(f"   POLL={POLL_INTERVAL}s | DRIFT_TIERS (prix→drift max): {PRICE_DRIFT_TIERS}")

    establish_baseline()

    while not _shutdown:
        try:
            run_cycle()
        except Exception as e:
            log(f"⚠️ Erreur cycle: {e}")

        for _ in range(POLL_INTERVAL):
            if _shutdown:
                break
            time.sleep(1)

    log("👋 Bot arrêté proprement")

if __name__ == "__main__":
    main()
