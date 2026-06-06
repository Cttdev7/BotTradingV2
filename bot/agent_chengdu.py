"""
agent_chengdu.py — Suivi du marché température maximale à Chengdu sur Polymarket
Tourne en continu. Toutes les 15 minutes :
- Analyse les 11 options de température du jour
- Enregistre les signaux >80%
- Vérifie les résolutions des jours précédents
- Calcule les stats globales
"""

import json, os, time, datetime, requests

GAMMA_API     = "https://gamma-api.polymarket.com"
TIMEOUT       = 15
INTERVAL      = 900  # 15 min

TRACKING_FILE = os.path.join(os.path.dirname(__file__), "chengdu_tracking.json")
STATS_FILE    = os.path.join(os.path.dirname(__file__), "chengdu_stats.json")

MONTHS = ["january","february","march","april","may","june",
          "july","august","september","october","november","december"]
MONTHS_FR = ["janvier","février","mars","avril","mai","juin",
             "juillet","août","septembre","octobre","novembre","décembre"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default

def _save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%d/%m %H:%M')}] {msg}", flush=True)

def slug_for(date):
    return f"highest-temperature-in-chengdu-on-{MONTHS[date.month-1]}-{date.day}-{date.year}"

# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_event(slug):
    """Récupère toutes les options de température pour un slug donné."""
    try:
        r = requests.get(f"{GAMMA_API}/events", params={"slug": slug}, timeout=TIMEOUT)
        r.raise_for_status()
        events = r.json()
        if not events:
            return None, []
        event = events[0]
        markets = []
        for m in event.get("markets", []):
            raw_p = m.get("outcomePrices", [])
            raw_o = m.get("outcomes", [])
            prices   = json.loads(raw_p) if isinstance(raw_p, str) else raw_p
            outcomes = json.loads(raw_o) if isinstance(raw_o, str) else raw_o
            if not prices or not outcomes:
                continue
            yes_price = next((float(p) for o, p in zip(outcomes, prices) if o.lower() == "yes"), None)
            if yes_price is None:
                continue
            markets.append({
                "condition_id": m.get("conditionId", ""),
                "question":     m.get("question", ""),
                "yes_price":    yes_price,
                "volume":       float(m.get("volume24hr") or m.get("volume") or 0),
                "closed":       m.get("closed", False),
            })
        return event, markets
    except Exception as e:
        log(f"⚠️  Erreur fetch {slug}: {e}")
        return None, []

# ── Signaux ───────────────────────────────────────────────────────────────────

def scan_signals(markets, tracking, date_str):
    """Détecte les nouvelles options franchissant 80% et les enregistre."""
    tracked_ids = {t["condition_id"] for t in tracking}
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    new_signals = []

    for m in markets:
        if m["condition_id"] in tracked_ids:
            continue
        if m["yes_price"] >= 0.80:
            entry = {
                "condition_id":        m["condition_id"],
                "question":            m["question"],
                "yes_price_au_signal": round(m["yes_price"] * 100, 1),
                "volume":              round(m["volume"], 0),
                "detecte_le":          now,
                "date_marche":         date_str,
                "resultat":            None,
                "resolu_le":           None,
            }
            tracking.append(entry)
            new_signals.append(entry)
            log(f"  🎯 SIGNAL: {m['question'][:60]} ({m['yes_price']*100:.0f}%)")

    return tracking, new_signals

# ── Résolution ────────────────────────────────────────────────────────────────

def check_resolved(tracking):
    """Vérifie si des marchés en attente ont été résolus."""
    unresolved = [t for t in tracking if t["resultat"] is None]
    if not unresolved:
        return tracking

    # Regrouper les marchés à vérifier par date (slug)
    slugs_to_check = set()
    for t in unresolved:
        try:
            d = datetime.datetime.strptime(t["date_marche"], "%d/%m/%Y")
            slugs_to_check.add((slug_for(d), t["date_marche"]))
        except Exception:
            pass

    for slug, date_str in slugs_to_check:
        event, markets = fetch_event(slug)
        if not markets:
            continue
        by_id = {m["condition_id"]: m for m in markets}
        for t in tracking:
            if t["resultat"] is not None or t["date_marche"] != date_str:
                continue
            m = by_id.get(t["condition_id"])
            if not m or not m["closed"]:
                continue
            now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            if m["yes_price"] >= 0.99:
                t["resultat"]  = "GAGNE"
                t["resolu_le"] = now
                log(f"  ✅ GAGNÉ : {t['question'][:55]}")
            elif m["yes_price"] <= 0.01:
                t["resultat"]  = "PERDU"
                t["resolu_le"] = now
                log(f"  ❌ PERDU : {t['question'][:55]}")

    return tracking

# ── Stats ─────────────────────────────────────────────────────────────────────

def compute_stats(tracking):
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNE"]
    perdus  = [t for t in resolus  if t["resultat"] == "PERDU"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None

    # Stats par date
    by_date = {}
    for t in tracking:
        d = t["date_marche"]
        if d not in by_date:
            by_date[d] = {"signaux": 0, "gagnes": 0, "perdus": 0, "en_attente": 0}
        by_date[d]["signaux"] += 1
        if t["resultat"] == "GAGNE":
            by_date[d]["gagnes"] += 1
        elif t["resultat"] == "PERDU":
            by_date[d]["perdus"] += 1
        else:
            by_date[d]["en_attente"] += 1

    return {
        "total_signaux":  len(tracking),
        "en_attente":     len(tracking) - len(resolus),
        "resolus":        len(resolus),
        "gagnes":         len(gagnes),
        "perdus":         len(perdus),
        "taux_victoire":  taux,
        "par_date":       by_date,
        "historique":     tracking[-50:],
        "derniere_maj":   datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "verdict": (
            "✅ Stratégie rentable"        if taux is not None and taux >= 60 else
            "⚠️ Stratégie à surveiller"   if taux is not None and taux >= 50 else
            "❌ Stratégie non rentable"    if taux is not None else
            "⏳ En attente de données"
        ),
    }

# ── Boucle principale ─────────────────────────────────────────────────────────

def run():
    log("🌡️  Agent Chengdu démarré")
    log("   Marché : température maximale à Chengdu (Polymarket)")
    log("   Seuil  : 80% YES | Scan : toutes les 15 min")
    log("")

    while True:
        now       = datetime.datetime.now()
        tomorrow  = now + datetime.timedelta(days=1)
        today_slug = slug_for(tomorrow)
        date_str   = tomorrow.strftime("%d/%m/%Y")

        log(f"── Cycle {now.strftime('%d/%m/%Y %H:%M')} ──")
        log(f"   Marché du jour : {today_slug}")

        tracking = _load(TRACKING_FILE, [])

        # 1. Vérifier résolutions des jours précédents
        log("Vérification des marchés résolus…")
        tracking = check_resolved(tracking)

        # 2. Fetch marché du jour
        log("Fetch marché Chengdu du jour…")
        event, markets = fetch_event(today_slug)

        if not markets:
            log("   ⚠️  Aucun marché trouvé pour aujourd'hui")
        else:
            top = sorted(markets, key=lambda x: x["yes_price"], reverse=True)
            log(f"   {len(markets)} options | Top: {top[0]['question'].split('be ')[-1].split(' on')[0]} "
                f"à {top[0]['yes_price']*100:.0f}%")

            for m in sorted(markets, key=lambda x: x["yes_price"], reverse=True):
                flag = "🔥" if m["yes_price"] >= 0.80 else ("📊" if m["yes_price"] >= 0.30 else "  ")
                log(f"   {flag} {m['yes_price']*100:5.1f}%  {m['question'].split('be ')[-1].split(' on')[0]}")

            # 3. Détecter signaux >80%
            tracking, new_signals = scan_signals(markets, tracking, date_str)
            if new_signals:
                log(f"   🎯 {len(new_signals)} nouveau(x) signal(s) enregistré(s) !")
            else:
                log("   Aucun nouveau signal (aucune option à 80%+)")

        # 4. Sauvegarder
        _save(TRACKING_FILE, tracking)
        stats = compute_stats(tracking)
        _save(STATS_FILE, stats)

        log(f"📊 Signaux:{stats['total_signaux']} | Résolus:{stats['resolus']} | "
            f"✅{stats['gagnes']} ❌{stats['perdus']} | Taux:{stats['taux_victoire']}% | {stats['verdict']}")
        log(f"   Prochain cycle dans 15 min")
        log("")

        time.sleep(INTERVAL)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run()
