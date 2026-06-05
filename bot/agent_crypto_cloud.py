"""
agent_crypto_cloud.py — Agent crypto Polymarket (GitHub Actions + Supabase + Google Gemini)
S'exécute toutes les 2h via GitHub Actions.
"""

import os, datetime, requests, json as _json

GAMMA_API = "https://gamma-api.polymarket.com"
TIMEOUT   = 15

CRYPTO_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "crypto", "token", "blockchain",
    "solana", "sol", "binance", "bnb", "xrp", "ripple", "cardano", "ada",
    "dogecoin", "doge", "polygon", "matic", "avalanche", "avax", "chainlink",
    "link", "uniswap", "uni", "litecoin", "ltc", "polkadot", "dot",
    "defi", "nft", "web3", "stablecoin", "usdt", "usdc", "altcoin",
    "halving", "mining", "wallet", "exchange", "coinbase", "kraken",
]

# ── Supabase ──────────────────────────────────────────────────────────────────

def get_db():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# ── Fetch Polymarket ──────────────────────────────────────────────────────────

def _parse_market(m):
    raw_p = m.get("outcomePrices", [])
    raw_o = m.get("outcomes", [])
    prices   = _json.loads(raw_p) if isinstance(raw_p, str) else raw_p
    outcomes = _json.loads(raw_o) if isinstance(raw_o, str) else raw_o
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
                any(kw in p["question"].lower() for kw in CRYPTO_KEYWORDS)]
    except Exception as e:
        print(f"⚠️  Fetch erreur: {e}")
        return []

# ── Stats globales (jamais supprimées) ───────────────────────────────────────

def increment_global_stats(db, resultat):
    """Met à jour le compteur cumulé all-time à chaque résolution."""
    res = db.table("crypto_stats").select("*").eq("id", "crypto").execute()
    current = res.data[0] if res.data else {"total_resolus": 0, "total_gagnes": 0, "total_perdus": 0}
    total_resolus = (current.get("total_resolus") or 0) + 1
    total_gagnes  = (current.get("total_gagnes")  or 0) + (1 if resultat == "GAGNE" else 0)
    total_perdus  = (current.get("total_perdus")  or 0) + (1 if resultat == "PERDU" else 0)
    taux = round(total_gagnes / total_resolus * 100, 1) if total_resolus > 0 else None
    db.table("crypto_stats").upsert({
        "id":                   "crypto",
        "total_resolus":        total_resolus,
        "total_gagnes":         total_gagnes,
        "total_perdus":         total_perdus,
        "taux_victoire_global": taux,
        "updated_at":           datetime.datetime.now().isoformat(),
    }).execute()

# ── Tracking Supabase ─────────────────────────────────────────────────────────

def load_tracking(db):
    return db.table("crypto_tracking").select("*").execute().data or []

def add_tracking(db, market):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    db.table("crypto_tracking").insert({
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
    db.table("crypto_tracking").update({
        "resultat":  resultat,
        "resolu_le": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
    }).eq("condition_id", condition_id).execute()
    increment_global_stats(db, resultat)

def check_resolved(db, tracking):
    """Vérifie les marchés résolus. Retourne le nombre de nouvelles résolutions."""
    closed = fetch_markets(active=False, closed=True)
    ids = {m["condition_id"]: m for m in closed}
    count = 0
    for t in tracking:
        if t["resultat"] is not None:
            continue
        m = ids.get(t["condition_id"])
        if not m:
            continue
        if m["yes_price"] >= 0.99:
            update_resolved(db, t["condition_id"], "GAGNE")
            print(f"  ✅ GAGNÉ : {t['question'][:55]}")
            count += 1
        elif m["yes_price"] <= 0.01:
            update_resolved(db, t["condition_id"], "PERDU")
            print(f"  ❌ PERDU : {t['question'][:55]}")
            count += 1
    return count

# ── Nettoyage des données > 4 jours ──────────────────────────────────────────

def cleanup_old_data(db):
    """Supprime tracking et rapports de plus de 4 jours. Les stats globales sont préservées."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=4)).isoformat()
    db.table("crypto_tracking").delete().lt("created_at", cutoff).execute()
    db.table("crypto_rapports").delete().lt("created_at", cutoff).execute()
    print("🗑️  Données >4 jours supprimées")

# ── Analyse Google Gemini ─────────────────────────────────────────────────────

def load_historique(db, limit=6):
    res = db.table("crypto_rapports").select("heure,taux_victoire,analyse_gemini,strategie_proposee").order("created_at", desc=True).limit(limit).execute()
    return res.data or []

def generate_analyse(tracking, taux, historique):
    key = os.getenv("GOOGLE_API_KEY", "")
    if not key:
        return "GOOGLE_API_KEY manquante.", ""
    resolus  = [t for t in tracking if t["resultat"] is not None]
    gagnes   = [t for t in resolus  if t["resultat"] == "GAGNE"]
    lignes   = "\n".join(
        f"- {t['question'][:70]} | {t['yes_price_au_track']}% | {t['resultat']}"
        for t in resolus[-15:]
    ) or "Aucun marché résolu."
    hist_txt = "\n".join(
        f"- {h.get('heure','?')} : {h['taux_victoire']}% | Stratégie : {(h.get('strategie_proposee') or 'aucune')[:80]}"
        for h in historique
    ) or "Aucun historique."
    prompt = f"""Tu es un expert en marchés de prédiction Polymarket spécialisé en crypto.
Tu analyses les paris crypto trackés à partir de 80% de probabilité YES.

RAPPORT ({datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}) :
Trackés: {len(tracking)} | Résolus: {len(resolus)} | Gagnés: {len(gagnes)} | Perdus: {len(resolus)-len(gagnes)} | Taux: {taux if taux else 'N/A'}%

Marchés résolus :
{lignes}

Historique des 6 derniers rapports :
{hist_txt}

Réponds en JSON :
{{
  "bilan": "2-3 phrases sur les résultats et la tendance crypto",
  "apprentissage": "Ce que tu retiens par rapport aux rapports précédents (1-2 phrases)",
  "strategie": "Stratégie concrète pour le prochain cycle basée sur l'historique (1-2 phrases)",
  "verdict": "RENTABLE" | "RISQUE" | "NON_RENTABLE" | "INSUFFISANT"
}}"""
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400,
                                       "responseMimeType": "application/json"}},
            timeout=30,
        )
        r.raise_for_status()
        raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        parsed = _json.loads(raw)
        analyse   = f"{parsed.get('bilan','')}\n\n🧠 {parsed.get('apprentissage','')}"
        strategie = parsed.get("strategie", "")
        return analyse, strategie
    except Exception as e:
        return f"Erreur Google Gemini : {e}", ""

def save_rapport(db, tracking, active):
    resolus  = [t for t in tracking if t["resultat"] is not None]
    gagnes   = [t for t in resolus  if t["resultat"] == "GAGNE"]
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
    analyse, strategie = generate_analyse(tracking, taux, historique)
    db.table("crypto_rapports").insert({
        "heure":              datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "trackes":            len(tracking),
        "en_attente":         len(tracking) - len(resolus),
        "resolus":            len(resolus),
        "gagnes":             len(gagnes),
        "perdus":             len(resolus) - len(gagnes),
        "taux_victoire":      taux,
        "actifs_80":          actifs80,
        "verdict":            verdict,
        "analyse_gemini":     analyse,
        "strategie_proposee": strategie,
    }).execute()
    print(f"📊 Trackés:{len(tracking)} | ✅{len(gagnes)} ❌{len(resolus)-len(gagnes)} | {verdict}")
    return taux

def save_resume(db, tracking, taux):
    historique = load_historique(db)
    analyse, strategie = generate_analyse(tracking, taux, historique)
    resolus = [t for t in tracking if t["resultat"] is not None]
    db.table("crypto_resumes").insert({
        "date":               datetime.datetime.now().strftime("%d/%m/%Y"),
        "heure":              "17:00",
        "trackes":            len(tracking),
        "resolus":            len(resolus),
        "gagnes":             len([t for t in resolus if t["resultat"] == "GAGNE"]),
        "perdus":             len([t for t in resolus if t["resultat"] == "PERDU"]),
        "taux_victoire":      taux,
        "analyse_gemini":     analyse,
        "strategie_proposee": strategie,
    }).execute()
    print(f"📋 Résumé quotidien sauvegardé | Stratégie : {strategie[:60]}")

# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    now = datetime.datetime.now()
    print(f"₿  Agent Crypto Cloud — {now.strftime('%d/%m/%Y %H:%M')}")

    db = get_db()

    # 1. Nettoyage des données > 4 jours
    print("1. Nettoyage des données >4 jours…")
    cleanup_old_data(db)

    # 2. Vérifie les marchés résolus
    print("2. Vérification des marchés résolus…")
    tracking = load_tracking(db)
    new_resolved = check_resolved(db, tracking)
    tracking = load_tracking(db)

    # 3. Fetch marchés crypto actifs
    print("3. Fetch marchés crypto actifs…")
    active = fetch_markets(active=True, closed=False)
    print(f"   {len(active)} marchés | {len([m for m in active if m['yes_price']>=0.80])} à 80%+")

    # 4. Tracking des nouveaux marchés à 80%+
    print("4. Mise à jour tracking…")
    tracked_ids = {t["condition_id"] for t in tracking}
    new_tracked = 0
    for m in active:
        if m["condition_id"] not in tracked_ids and m["yes_price"] >= 0.80:
            add_tracking(db, m)
            new_tracked += 1
    tracking = load_tracking(db)

    # 5. Rapport Gemini uniquement si des changements ont eu lieu
    taux = None
    if new_resolved > 0 or new_tracked > 0:
        print(f"5. Rapport Gemini ({new_resolved} résolus, {new_tracked} nouveaux)…")
        taux = save_rapport(db, tracking, active)
    else:
        print("5. Aucun changement — rapport Gemini ignoré")

    # 6. Résumé quotidien à 17h
    if now.hour == 17 and now.minute < 30:
        print("6. Résumé quotidien 17h…")
        save_resume(db, tracking, taux)

    print("✅ Cycle terminé")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run()
