"""
agent_deko.py — Analyse Deko

Surveille les trades de sailor82 (@sailor82, Polymarket) en temps réel.
Détecte ses patterns (timing, villes, fourchettes, mise/certitude) et
génère des analyses pour améliorer notre bot V2.

Tables Supabase utilisées :
  - deko_trades   : chaque trade détecté de sailor82
  - deko_rapports : analyses périodiques Claude
  - deko_stats    : stats cumulatives (win rate, P&L, patterns)
"""

import os, re, json, time, datetime, requests
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")

SAILOR82_ADDRESS = "0xbbb72a812cfbc5217d77c0a0018c71f174d3a11a"
DATA_API         = "https://data-api.polymarket.com"
GAMMA_API        = "https://gamma-api.polymarket.com"
INTERVAL_MIN     = 15
ANALYSE_EVERY    = 4   # générer une analyse toutes les N cycles (1h)
TIMEOUT          = 10

SB_URL = os.getenv("SUPABASE_URL", "https://obqkqhlqlowxrxbyvktl.supabase.co")
SB_KEY = os.getenv("SUPABASE_KEY", "")

# ── Logging ────────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[DEKO][{datetime.datetime.now(PARIS).strftime('%d/%m %H:%M')}] {msg}", flush=True)

# ── Supabase ───────────────────────────────────────────────────────────────────

def _sb(method: str, table: str, **kwargs) -> list | dict:
    url     = f"{SB_URL}/rest/v1/{table}"
    headers = {
        "apikey":        SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }
    r = requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
    if r.status_code in (200, 201):
        try:
            return r.json()
        except Exception:
            return []
    return []

def sb_get(table: str, params: dict = None) -> list:
    return _sb("GET", table, params=params) or []

def sb_upsert(table: str, data: dict | list):
    _sb("POST", table, json=data)

def sb_patch(table: str, params: dict, data: dict):
    url = f"{SB_URL}/rest/v1/{table}"
    headers = {
        "apikey":        SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type":  "application/json",
    }
    requests.patch(url, headers=headers, params=params, json=data, timeout=TIMEOUT)

# ── Polymarket API ─────────────────────────────────────────────────────────────

def fetch_activity(limit: int = 100) -> list:
    """Récupère l'activité récente de sailor82."""
    try:
        r = requests.get(
            f"{DATA_API}/activity",
            params={"user": SAILOR82_ADDRESS, "limit": limit},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return r.json() if isinstance(r.json(), list) else []
    except Exception as e:
        log(f"⚠️  fetch_activity : {e}")
    return []

def fetch_positions() -> list:
    """Récupère les positions ouvertes de sailor82."""
    try:
        r = requests.get(
            f"{DATA_API}/positions",
            params={"user": SAILOR82_ADDRESS, "sizeThreshold": "0.01"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else []
    except Exception as e:
        log(f"⚠️  fetch_positions : {e}")
    return []

def fetch_market_title(condition_id: str) -> str:
    """Récupère le titre du marché depuis Gamma API."""
    try:
        r = requests.get(
            f"{GAMMA_API}/markets",
            params={"conditionId": condition_id},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                return data[0].get("question", "")
    except Exception:
        pass
    return ""

# ── Extraction des patterns ────────────────────────────────────────────────────

def _parse_city(question: str) -> str:
    """Extrait la ville depuis la question du marché."""
    m = re.search(r'temperature in ([\w\s\-]+?)(?:\s+be|\s+on)', question, re.I)
    if m:
        return m.group(1).strip().lower()
    return "unknown"

def _parse_range(question: str) -> tuple[float, float] | None:
    """Extrait la fourchette °F depuis la question."""
    m = re.search(r'between\s+([\d.]+)\s+and\s+([\d.]+)', question, re.I)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r'([\d.]+)[–\-]([\d.]+)\s*[°]?[FC]', question)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None

def _parse_date(question: str) -> str:
    """Extrait la date depuis la question."""
    m = re.search(r'on\s+(\w+\s+\d+,?\s+\d{4}|\d{4}-\d{2}-\d{2})', question, re.I)
    return m.group(1).strip() if m else ""

def _classify_certainty(outcome: str, price: float) -> str:
    """Classifie la certitude du trade comme sailor82 le fait."""
    if outcome.lower() == "no":
        if price >= 0.85:
            return "high"
        elif price >= 0.75:
            return "medium"
        else:
            return "low"
    else:  # YES
        if price <= 0.20:
            return "moonshot"
        elif price <= 0.45:
            return "speculative"
        else:
            return "standard"

# ── Détection et stockage des nouveaux trades ──────────────────────────────────

def _known_tx_hashes() -> set:
    """Récupère les tx_hash déjà enregistrés pour éviter les doublons."""
    rows = sb_get("deko_trades", params={"select": "tx_hash", "limit": "500", "order": "detected_at.desc"})
    return {r.get("tx_hash", "") for r in rows if r.get("tx_hash")}

def detect_new_trades() -> list:
    """Détecte et enregistre les nouveaux trades de sailor82."""
    activity = fetch_activity(limit=50)
    if not activity:
        return []

    known = _known_tx_hashes()
    new_trades = []

    for act in activity:
        tx_hash = act.get("transactionHash", "") or act.get("id", "")
        if tx_hash in known:
            continue

        trade_type = (act.get("type") or "").upper()
        if trade_type not in ("BUY", "TRADE"):
            continue

        condition_id = act.get("conditionId", "") or act.get("condition_id", "")
        outcome      = act.get("outcome", "") or act.get("side", "")
        price        = float(act.get("price") or 0)
        amount       = float(act.get("usdcSize") or act.get("amount") or act.get("size") or 0)
        timestamp    = act.get("timestamp") or act.get("createdAt") or 0

        # Convertit timestamp unix en datetime
        if isinstance(timestamp, (int, float)) and timestamp > 1e9:
            dt = datetime.datetime.fromtimestamp(timestamp, tz=ZoneInfo("UTC"))
        else:
            dt = datetime.datetime.now(ZoneInfo("UTC"))

        # Récupère le titre du marché si absent
        question = act.get("title", "") or act.get("question", "")
        if not question and condition_id:
            question = fetch_market_title(condition_id)

        city       = _parse_city(question)
        bounds     = _parse_range(question)
        certainty  = _classify_certainty(outcome, price)
        hour_utc   = dt.hour
        hour_et    = (dt.astimezone(ZoneInfo("America/New_York"))).hour

        trade = {
            "tx_hash":      tx_hash,
            "condition_id": condition_id,
            "question":     question[:200],
            "city":         city,
            "range_low":    bounds[0] if bounds else None,
            "range_high":   bounds[1] if bounds else None,
            "outcome":      outcome,
            "price":        price,
            "amount_usdc":  amount,
            "certainty":    certainty,
            "hour_utc":     hour_utc,
            "hour_et":      hour_et,
            "trade_date":   dt.strftime("%Y-%m-%d"),
            "pnl":          None,
            "result":       None,
            "detected_at":  datetime.datetime.now(ZoneInfo("UTC")).isoformat(),
        }
        sb_upsert("deko_trades", trade)
        new_trades.append(trade)
        log(f"  🆕 {outcome} {city} {bounds} à {price:.2f}¢ | ${amount:.0f} | {hour_et}h ET [{certainty}]")

    return new_trades

# ── Résolution des trades ──────────────────────────────────────────────────────

def resolve_open_trades():
    """Met à jour le résultat des trades non résolus."""
    open_trades = sb_get("deko_trades", params={
        "result": "is.null",
        "order":  "detected_at.desc",
        "limit":  "100",
    })
    if not open_trades:
        return

    for t in open_trades:
        cid = t.get("condition_id", "")
        if not cid:
            continue
        try:
            r = requests.get(f"{GAMMA_API}/markets/{cid}", timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            m = r.json()
            if not m.get("closed") and not m.get("resolved"):
                continue

            raw_p = m.get("outcomePrices", [])
            raw_o = m.get("outcomes", [])
            prices   = json.loads(raw_p) if isinstance(raw_p, str) else raw_p
            outcomes = json.loads(raw_o) if isinstance(raw_o, str) else raw_o

            outcome_lower = (t.get("outcome") or "").lower()
            price_final = next(
                (float(p) for o, p in zip(outcomes, prices) if o.lower() == outcome_lower),
                None
            )
            if price_final is None:
                continue

            won   = price_final >= 0.95
            lost  = price_final <= 0.05
            if not (won or lost):
                continue

            result  = "GAGNANT" if won else "PERDANT"
            amount  = float(t.get("amount_usdc") or 0)
            entry   = float(t.get("price") or 0)
            tokens  = amount / entry if entry > 0 else 0
            pnl     = round(tokens * (price_final - entry), 2)

            sb_patch("deko_trades", {"tx_hash": f"eq.{t['tx_hash']}"}, {
                "result":      result,
                "pnl":         pnl,
                "price_final": price_final,
            })
            log(f"  ✅ Résolu {t.get('city','?')} {t.get('outcome','')} → {result} | P&L ${pnl:.2f}")
        except Exception as e:
            log(f"  ⚠️  Résolution {cid[:12]} : {e}")

# ── Stats cumulatives ──────────────────────────────────────────────────────────

def update_stats():
    """Calcule et sauvegarde les stats cumulatives de sailor82."""
    all_trades = sb_get("deko_trades", params={"limit": "500", "order": "detected_at.desc"})
    if not all_trades:
        return {}

    resolved = [t for t in all_trades if t.get("result")]
    wins     = [t for t in resolved if t.get("result") == "GAGNANT"]
    losses   = [t for t in resolved if t.get("result") == "PERDANT"]
    open_t   = [t for t in all_trades if not t.get("result")]

    total_pnl   = round(sum(t.get("pnl") or 0 for t in resolved), 2)
    win_rate    = round(len(wins) / len(resolved) * 100, 1) if resolved else 0
    total_vol   = round(sum(t.get("amount_usdc") or 0 for t in all_trades), 2)

    # Analyse par ville
    cities = {}
    for t in resolved:
        c = t.get("city", "unknown")
        if c not in cities:
            cities[c] = {"wins": 0, "losses": 0, "pnl": 0, "vol": 0}
        if t.get("result") == "GAGNANT":
            cities[c]["wins"] += 1
        else:
            cities[c]["losses"] += 1
        cities[c]["pnl"] += t.get("pnl") or 0
        cities[c]["vol"] += t.get("amount_usdc") or 0

    # Analyse par heure ET
    hours = {}
    for t in all_trades:
        h = t.get("hour_et")
        if h is not None:
            hours[str(h)] = hours.get(str(h), 0) + 1

    # Analyse NO vs YES
    no_trades  = [t for t in resolved if (t.get("outcome") or "").lower() == "no"]
    yes_trades = [t for t in resolved if (t.get("outcome") or "").lower() == "yes"]
    no_wins    = len([t for t in no_trades  if t.get("result") == "GAGNANT"])
    yes_wins   = len([t for t in yes_trades if t.get("result") == "GAGNANT"])

    stats = {
        "id":             "global",
        "total_trades":   len(all_trades),
        "resolved":       len(resolved),
        "wins":           len(wins),
        "losses":         len(losses),
        "open":           len(open_t),
        "win_rate":       win_rate,
        "total_pnl":      total_pnl,
        "total_volume":   total_vol,
        "no_win_rate":    round(no_wins / len(no_trades) * 100, 1) if no_trades else 0,
        "yes_win_rate":   round(yes_wins / len(yes_trades) * 100, 1) if yes_trades else 0,
        "cities":         json.dumps(cities),
        "hours_et":       json.dumps(hours),
        "updated_at":     datetime.datetime.now(ZoneInfo("UTC")).isoformat(),
    }
    sb_upsert("deko_stats", stats)
    log(f"📊 Stats : {len(wins)}W/{len(losses)}L ({win_rate}%) | P&L ${total_pnl:.2f} | {len(open_t)} ouverts")
    return stats

# ── Analyse Claude ─────────────────────────────────────────────────────────────

def generate_analysis(stats: dict):
    """Génère une analyse Mistral des patterns de sailor82."""
    api_key = os.getenv("MISTRAL_API_KEY2") or os.getenv("MISTRAL_API_KEY", "")
    if not api_key:
        log("⚠️  MISTRAL_API_KEY2 manquante dans .env")
        return

    all_trades = sb_get("deko_trades", params={"limit": "100", "order": "detected_at.desc"})
    resolved   = [t for t in all_trades if t.get("result")]

    if len(resolved) < 3:
        log("Pas assez de trades résolus pour analyser")
        return

    # Formate les trades pour Claude
    lines = []
    for t in resolved[-30:]:
        lines.append(
            f"- {t.get('trade_date','')} {t.get('hour_et','?')}h ET | "
            f"{t.get('outcome','')} {t.get('city','')} "
            f"[{t.get('range_low','?')}-{t.get('range_high','?')}°F] "
            f"@ {t.get('price',0):.2f} | ${t.get('amount_usdc',0):.0f} | "
            f"{t.get('result','?')} ({'+' if (t.get('pnl') or 0)>0 else ''}${t.get('pnl',0):.2f})"
        )

    cities_data = json.loads(stats.get("cities") or "{}")
    hours_data  = json.loads(stats.get("hours_et") or "{}")
    best_hour   = max(hours_data, key=lambda h: hours_data[h]) if hours_data else "?"
    best_city   = max(cities_data, key=lambda c: cities_data[c].get("wins", 0)) if cities_data else "?"

    prompt = f"""Tu analyses les trades de sailor82, un trader Polymarket très performant (stratégie NO sur fourchettes météo US).

STATS GLOBALES :
- Total trades : {stats.get('total_trades', 0)}
- Win rate : {stats.get('win_rate', 0)}%
- P&L total : ${stats.get('total_pnl', 0):.2f}
- Win rate NO : {stats.get('no_win_rate', 0)}%
- Win rate YES : {stats.get('yes_win_rate', 0)}%
- Heure favorite : {best_hour}h ET
- Ville favorite : {best_city}

DISTRIBUTION HORAIRE (heure ET) :
{json.dumps(hours_data, indent=2)}

PERFORMANCE PAR VILLE :
{json.dumps(cities_data, indent=2)}

DERNIERS 30 TRADES :
{chr(10).join(lines)}

Analyse en 5-8 phrases :
1. À quelle heure exacte il trade et pourquoi
2. Quelles villes il évite et pourquoi (pertes)
3. Quel prix NO il cible (trop bas = risqué ?)
4. Ce qu'on doit copier pour notre bot V2
5. Ce qu'on doit éviter (ses erreurs coûteuses)
6. 2-3 recommandations concrètes pour notre V2

Réponds en français, direct et actionnable."""

    r = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": "mistral-small-latest", "max_tokens": 800,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=30,
    )
    analyse_text = ""
    if r.status_code == 200:
        analyse_text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()

    rapport = {
        "analyse_text": analyse_text,
        "stats_json":   json.dumps(stats),
        "trades_count": len(resolved),
        "created_at":   datetime.datetime.now(ZoneInfo("UTC")).isoformat(),
    }
    sb_upsert("deko_rapports", rapport)
    log(f"🧠 Analyse Claude générée ({len(analyse_text)} chars)")
    log(f"\n{'='*60}\n{analyse_text}\n{'='*60}")

# ── Boucle principale ──────────────────────────────────────────────────────────

def run_cycle(cycle_count: int):
    log(f"─── Cycle #{cycle_count} ───")

    # 1. Détecte les nouveaux trades
    new = detect_new_trades()
    log(f"  {len(new)} nouveau(x) trade(s) détecté(s)")

    # 2. Résout les trades anciens
    resolve_open_trades()

    # 3. Met à jour les stats
    stats = update_stats()

    # 4. Analyse Claude toutes les ANALYSE_EVERY cycles
    if cycle_count % ANALYSE_EVERY == 0 and stats:
        log("🧠 Génération analyse Claude…")
        generate_analysis(stats)

if __name__ == "__main__":
    log("🔍 Analyse Deko démarré")
    log(f"   Cible : sailor82 ({SAILOR82_ADDRESS[:12]}…)")
    log(f"   Cycle : toutes les {INTERVAL_MIN} min")
    log(f"   Analyse Claude : toutes les {INTERVAL_MIN * ANALYSE_EVERY} min")

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
        log(f"Prochain cycle dans {INTERVAL_MIN} min…")
        time.sleep(INTERVAL_MIN * 60)
