"""
agent_crypto_4h_cloud.py — Agent crypto 4H Polymarket (GitHub Actions + Supabase + Google Gemini)
Tracke les paris crypto de polymarket.com/crypto/4hour (YES ≥ 80%, résolution dans 1.5h-6h).
S'exécute toutes les heures via GitHub Actions.
"""

import os, datetime, requests, json as _json

GAMMA_API = "https://gamma-api.polymarket.com"
TIMEOUT   = 15

CRYPTO_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp", "ripple",
    "cardano", "ada", "dogecoin", "doge", "bnb", "binance", "avalanche", "avax",
    "chainlink", "link", "polkadot", "dot", "litecoin", "ltc", "crypto",
]

# ── Supabase ──────────────────────────────────────────────────────────────────

def get_db():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"])

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
        "end_date":     m.get("endDate", ""),
        "uma_status":   m.get("umaResolutionStatus"),
    }

def _is_4h_market(market):
    """Vrai si le marché se résout entre 1.5h et 6h (fenêtre 4h)."""
    end_str = market.get("end_date", "")
    if not end_str:
        return False
    try:
        end = datetime.datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        return now + datetime.timedelta(hours=1, minutes=30) < end <= now + datetime.timedelta(hours=6)
    except:
        return False

def fetch_4h_markets(limit=500):
    """Fetch les marchés crypto actifs qui se résolvent dans 1.5h à 6h."""
    try:
        params = {"limit": limit, "order": "volume", "ascending": "false",
                  "active": "true", "closed": "false"}
        r = requests.get(f"{GAMMA_API}/markets", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        raw = r.json()
        if not isinstance(raw, list):
            return []
        result = []
        for m in raw:
            p = _parse_market(m)
            if not p:
                continue
            if not any(kw in p["question"].lower() for kw in CRYPTO_KEYWORDS):
                continue
            if not _is_4h_market(p):
                continue
            result.append(p)
        return result
    except Exception as e:
        print(f"⚠️  Fetch erreur: {e}")
        return []

def fetch_market_by_id(condition_id):
    """Fetch un marché directement par condition_id.

    Le paramètre 'conditionId' (singulier) de l'API gamma est ignoré silencieusement
    (renvoie une page de marchés sans rapport) — le bon paramètre est 'condition_ids'
    (pluriel), qui en plus ne renvoie que les marchés actifs par défaut : il faut
    retenter avec closed=true si le marché est déjà fermé.
    """
    try:
        r = requests.get(f"{GAMMA_API}/markets",
                        params={"condition_ids": condition_id},
                        timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if not data:
            r = requests.get(f"{GAMMA_API}/markets",
                            params={"condition_ids": condition_id, "closed": "true"},
                            timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
        if isinstance(data, list) and data:
            m = data[0]
            if m.get("conditionId", "").lower() != condition_id.lower():
                return None
            return _parse_market(m)
    except Exception as e:
        print(f"⚠️  Fetch {condition_id[:16]}: {e}")
    return None

# ── Stats globales (jamais supprimées) ───────────────────────────────────────

def increment_global_stats(db, resultat):
    res = db.table("crypto_4h_stats").select("*").eq("id", "crypto_4h").execute()
    current = res.data[0] if res.data else {"total_resolus": 0, "total_gagnes": 0, "total_perdus": 0}
    total_resolus = (current.get("total_resolus") or 0) + 1
    total_gagnes  = (current.get("total_gagnes")  or 0) + (1 if resultat == "GAGNE" else 0)
    total_perdus  = (current.get("total_perdus")  or 0) + (1 if resultat == "PERDU" else 0)
    taux = round(total_gagnes / total_resolus * 100, 1) if total_resolus > 0 else None
    db.table("crypto_4h_stats").upsert({
        "id":                   "crypto_4h",
        "total_resolus":        total_resolus,
        "total_gagnes":         total_gagnes,
        "total_perdus":         total_perdus,
        "taux_victoire_global": taux,
        "updated_at":           datetime.datetime.now().isoformat(),
    }).execute()

# ── Tracking Supabase ─────────────────────────────────────────────────────────

def load_tracking(db):
    return db.table("crypto_4h_tracking").select("*").execute().data or []

def add_tracking(db, market):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    db.table("crypto_4h_tracking").insert({
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
    db.table("crypto_4h_tracking").update({
        "resultat":  resultat,
        "resolu_le": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
    }).eq("condition_id", condition_id).execute()
    increment_global_stats(db, resultat)

def check_resolved(db, tracking):
    """Vérifie chaque marché tracké directement par son ID."""
    pending = [t for t in tracking if t["resultat"] is None]
    if not pending:
        return 0
    count = 0
    for t in pending:
        m = fetch_market_by_id(t["condition_id"])
        if not m:
            continue
        # N'exige pas juste un prix extrême : le marché doit être réellement et
        # définitivement résolu (closed + umaResolutionStatus), sinon un prix qui
        # touche 0.99/0.01 momentanément pourrait revenir en arrière (litige UMA).
        if not (m["closed"] and m.get("uma_status") == "resolved"):
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
    """Supprime tracking et rapports >4 jours. Stats préservées."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=4)).isoformat()
    db.table("crypto_4h_tracking").delete().lt("created_at", cutoff).execute()
    db.table("crypto_4h_rapports").delete().lt("created_at", cutoff).execute()
    print("🗑️  Données >4 jours supprimées")

# ── Analyse Google Gemini ─────────────────────────────────────────────────────

def load_historique(db, limit=6):
    res = db.table("crypto_4h_rapports").select("heure,taux_victoire,analyse_gemini,strategie_proposee").order("created_at", desc=True).limit(limit).execute()
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
    prompt = f"""Tu es un expert en marchés de prédiction Polymarket spécialisé en crypto 4 heures.
Tu analyses les paris crypto à résolution 4H trackés à partir de 80% de probabilité YES.
Ces marchés se résolvent toutes les 4 heures (ex: "Will BTC be above $X at 4:00 PM?").

RAPPORT ({datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}) :
Trackés: {len(tracking)} | Résolus: {len(resolus)} | Gagnés: {len(gagnes)} | Perdus: {len(resolus)-len(gagnes)} | Taux: {taux if taux else 'N/A'}%

Marchés résolus :
{lignes}

Historique des 6 derniers rapports :
{hist_txt}

Réponds en JSON :
{{
  "bilan": "2-3 phrases sur les résultats et la tendance crypto sur les cycles 4H",
  "apprentissage": "Ce que tu retiens pour mieux sélectionner les paris 4H (1-2 phrases)",
  "strategie": "Stratégie adaptative pour le prochain cycle 4H basée sur l'historique (1-2 phrases)",
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
    db.table("crypto_4h_rapports").insert({
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
    db.table("crypto_4h_resumes").insert({
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
    print(f"📋 Résumé quotidien sauvegardé")

# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    now = datetime.datetime.now()
    print(f"⏱  Agent Crypto 4H Cloud — {now.strftime('%d/%m/%Y %H:%M')}")

    db = get_db()

    # 1. Nettoyage
    print("1. Nettoyage des données >4 jours…")
    cleanup_old_data(db)

    # 2. Vérifie les marchés résolus
    print("2. Vérification des marchés résolus…")
    tracking = load_tracking(db)
    new_resolved = check_resolved(db, tracking)
    tracking = load_tracking(db)

    # 3. Fetch marchés crypto 4H actifs
    print("3. Fetch marchés crypto 4H (YES ≥ 80%, résolution dans 1.5h-6h)…")
    active = fetch_4h_markets()
    print(f"   {len(active)} marchés 4H | {len([m for m in active if m['yes_price']>=0.80])} à 80%+")

    # 4. Tracking des nouveaux marchés à 80%+
    print("4. Mise à jour tracking…")
    tracked_ids = {t["condition_id"] for t in tracking}
    new_tracked = 0
    for m in active:
        if m["condition_id"] not in tracked_ids and m["yes_price"] >= 0.80:
            add_tracking(db, m)
            new_tracked += 1
    tracking = load_tracking(db)

    # 5. Rapport Gemini à chaque cycle
    print(f"5. Rapport Gemini ({new_resolved} résolus, {new_tracked} nouveaux)…")
    taux = save_rapport(db, tracking, active)

    # 6. Résumé quotidien à 17h
    if now.hour == 17 and now.minute < 60:
        print("6. Résumé quotidien 17h…")
        save_resume(db, tracking, taux)

    print("✅ Cycle terminé")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run()
