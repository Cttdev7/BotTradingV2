"""
agent_crypto_cloud.py — Agent crypto Polymarket (GitHub Actions + Supabase + Google Gemini)
S'exécute toutes les 2h via GitHub Actions.
Tracke les marchés crypto à 80%+ et analyse avec Google Gemini.
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

# ── Analyse Google Gemini ─────────────────────────────────────────────────────

def load_historique(db, limit=6):
    res = db.table("crypto_rapports").select("heure,taux_victoire,analyse_gemini,strategie_proposee").order("created_at", desc=True).limit(limit).execute()
    return res.data or []

def generate_analyse(tracking, taux, historique):
    key = os.getenv("GOOGLE_API_KEY", "")
    if not key:
        return "GOOGLE_API_KEY manquante.", ""

    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNE"]
    lignes  = "\n".join(
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

# ── Rapport ───────────────────────────────────────────────────────────────────

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
        "heure":             datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "trackes":           len(tracking),
        "en_attente":        len(tracking) - len(resolus),
        "resolus":           len(resolus),
        "gagnes":            len(gagnes),
        "perdus":            len(resolus) - len(gagnes),
        "taux_victoire":     taux,
        "actifs_80":         actifs80,
        "verdict":           verdict,
        "analyse_gemini":    analyse,
        "strategie_proposee": strategie,
    }).execute()
    print(f"📊 Trackés:{len(tracking)} | ✅{len(gagnes)} ❌{len(resolus)-len(gagnes)} | {verdict}")

# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    now = datetime.datetime.now()
    print(f"₿  Agent Crypto Cloud — {now.strftime('%d/%m/%Y %H:%M')}")

    db = get_db()

    print("1. Vérification des marchés résolus…")
    tracking = load_tracking(db)
    check_resolved(db, tracking)
    tracking = load_tracking(db)

    print("2. Fetch marchés crypto actifs…")
    active = fetch_markets(active=True, closed=False)
    print(f"   {len(active)} marchés | {len([m for m in active if m['yes_price']>=0.80])} à 80%+")

    print("3. Mise à jour tracking…")
    tracked_ids = {t["condition_id"] for t in tracking}
    for m in active:
        if m["condition_id"] not in tracked_ids and m["yes_price"] >= 0.80:
            add_tracking(db, m)
    tracking = load_tracking(db)

    print("4. Rapport + analyse Google Gemini…")
    save_rapport(db, tracking, active)

    print("✅ Cycle terminé")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run()
