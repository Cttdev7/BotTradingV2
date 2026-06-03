"""
agent_meteo.py — Agent météo Polymarket
Tourne en continu. Toutes les heures :
- Scrute les marchés météo Polymarket
- Tracke les paris à YES > 80%
- Vérifie les résultats des marchés terminés
- Génère un résumé quotidien à 17h00 chaque jour
"""

import json, os, time, datetime, requests

GAMMA_API     = "https://gamma-api.polymarket.com"
TIMEOUT       = 15
INTERVAL      = 1800  # 30 min entre chaque cycle

TRACKING_FILE = os.path.join(os.path.dirname(__file__), "meteo_tracking.json")
RAPPORTS_FILE = os.path.join(os.path.dirname(__file__), "meteo_rapports.json")
RESUMES_FILE  = os.path.join(os.path.dirname(__file__), "meteo_resumes.json")

METEO_KEYWORDS = [
    "weather", "temperature", "rain", "snow", "hurricane", "storm",
    "celsius", "fahrenheit", "precipitation", "wind", "heat", "cold",
    "flood", "drought", "cyclone", "tornado", "blizzard", "frost",
    "hail", "thunder", "météo", "pluie", "neige", "tempête",
]

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

# ── Fetch ─────────────────────────────────────────────────────────────────────

def _parse_market(m):
    import json as _j
    raw_p = m.get("outcomePrices", [])
    raw_o = m.get("outcomes", [])
    prices   = _j.loads(raw_p) if isinstance(raw_p, str) else raw_p
    outcomes = _j.loads(raw_o) if isinstance(raw_o, str) else raw_o
    if not prices or not outcomes:
        return None
    yes_price = next((float(p) for o, p in zip(outcomes, prices) if o.lower() == "yes"), None)
    if yes_price is None:
        return None
    return {
        "condition_id": m.get("conditionId", ""),
        "question":     m.get("question", ""),
        "yes_price":    yes_price,
        "volume":       float(m.get("volume24hr") or m.get("volume") or 0),
        "closed":       m.get("closed", False),
    }

def fetch_markets(active=True, closed=False, limit=300):
    try:
        params = {"limit": limit, "order": "volume", "ascending": "false"}
        if active is not None:  params["active"] = str(active).lower()
        if closed is not None:  params["closed"] = str(closed).lower()
        r = requests.get(f"{GAMMA_API}/markets", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        raw = r.json()
        if not isinstance(raw, list):
            return []
        out = []
        for m in raw:
            p = _parse_market(m)
            if p and any(kw in p["question"].lower() for kw in METEO_KEYWORDS):
                out.append(p)
        return out
    except Exception as e:
        log(f"⚠️  Fetch erreur: {e}")
        return []

# ── Tracking ──────────────────────────────────────────────────────────────────

def update_tracking(tracking, active_markets):
    ids = {t["condition_id"] for t in tracking}
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    for m in active_markets:
        if m["condition_id"] in ids or m["yes_price"] < 0.80:
            continue
        tracking.append({
            "condition_id":       m["condition_id"],
            "question":           m["question"],
            "yes_price_au_track": round(m["yes_price"] * 100, 1),
            "volume":             round(m["volume"], 0),
            "tracke_le":          now,
            "resultat":           None,   # "GAGNE" ou "PERDU"
            "resolu_le":          None,
        })
        log(f"  📌 {m['question'][:65]} ({m['yes_price']*100:.0f}%)")
    return tracking

def check_resolved(tracking):
    closed = fetch_markets(active=False, closed=True)
    ids = {m["condition_id"]: m for m in closed}
    for t in tracking:
        if t["resultat"] is not None:
            continue
        m = ids.get(t["condition_id"])
        if not m:
            continue
        if m["yes_price"] >= 0.99:
            t["resultat"]  = "GAGNE"
            t["resolu_le"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            log(f"  ✅ GAGNÉ : {t['question'][:55]}")
        elif m["yes_price"] <= 0.01:
            t["resultat"]  = "PERDU"
            t["resolu_le"] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            log(f"  ❌ PERDU : {t['question'][:55]}")
    return tracking

# ── Rapport horaire simplifié ─────────────────────────────────────────────────

def build_rapport(tracking, active):
    resolus  = [t for t in tracking if t["resultat"] is not None]
    gagnes   = [t for t in resolus  if t["resultat"] == "GAGNE"]
    perdus   = [t for t in resolus  if t["resultat"] == "PERDU"]
    taux     = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    actifs85 = [m for m in active if m["yes_price"] >= 0.80]
    return {
        "heure":          datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "trackes":        len(tracking),
        "en_attente":     len(tracking) - len(resolus),
        "resolus":        len(resolus),
        "gagnes":         len(gagnes),
        "perdus":         len(perdus),
        "taux_victoire":  taux,
        "actifs_85":      [{"question": m["question"][:70], "pct": round(m["yes_price"]*100,1)} for m in actifs85],
        "verdict":        (
            "✅ Stratégie rentable" if taux is not None and taux >= 60 else
            "⚠️ Stratégie à surveiller" if taux is not None and taux >= 50 else
            "❌ Stratégie non rentable" if taux is not None else
            "⏳ En attente de données"
        ),
    }

# ── Résumé quotidien à 17h (Mistral) ─────────────────────────────────────────

def generate_resume_quotidien(tracking):
    key = os.getenv("MISTRAL_API_KEY", "")
    if not key:
        return "MISTRAL_API_KEY manquante."

    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNE"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None

    lignes = "\n".join(
        f"- {t['question'][:70]} | tracké à {t['yes_price_au_track']}% | {t['resultat']}"
        for t in resolus[-15:]
    ) or "Aucun marché résolu."

    prompt = f"""Résume en 5 lignes max ces stats de paris météo Polymarket à +80% :

Trackés: {len(tracking)} | Résolus: {len(resolus)} | Gagnés: {len(gagnes)} | Perdus: {len(resolus)-len(gagnes)} | Taux: {taux}%

Derniers résolus:
{lignes}

Réponds en français, sois très court et direct. Donne juste :
1. Le taux de réussite
2. Si la stratégie vaut le coup (oui/non et pourquoi en 1 phrase)
3. Un conseil pour demain"""

    try:
        r = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "mistral-small-latest", "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 200, "temperature": 0.2},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Erreur Mistral : {e}"

def save_resume(tracking, taux):
    resumes = _load(RESUMES_FILE, [])
    resume = {
        "date":          datetime.datetime.now().strftime("%d/%m/%Y"),
        "heure":         "17:00",
        "trackes":       len(tracking),
        "resolus":       len([t for t in tracking if t["resultat"] is not None]),
        "gagnes":        len([t for t in tracking if t["resultat"] == "GAGNE"]),
        "perdus":        len([t for t in tracking if t["resultat"] == "PERDU"]),
        "taux_victoire": taux,
        "analyse":       generate_resume_quotidien(tracking),
    }
    resumes.insert(0, resume)
    _save(RESUMES_FILE, resumes[:90])  # 90 jours max
    log(f"📋 Résumé quotidien sauvegardé — taux: {taux}%")
    return resume

# ── Boucle principale ─────────────────────────────────────────────────────────

def next_17h():
    """Retourne le prochain 17h00 (aujourd'hui ou demain)."""
    now = datetime.datetime.now()
    target = now.replace(hour=17, minute=0, second=0, microsecond=0)
    if now >= target:
        target += datetime.timedelta(days=1)
    return target

def run():
    log("🌦  Agent Météo Polymarket démarré")
    log(f"   Cycle : toutes les heures | Résumé : chaque jour à 17h00")
    log("")

    derniere_date_resume = None

    while True:
        now = datetime.datetime.now()
        log(f"── Cycle {now.strftime('%d/%m/%Y %H:%M')} ──")

        tracking = _load(TRACKING_FILE, [])

        log("Vérification des marchés résolus…")
        tracking = check_resolved(tracking)

        log("Fetch marchés météo actifs…")
        active = fetch_markets(active=True, closed=False)
        log(f"   {len(active)} marchés météo | {len([m for m in active if m['yes_price']>=0.80])} à 80%+")

        log("Mise à jour tracking…")
        tracking = update_tracking(tracking, active)
        _save(TRACKING_FILE, tracking)

        rapport = build_rapport(tracking, active)
        rapports = _load(RAPPORTS_FILE, [])
        rapports.insert(0, rapport)
        _save(RAPPORTS_FILE, rapports[:72])  # 72h max

        log(f"📊 Trackés:{rapport['trackes']} | Résolus:{rapport['resolus']} | "
            f"✅{rapport['gagnes']} ❌{rapport['perdus']} | {rapport['verdict']}")

        # ── Résumé quotidien à 17h + reset du tracking ──
        aujourd_hui = now.strftime("%d/%m/%Y")
        if now.hour == 17 and derniere_date_resume != aujourd_hui:
            log("⏰ 17h00 — Génération du résumé quotidien…")
            save_resume(tracking, rapport["taux_victoire"])
            derniere_date_resume = aujourd_hui
            # Reset du tracking pour repartir propre le lendemain
            _save(TRACKING_FILE, [])
            tracking = []
            log("🔄 Tracking remis à zéro — nouveau cycle commence demain")

        # Calcule le prochain réveil — se cale sur 17h si proche
        prochain_17h = next_17h()
        secs_17h = (prochain_17h - now).total_seconds()
        next_cycle = min(INTERVAL, int(secs_17h)) if secs_17h < INTERVAL else INTERVAL
        next_cycle = max(60, next_cycle)

        log(f"   Prochain cycle dans {next_cycle//60} min | Prochain résumé à {prochain_17h.strftime('%d/%m %H:%M')}")
        log("")
        time.sleep(next_cycle)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run()
