"""
agent_chengdu_cloud.py — Bot Chengdu température maximale (Railway + Supabase)
Tourne en continu sur Railway. Toutes les 15 minutes :
- Analyse les 11 options de température du lendemain à Chengdu
- Enregistre les signaux >80% dans Supabase
- Vérifie les résolutions des marchés précédents
- Met à jour les stats globales
"""

import os, json, time, datetime, requests
from supabase import create_client

GAMMA_API = "https://gamma-api.polymarket.com"
TIMEOUT   = 15
INTERVAL  = 900  # 15 min

MONTHS = ["january","february","march","april","may","june",
          "july","august","september","october","november","december"]

# ── Supabase ──────────────────────────────────────────────────────────────────

def get_db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%d/%m %H:%M')}] {msg}", flush=True)

# ── Slug & Fetch ──────────────────────────────────────────────────────────────

def slug_for(date):
    return f"highest-temperature-in-chengdu-on-{MONTHS[date.month-1]}-{date.day}-{date.year}"

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

def fetch_market_by_id(condition_id):
    """Relit un marché spécifique par son condition_id."""
    try:
        r = requests.get(f"{GAMMA_API}/markets",
                         params={"conditionId": condition_id},
                         timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            m = data[0]
            raw_p = m.get("outcomePrices", [])
            raw_o = m.get("outcomes", [])
            prices   = json.loads(raw_p) if isinstance(raw_p, str) else raw_p
            outcomes = json.loads(raw_o) if isinstance(raw_o, str) else raw_o
            if not prices or not outcomes:
                return None
            yes_price = next((float(p) for o, p in zip(outcomes, prices) if o.lower() == "yes"), None)
            if yes_price is None:
                return None
            return {
                "condition_id": m.get("conditionId", ""),
                "yes_price":    yes_price,
                "closed":       m.get("closed", False),
            }
    except Exception as e:
        log(f"⚠️  Fetch {condition_id[:16]}: {e}")
    return None

# ── Tracking Supabase ─────────────────────────────────────────────────────────

def load_tracking(db):
    res = db.table("chengdu_tracking").select("*").execute()
    return res.data or []

def add_signal(db, market, date_str):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    pct = round(market["yes_price"] * 100, 1)
    db.table("chengdu_tracking").upsert({
        "condition_id":        market["condition_id"],
        "question":            market["question"],
        "yes_price_au_signal": pct,
        "yes_price_actuel":    pct,
        "volume":              round(market["volume"], 0),
        "detecte_le":          now,
        "date_marche":         date_str,
        "resultat":            None,
        "resolu_le":           None,
    }, on_conflict="condition_id", ignore_duplicates=True).execute()
    log(f"  🎯 SIGNAL: {market['question'][:60]} ({pct}%)")

def update_price(db, condition_id, yes_price):
    db.table("chengdu_tracking").update({
        "yes_price_actuel":  round(yes_price * 100, 1),
        "derniere_lecture":  datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
    }).eq("condition_id", condition_id).execute()

def resolve_signal(db, condition_id, resultat):
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    db.table("chengdu_tracking").update({
        "resultat":  resultat,
        "resolu_le": now,
    }).eq("condition_id", condition_id).execute()
    icon = "✅" if resultat == "GAGNANT" else "❌" if resultat == "PERDANT" else "🔚"
    log(f"  {icon} {resultat}")

# ── Stats globales ────────────────────────────────────────────────────────────

def update_stats(db, tracking):
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None

    # Stats par date
    by_date = {}
    for t in tracking:
        d = t["date_marche"]
        if d not in by_date:
            by_date[d] = {"signaux": 0, "gagnes": 0, "perdus": 0, "en_attente": 0}
        by_date[d]["signaux"] += 1
        if t["resultat"] == "GAGNANT":
            by_date[d]["gagnes"] += 1
        elif t["resultat"] == "PERDANT":
            by_date[d]["perdus"] += 1
        else:
            by_date[d]["en_attente"] += 1

    db.table("chengdu_stats").upsert({
        "id":              "chengdu",
        "total_signaux":   len(tracking),
        "en_attente":      len(tracking) - len(resolus),
        "resolus":         len(resolus),
        "gagnes":          len(gagnes),
        "perdus":          len(perdus),
        "taux_victoire":   taux,
        "par_date":        by_date,
        "updated_at":      datetime.datetime.now().isoformat(),
        "verdict": (
            "Stratégie rentable"      if taux is not None and taux >= 60 else
            "Stratégie à surveiller"  if taux is not None and taux >= 50 else
            "Stratégie non rentable"  if taux is not None else
            "En attente de données"
        ),
    }).execute()

# ── Résolution des marchés en attente ─────────────────────────────────────────

def check_resolved(db, tracking):
    pending = [t for t in tracking if t["resultat"] is None]
    if not pending:
        return
    for t in pending:
        m = fetch_market_by_id(t["condition_id"])
        if m is None or m["closed"]:
            final = m["yes_price"] if m else None
            if final is not None and final >= 0.95:
                resultat = "GAGNANT"
            elif final is not None and final <= 0.05:
                resultat = "PERDANT"
            else:
                pct = t.get("yes_price_actuel") or t.get("yes_price_au_signal") or 0
                resultat = f"TERMINÉ: {pct}%"
            resolve_signal(db, t["condition_id"], resultat)
        elif m:
            update_price(db, t["condition_id"], m["yes_price"])

# ── Rapport cycle + Résumé 17h ───────────────────────────────────────────────

def save_rapport(db, tracking, slug):
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    db.table("chengdu_rapports").insert({
        "heure":        datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "trackes":      len(tracking),
        "en_attente":   len(tracking) - len(resolus),
        "resolus":      len(resolus),
        "gagnes":       len(gagnes),
        "perdus":       len(perdus),
        "taux_victoire": taux,
        "marche_slug":  slug,
        "verdict": (
            "Stratégie rentable"      if taux is not None and taux >= 60 else
            "Stratégie à surveiller"  if taux is not None and taux >= 50 else
            "Stratégie non rentable"  if taux is not None else
            "En attente de données"
        ),
    }).execute()

def generate_daily_resume(tracking):
    key = os.getenv("MISTRAL_API_KEY", "")
    if not key:
        return "MISTRAL_API_KEY manquante."
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    lignes  = "\n".join(
        f"- {t['question'][:70]} | signalé à {t['yes_price_au_signal']}% | {t['resultat']}"
        for t in resolus[-15:]
    ) or "Aucun marché résolu."
    prompt = f"""Résume en 5 lignes max ces stats de paris sur la température à Chengdu (Polymarket, seuil 80%) :

Signaux: {len(tracking)} | Résolus: {len(resolus)} | Gagnés: {len(gagnes)} | Perdus: {len(resolus)-len(gagnes)} | Taux: {taux}%

Derniers résolus:
{lignes}

Réponds en français, très court. Donne :
1. Le taux de réussite
2. Si la stratégie vaut le coup (oui/non, 1 phrase)
3. Un conseil pour demain"""
    try:
        r = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "mistral-small-latest",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 200, "temperature": 0.2},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Erreur Mistral : {e}"

def save_resume(db, tracking):
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    analyse = generate_daily_resume(tracking)
    db.table("chengdu_resumes").insert({
        "date":          datetime.datetime.now().strftime("%d/%m/%Y"),
        "trackes":       len(tracking),
        "resolus":       len(resolus),
        "gagnes":        len(gagnes),
        "perdus":        len(perdus),
        "taux_victoire": taux,
        "analyse":       analyse,
    }).execute()
    log(f"📋 Résumé 17h sauvegardé — taux: {taux}%")

# ── Boucle principale ─────────────────────────────────────────────────────────

def run():
    log("🌡️  Agent Chengdu Cloud démarré (Railway + Supabase)")
    log("   Seuil : 80% YES | Scan : toutes les 15 min")
    log("")

    db = get_db()

    while True:
        now      = datetime.datetime.now()
        target   = now + datetime.timedelta(days=1)
        slug     = slug_for(target)
        date_str = target.strftime("%d/%m/%Y")

        log(f"── Cycle {now.strftime('%d/%m/%Y %H:%M')} ──")
        log(f"   Marché suivi : {slug}")

        # 1. Vérifier résolutions des marchés en attente
        log("Vérification des marchés résolus…")
        tracking = load_tracking(db)
        check_resolved(db, tracking)
        tracking = load_tracking(db)

        # 2. Fetch marché Chengdu du lendemain
        log("Fetch marché Chengdu…")
        event, markets = fetch_event(slug)

        if not markets:
            log("   ⚠️  Aucun marché trouvé")
        else:
            top = sorted(markets, key=lambda x: x["yes_price"], reverse=True)
            log(f"   {len(markets)} options | Top: {top[0]['question'].split('be ')[-1].split(' on')[0]} à {top[0]['yes_price']*100:.0f}%")

            for m in sorted(markets, key=lambda x: x["yes_price"], reverse=True):
                flag = "🔥" if m["yes_price"] >= 0.80 else ("📊" if m["yes_price"] >= 0.30 else "  ")
                temp = m["question"].split("be ")[-1].split(" on")[0]
                log(f"   {flag} {m['yes_price']*100:5.1f}%  {temp}")

            # 3. Enregistrer les signaux >80%
            tracked_ids = {t["condition_id"] for t in tracking}
            new_signals = 0
            for m in markets:
                if m["condition_id"] not in tracked_ids and m["yes_price"] >= 0.80:
                    add_signal(db, m, date_str)
                    new_signals += 1

            if new_signals:
                log(f"   🎯 {new_signals} nouveau(x) signal(s) !")
            else:
                log("   Aucun nouveau signal (aucune option à 80%+)")

        # 4. Mise à jour stats
        tracking = load_tracking(db)
        update_stats(db, tracking)

        resolus = [t for t in tracking if t["resultat"] is not None]
        gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
        perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]
        taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
        log(f"📊 Signaux:{len(tracking)} | Résolus:{len(resolus)} | ✅{len(gagnes)} ❌{len(perdus)} | Taux:{taux}%")

        # 5. Rapport cycle → chengdu_rapports
        try:
            save_rapport(db, tracking, slug)
        except Exception as e:
            log(f"⚠️  Rapport: {e}")

        # 6. Résumé 17h → chengdu_resumes
        if now.hour == 17 and now.minute < 15:
            log("⏰ 17h00 — Génération du résumé quotidien…")
            try:
                save_resume(db, tracking)
            except Exception as e:
                log(f"⚠️  Résumé: {e}")

        log(f"   Prochain cycle dans 15 min")
        log("")

        time.sleep(INTERVAL)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run()
