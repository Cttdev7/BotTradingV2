"""
agent_meteo_cloud.py — Agent météo Polymarket (version GitHub Actions + Supabase)
S'exécute toutes les 30 min via GitHub Actions.
Stocke les données dans Supabase au lieu de fichiers JSON.
"""

import os, datetime, requests
from supabase import create_client

GAMMA_API = "https://gamma-api.polymarket.com"
TIMEOUT   = 15

METEO_KEYWORDS = [
    "weather", "temperature", "rain", "snow", "hurricane", "storm",
    "celsius", "fahrenheit", "precipitation", "wind", "heat", "cold",
    "flood", "drought", "cyclone", "tornado", "blizzard", "frost",
    "hail", "thunder", "météo", "pluie", "neige", "tempête",
]

# ── Supabase ──────────────────────────────────────────────────────────────────

def get_db():
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)

# ── Fetch Polymarket ──────────────────────────────────────────────────────────

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
        return [p for m in raw if (p := _parse_market(m)) and
                any(kw in p["question"].lower() for kw in METEO_KEYWORDS)]
    except Exception as e:
        print(f"⚠️  Fetch erreur: {e}")
        return []

# ── Tracking Supabase ─────────────────────────────────────────────────────────

def load_tracking(db):
    res = db.table("meteo_tracking").select("*").execute()
    return res.data or []

def add_tracking(db, market):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    db.table("meteo_tracking").insert({
        "condition_id":       market["condition_id"],
        "question":           market["question"],
        "yes_price_au_track": round(market["yes_price"] * 100, 1),
        "volume":             round(market["volume"], 0),
        "tracke_le":          now,
        "resultat":           None,
        "resolu_le":          None,
    }).execute()
    print(f"  📌 {market['question'][:65]} ({market['yes_price']*100:.0f}%)")

def update_resolved(db, condition_id, resultat):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    db.table("meteo_tracking").update({
        "resultat":   resultat,
        "resolu_le":  now,
    }).eq("condition_id", condition_id).execute()

def reset_tracking(db):
    db.table("meteo_tracking").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print("🔄 Tracking remis à zéro")

# ── Vérification des résultats ────────────────────────────────────────────────

def check_resolved(db, tracking):
    closed = fetch_markets(active=False, closed=True)
    ids = {m["condition_id"]: m for m in closed}
    for t in tracking:
        if t["resultat"] is not None:
            continue
        m = ids.get(t["condition_id"])
        if not m:
            continue
        if m["yes_price"] >= 0.99:
            update_resolved(db, t["condition_id"], "GAGNE")
            print(f"  ✅ GAGNÉ : {t['question'][:55]}")
        elif m["yes_price"] <= 0.01:
            update_resolved(db, t["condition_id"], "PERDU")
            print(f"  ❌ PERDU : {t['question'][:55]}")

# ── Rapport ───────────────────────────────────────────────────────────────────

def load_historique(db, limit=6):
    """Charge les 6 derniers rapports pour que Mistral apprenne."""
    res = db.table("meteo_rapports").select("heure,taux_victoire,analyse_mistral,strategie_proposee").order("created_at", desc=True).limit(limit).execute()
    return res.data or []

def save_rapport(db, tracking, active):
    resolus  = [t for t in tracking if t["resultat"] is not None]
    gagnes   = [t for t in resolus  if t["resultat"] == "GAGNE"]
    perdus   = [t for t in resolus  if t["resultat"] == "PERDU"]
    taux     = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    actifs80 = [{"question": m["question"][:70], "pct": round(m["yes_price"]*100,1)}
                for m in active if m["yes_price"] >= 0.80]
    verdict  = (
        "✅ Stratégie rentable"     if taux and taux >= 60 else
        "⚠️ Stratégie à surveiller" if taux and taux >= 50 else
        "❌ Stratégie non rentable" if taux else
        "⏳ En attente de données"
    )
    historique = load_historique(db)
    analyse, strategie = generate_resume(tracking, taux, historique)
    db.table("meteo_rapports").insert({
        "heure":             datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "trackes":           len(tracking),
        "en_attente":        len(tracking) - len(resolus),
        "resolus":           len(resolus),
        "gagnes":            len(gagnes),
        "perdus":            len(perdus),
        "taux_victoire":     taux,
        "actifs_85":         actifs80,
        "verdict":           verdict,
        "analyse_mistral":   analyse,
        "strategie_proposee": strategie,
    }).execute()
    print(f"📊 Trackés:{len(tracking)} | ✅{len(gagnes)} ❌{len(perdus)} | {verdict}")
    return taux

def generate_resume(tracking, taux, historique):
    key = os.getenv("MISTRAL_API_KEY", "")
    if not key:
        return "MISTRAL_API_KEY manquante.", ""
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNE"]
    lignes  = "\n".join(
        f"- {t['question'][:70]} | {t['yes_price_au_track']}% | {t['resultat']}"
        for t in resolus[-15:]
    ) or "Aucun marché résolu aujourd'hui."

    hist_txt = "\n".join(
        f"- {h['date']} : {h['taux_victoire']}% réussite | Stratégie appliquée : {(h.get('strategie_proposee') or 'aucune')[:80]}"
        for h in historique
    ) or "Aucun historique disponible."

    prompt = f"""Tu es un agent d'analyse de marchés de prédiction Polymarket spécialisé en météo.
Tu analyses les paris météo trackés à partir de 80% de probabilité YES.

AUJOURD'HUI ({datetime.datetime.now().strftime('%d/%m/%Y')}) :
- Trackés : {len(tracking)} | Résolus : {len(resolus)} | Gagnés : {len(gagnes)} | Perdus : {len(resolus)-len(gagnes)} | Taux : {taux if taux else 'N/A'}%

Détail des marchés résolus :
{lignes}

HISTORIQUE DES 7 DERNIERS JOURS :
{hist_txt}

Réponds en JSON avec exactement cette structure :
{{
  "bilan": "2-3 phrases sur les résultats du jour et la tendance",
  "apprentissage": "Ce que tu as appris par rapport aux jours précédents (1-2 phrases)",
  "strategie": "Stratégie concrète à appliquer demain basée sur l'historique (1-2 phrases)",
  "verdict": "RENTABLE" | "RISQUE" | "NON_RENTABLE" | "INSUFFISANT"
}}"""

    try:
        r = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "mistral-small-latest",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 400, "temperature": 0.2,
                  "response_format": {"type": "json_object"}},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()["choices"][0]["message"]["content"]
        import json as _j
        parsed = _j.loads(data)
        analyse  = f"{parsed.get('bilan','')}\n\n🧠 {parsed.get('apprentissage','')}"
        strategie = parsed.get("strategie", "")
        return analyse, strategie
    except Exception as e:
        return f"Erreur Mistral : {e}", ""

def save_resume(db, tracking, taux):
    historique = load_historique(db)
    analyse, strategie = generate_resume(tracking, taux, historique)
    resolus = [t for t in tracking if t["resultat"] is not None]
    db.table("meteo_resumes").insert({
        "date":               datetime.datetime.now().strftime("%d/%m/%Y"),
        "heure":              "17:00",
        "trackes":            len(tracking),
        "resolus":            len(resolus),
        "gagnes":             len([t for t in resolus if t["resultat"] == "GAGNE"]),
        "perdus":             len([t for t in resolus if t["resultat"] == "PERDU"]),
        "taux_victoire":      taux,
        "analyse_mistral":    analyse,
        "strategie_proposee": strategie,
    }).execute()
    print(f"📋 Résumé quotidien sauvegardé | Stratégie : {strategie[:60]}")

# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    now = datetime.datetime.now()
    print(f"🌦  Agent Météo Cloud — {now.strftime('%d/%m/%Y %H:%M')}")

    db = get_db()

    # 1. Vérifie les marchés résolus
    print("1. Vérification des marchés résolus…")
    tracking = load_tracking(db)
    check_resolved(db, tracking)
    tracking = load_tracking(db)  # recharge après updates

    # 2. Fetch marchés météo actifs
    print("2. Fetch marchés météo actifs…")
    active = fetch_markets(active=True, closed=False)
    print(f"   {len(active)} marchés | {len([m for m in active if m['yes_price']>=0.80])} à 80%+")

    # 3. Tracking des nouveaux marchés à 80%+
    print("3. Mise à jour tracking…")
    tracked_ids = {t["condition_id"] for t in tracking}
    for m in active:
        if m["condition_id"] not in tracked_ids and m["yes_price"] >= 0.80:
            add_tracking(db, m)
    tracking = load_tracking(db)

    # 4. Rapport toutes les 2h avec analyse Mistral
    print("4. Sauvegarde rapport + analyse Mistral…")
    save_rapport(db, tracking, active)

    print("✅ Cycle terminé")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run()
