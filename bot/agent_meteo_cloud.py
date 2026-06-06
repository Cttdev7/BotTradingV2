"""
agent_meteo_cloud.py — Agent météo Polymarket (version GitHub Actions + Supabase)
S'exécute toutes les 30 min via GitHub Actions.
"""

import os, datetime, requests
from supabase import create_client

GAMMA_API      = "https://gamma-api.polymarket.com"
POLYGON_RPC    = "https://polygon-bor-rpc.publicnode.com"
USDC_CONTRACT  = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
USDCE_CONTRACT = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
TIMEOUT        = 15

GAMMA_EVENTS_API = "https://gamma-api.polymarket.com/events"

# ── Supabase ──────────────────────────────────────────────────────────────────

def get_db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# ── Wallet Polygon ────────────────────────────────────────────────────────────

def fetch_wallet_balance():
    wallet = os.environ.get("WALLET_ADDRESS", "")
    if not wallet:
        return None
    data = "0x70a08231" + wallet[2:].lower().zfill(64)
    def rpc(method, params, rid=1):
        r = requests.post(POLYGON_RPC,
            json={"jsonrpc": "2.0", "method": method, "params": params, "id": rid},
            timeout=10)
        return r.json().get("result", "0x0")
    try:
        pol_hex   = rpc("eth_getBalance",  [wallet, "latest"], 1)
        usdc_hex  = rpc("eth_call", [{"to": USDC_CONTRACT,  "data": data}, "latest"], 2)
        usdce_hex = rpc("eth_call", [{"to": USDCE_CONTRACT, "data": data}, "latest"], 3)
        return {
            "pol":    round(int(pol_hex,   16) / 1e18, 4),
            "usdc":   round(int(usdc_hex,  16) / 1e6,  2),
            "usdce":  round(int(usdce_hex, 16) / 1e6,  2),
            "wallet": wallet,
        }
    except Exception as e:
        print(f"⚠️  Wallet erreur: {e}")
        return None

def save_bot_status(db, wallet):
    if not wallet:
        return
    db.table("bot_status").upsert({
        "id":         "polyedge",
        "wallet":     wallet.get("wallet", ""),
        "usdc":       wallet.get("usdc", 0),
        "usdce":      wallet.get("usdce", 0),
        "pol":        wallet.get("pol", 0),
        "updated_at": datetime.datetime.now().isoformat(),
    }).execute()
    total = wallet.get("usdc", 0) + wallet.get("usdce", 0)
    print(f"💰 Wallet: {total:.2f} USDC | {wallet.get('pol', 0)} POL")

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

def fetch_high_temp_markets():
    """Fetch les marchés 'highest temperature' actifs se résolvant dans les 7 prochains jours."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now + datetime.timedelta(days=7)
        result = []
        r = requests.get(GAMMA_EVENTS_API,
            params={"tag_slug": "weather", "limit": 100, "active": "true",
                    "order": "createdAt", "ascending": "false"},
            timeout=TIMEOUT)
        r.raise_for_status()
        events = r.json()
        for event in events:
            title = event.get("title", "").lower()
            if "highest temperature" not in title and "high temperature" not in title:
                continue
            for m in event.get("markets", []):
                # Filtre strict : marché actif, non fermé, endDate dans les 7 jours
                if m.get("closed") or not m.get("active", True):
                    continue
                end_str = m.get("endDate", "")
                if end_str:
                    try:
                        end = datetime.datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                        if end < now or end > cutoff:
                            continue
                    except:
                        continue
                parsed = _parse_market(m)
                if parsed:
                    result.append(parsed)
        return result
    except Exception as e:
        print(f"⚠️  Fetch erreur: {e}")
        return []

# ── Stats globales (jamais supprimées) ───────────────────────────────────────

def increment_global_stats(db, last_price_pct):
    """Met à jour le compteur cumulé. Un marché terminé à >50% = prédiction tenue."""
    res = db.table("meteo_stats").select("*").eq("id", "meteo").execute()
    current = res.data[0] if res.data else {"total_resolus": 0, "total_gagnes": 0, "total_perdus": 0}
    total_resolus = (current.get("total_resolus") or 0) + 1
    tenu          = last_price_pct >= 50  # la prédiction a tenu si terminé à 50%+
    total_gagnes  = (current.get("total_gagnes")  or 0) + (1 if tenu else 0)
    total_perdus  = (current.get("total_perdus")  or 0) + (0 if tenu else 1)
    taux = round(total_gagnes / total_resolus * 100, 1) if total_resolus > 0 else None
    db.table("meteo_stats").upsert({
        "id":                   "meteo",
        "total_resolus":        total_resolus,
        "total_gagnes":         total_gagnes,
        "total_perdus":         total_perdus,
        "taux_victoire_global": taux,
        "updated_at":           datetime.datetime.now().isoformat(),
    }).execute()

# ── Tracking Supabase ─────────────────────────────────────────────────────────

def load_tracking(db):
    res = db.table("meteo_tracking").select("*").execute()
    return res.data or []

def add_tracking(db, market):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    pct = round(market["yes_price"] * 100, 1)
    db.table("meteo_tracking").upsert({
        "condition_id":       market["condition_id"],
        "question":           market["question"],
        "yes_price_au_track": pct,
        "yes_price_actuel":   pct,
        "volume":             round(market["volume"], 0),
        "tracke_le":          now,
        "derniere_lecture":   now,
        "resultat":           None,
        "resolu_le":          None,
    }, on_conflict="condition_id", ignore_duplicates=True).execute()
    print(f"  📌 {market['question'][:65]} ({pct}%)")

def update_price(db, condition_id, yes_price_actuel):
    """Met à jour le % actuel du marché tracké."""
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    db.table("meteo_tracking").update({
        "yes_price_actuel":  yes_price_actuel,
        "derniere_lecture":  now,
    }).eq("condition_id", condition_id).execute()

def update_terminated(db, condition_id, last_price_pct):
    """Marque le marché comme terminé avec le dernier % connu."""
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    db.table("meteo_tracking").update({
        "resultat":  f"TERMINÉ: {last_price_pct}%",
        "resolu_le": now,
    }).eq("condition_id", condition_id).execute()
    increment_global_stats(db, last_price_pct)

def fetch_market_by_id(condition_id):
    """Fetch un marché directement par condition_id."""
    try:
        r = requests.get(f"{GAMMA_API}/markets",
                        params={"conditionId": condition_id},
                        timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            return _parse_market(data[0])
    except Exception as e:
        print(f"⚠️  Fetch {condition_id[:16]}: {e}")
    return None

def check_and_update(db, tracking):
    """Relit chaque marché tracké, met à jour le % actuel.
    Si le marché a disparu ou fermé → enregistre le dernier % comme résultat final."""
    pending = [t for t in tracking if t["resultat"] is None]
    if not pending:
        return 0
    count = 0
    for t in pending:
        m = fetch_market_by_id(t["condition_id"])
        last_pct = t.get("yes_price_actuel") or t.get("yes_price_au_track") or 0
        if m is None or m.get("closed"):
            # Marché disparu ou fermé → TERMINÉ avec dernier % connu
            update_terminated(db, t["condition_id"], last_pct)
            print(f"  🔚 TERMINÉ à {last_pct}% : {t['question'][:50]}")
            count += 1
        else:
            # Mise à jour du % actuel
            new_pct = round(m["yes_price"] * 100, 1)
            update_price(db, t["condition_id"], new_pct)
            print(f"  🔄 {new_pct}% : {t['question'][:50]}")
    return count

# ── Nettoyage des données > 4 jours ──────────────────────────────────────────

def cleanup_old_data(db):
    """Supprime tracking et rapports de plus de 4 jours. Les stats globales sont préservées."""
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=4)).isoformat()
    db.table("meteo_tracking").delete().lt("created_at", cutoff).execute()
    db.table("meteo_rapports").delete().lt("created_at", cutoff).execute()
    print("🗑️  Données >4 jours supprimées")

# ── Rapport ───────────────────────────────────────────────────────────────────

def load_historique(db, limit=6):
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
        "heure":              datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "trackes":            len(tracking),
        "en_attente":         len(tracking) - len(resolus),
        "resolus":            len(resolus),
        "gagnes":             len(gagnes),
        "perdus":             len(perdus),
        "taux_victoire":      taux,
        "actifs_85":          actifs80,
        "verdict":            verdict,
        "analyse_mistral":    analyse,
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
    ) or "Aucun marché résolu."
    hist_txt = "\n".join(
        f"- {h.get('heure','?')} : {h['taux_victoire']}% réussite | Stratégie : {(h.get('strategie_proposee') or 'aucune')[:80]}"
        for h in historique
    ) or "Aucun historique disponible."
    prompt = f"""Tu es un agent d'analyse de marchés de prédiction Polymarket spécialisé en météo.
Tu analyses les paris météo trackés à partir de 80% de probabilité YES.

AUJOURD'HUI ({datetime.datetime.now().strftime('%d/%m/%Y')}) :
- Trackés : {len(tracking)} | Résolus : {len(resolus)} | Gagnés : {len(gagnes)} | Perdus : {len(resolus)-len(gagnes)} | Taux : {taux if taux else 'N/A'}%

Détail des marchés résolus :
{lignes}

HISTORIQUE DES 6 DERNIERS RAPPORTS :
{hist_txt}

Réponds en JSON avec exactement cette structure :
{{
  "bilan": "2-3 phrases sur les résultats et la tendance",
  "apprentissage": "Ce que tu as appris par rapport aux rapports précédents (1-2 phrases)",
  "strategie": "Stratégie concrète à appliquer basée sur l'historique (1-2 phrases)",
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
        analyse   = f"{parsed.get('bilan','')}\n\n🧠 {parsed.get('apprentissage','')}"
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

    # 1. Nettoyage des données > 4 jours
    print("1. Nettoyage des données >4 jours…")
    cleanup_old_data(db)

    # 2. Relit et met à jour tous les marchés trackés
    print("2. Mise à jour des marchés trackés…")
    tracking = load_tracking(db)
    new_resolved = check_and_update(db, tracking)
    tracking = load_tracking(db)

    # 3. Fetch marchés high temperature (polymarket.com/weather/high-temperature)
    print("3. Fetch marchés highest temperature…")
    active = fetch_high_temp_markets()
    print(f"   {len(active)} marchés high temp | {len([m for m in active if m['yes_price']>=0.80])} à 80%+")

    # 4. Tracking des nouveaux marchés à 80%+
    print("4. Mise à jour tracking…")
    tracked_ids = {t["condition_id"] for t in tracking}
    new_tracked = 0
    for m in active:
        if m["condition_id"] not in tracked_ids and m["yes_price"] >= 0.80:
            add_tracking(db, m)
            new_tracked += 1
    tracking = load_tracking(db)

    # 5. Rapport Mistral à chaque cycle
    print(f"5. Rapport Mistral ({new_resolved} résolus, {new_tracked} nouveaux)…")
    taux = save_rapport(db, tracking, active)

    # 6. Résumé quotidien à 17h
    if now.hour == 17 and now.minute < 30:
        print("6. Résumé quotidien 17h…")
        save_resume(db, tracking, taux)

    # 7. Mise à jour solde wallet
    print("7. Mise à jour solde wallet…")
    save_bot_status(db, fetch_wallet_balance())

    print("✅ Cycle terminé")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run()
