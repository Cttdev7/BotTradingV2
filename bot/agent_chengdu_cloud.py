"""
agent_chengdu_cloud.py — Bot Chengdu température maximale (Railway + Supabase)
Tourne en continu sur Railway. Toutes les 15 minutes :
- Analyse les 11 options de température du marché actif (avant 14h→aujourd'hui, après 14h→demain)
- Enregistre les signaux >80% dans Supabase
- Vérifie les résolutions des marchés précédents
- Met à jour les stats globales
"""

import os, json, time, datetime, requests
from zoneinfo import ZoneInfo
from supabase import create_client

PARIS = ZoneInfo("Europe/Paris")

def now_paris():
    return datetime.datetime.now(PARIS)

GAMMA_API          = "https://gamma-api.polymarket.com"
TIMEOUT            = 15
INTERVAL           = 900   # 15 min
MARKET_CLOSE_HOUR  = 14    # marchés Chengdu ferment à 12h UTC = 14h Paris

MONTHS = ["january","february","march","april","may","june",
          "july","august","september","october","november","december"]

# ── Supabase ──────────────────────────────────────────────────────────────────

def get_db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def log(msg):
    print(f"[{now_paris().strftime('%d/%m %H:%M')}] {msg}", flush=True)

# ── Slug & Fetch ──────────────────────────────────────────────────────────────

def slug_for(date):
    return f"highest-temperature-in-chengdu-on-{MONTHS[date.month-1]}-{date.day}-{date.year}"

def fetch_event(slug):
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
    # [FIX 9] limit pour éviter de tout charger en mémoire si la table grossit
    res = db.table("chengdu_tracking").select("*").limit(500).execute()
    return res.data or []

def add_signal(db, market, date_str):
    now = now_paris().strftime("%d/%m/%Y %H:%M")
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
        "derniere_lecture":  now_paris().strftime("%d/%m/%Y %H:%M"),
    }).eq("condition_id", condition_id).execute()

def resolve_signal(db, condition_id, resultat):
    now = now_paris().strftime("%d/%m/%Y %H:%M")
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
        "updated_at":      now_paris().isoformat(),
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
        # [FIX 2] m is None = erreur réseau/API → skip, réessayer au prochain cycle
        if m is None:
            log(f"  ⚠️  API indisponible pour {t['condition_id'][:16]}, skip")
            continue
        if m["closed"]:
            final = m["yes_price"]
            if final >= 0.95:
                resultat = "GAGNANT"
            elif final <= 0.05:
                resultat = "PERDANT"
            else:
                # [FIX 3] utiliser le vrai prix de clôture (final), pas le cache
                pct = round(final * 100, 1)
                resultat = f"TERMINÉ: {pct}%"
            resolve_signal(db, t["condition_id"], resultat)
        else:
            update_price(db, t["condition_id"], m["yes_price"])

# ── Rapport cycle + purge ─────────────────────────────────────────────────────

def save_rapport(db, tracking, slug):
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    db.table("chengdu_rapports").insert({
        "heure":         now_paris().strftime("%d/%m/%Y %H:%M"),
        "trackes":       len(tracking),
        "en_attente":    len(tracking) - len(resolus),
        "resolus":       len(resolus),
        "gagnes":        len(gagnes),
        "perdus":        len(perdus),
        "taux_victoire": taux,
        "marche_slug":   slug,
        "verdict": (
            "Stratégie rentable"      if taux is not None and taux >= 60 else
            "Stratégie à surveiller"  if taux is not None and taux >= 50 else
            "Stratégie non rentable"  if taux is not None else
            "En attente de données"
        ),
    }).execute()

def purge_old_rapports(db):
    # [FIX 7] garde seulement les 2880 derniers rapports (~30 jours)
    try:
        res = db.table("chengdu_rapports").select("id").order("created_at", desc=True).offset(2880).limit(200).execute()
        ids = [r["id"] for r in (res.data or [])]
        if ids:
            db.table("chengdu_rapports").delete().in_("id", ids).execute()
            log(f"  🧹 Purge: {len(ids)} anciens rapports supprimés")
    except Exception as e:
        log(f"  ⚠️  Purge rapports: {e}")

# ── Résumé 17h ────────────────────────────────────────────────────────────────

def already_have_resume_today(db):
    # [FIX 4] dédup — évite un double résumé si Railway redémarre entre 17h00 et 17h14
    today = now_paris().strftime("%d/%m/%Y")
    try:
        res = db.table("chengdu_resumes").select("id").eq("date", today).limit(1).execute()
        return bool(res.data)
    except Exception:
        return False

def generate_daily_resume(tracking):
    key = os.getenv("MISTRAL_API_KEY", "")
    if not key:
        return "MISTRAL_API_KEY manquante."
    resolus  = [t for t in tracking if t["resultat"] is not None]
    gagnes   = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus   = [t for t in resolus  if t["resultat"] == "PERDANT"]
    # [FIX 6] TERMINÉ ≠ PERDANT — séparé dans le prompt pour ne pas biaiser Mistral
    termines = [t for t in resolus  if t["resultat"] not in ("GAGNANT", "PERDANT")]
    taux     = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    lignes   = "\n".join(
        f"- {t['question'][:70]} | signalé à {t['yes_price_au_signal']}% | {t['resultat']}"
        for t in resolus[-15:]
    ) or "Aucun marché résolu."
    prompt = f"""Résume en 5 lignes max ces stats de paris sur la température à Chengdu (Polymarket, seuil 80%) :

Signaux: {len(tracking)} | Résolus: {len(resolus)} | Gagnés: {len(gagnes)} | Perdus (PERDANT): {len(perdus)} | Terminés ambigus: {len(termines)} | Taux victoire: {taux}%

Note: "TERMINÉ: X%" = marché fermé entre 5% et 95% (ambiguïté), ne pas compter comme perte.

Derniers résolus:
{lignes}

Réponds en français, très court. Donne :
1. Le taux de réussite (sur GAGNANT/PERDANT uniquement)
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
        "date":          now_paris().strftime("%d/%m/%Y"),
        "trackes":       len(tracking),
        "resolus":       len(resolus),
        "gagnes":        len(gagnes),
        "perdus":        len(perdus),
        "taux_victoire": taux,
        "analyse_text":  analyse,
    }).execute()
    log(f"📋 Résumé 17h sauvegardé — taux: {taux}%")

# ── Boucle principale ─────────────────────────────────────────────────────────

def run():
    log("🌡️  Agent Chengdu Cloud démarré (Railway + Supabase)")
    log("   Seuil : 80% YES | Scan : toutes les 15 min")
    log("")

    while True:
        # [FIX 5] client recréé à chaque cycle — évite les connexions expirées après plusieurs heures
        db  = get_db()
        now = now_paris()

        # [FIX 1] avant 14h → marché du jour encore ouvert ; après 14h → marché du lendemain
        target   = now if now.hour < MARKET_CLOSE_HOUR else now + datetime.timedelta(days=1)
        slug     = slug_for(target)
        date_str = target.strftime("%d/%m/%Y")

        log(f"── Cycle {now.strftime('%d/%m/%Y %H:%M')} ──")
        log(f"   Marché suivi : {slug}")

        # 1. Vérifier résolutions des marchés en attente
        log("Vérification des marchés résolus…")
        tracking = load_tracking(db)
        check_resolved(db, tracking)
        tracking = load_tracking(db)

        # 2. Fetch marché Chengdu
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

            # 3. Nouveaux signaux >80% + mise à jour prix des signaux existants
            tracked_ids = {t["condition_id"] for t in tracking}
            pending_ids = {t["condition_id"] for t in tracking if t["resultat"] is None}
            new_signals = 0
            for m in markets:
                if m["condition_id"] not in tracked_ids and m["yes_price"] >= 0.80:
                    add_signal(db, m, date_str)
                    new_signals += 1
                elif m["condition_id"] in pending_ids:
                    # [FIX 8] mettre à jour le prix actuel des signaux déjà en base
                    update_price(db, m["condition_id"], m["yes_price"])

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
            # Purge nocturne à 4h00 (1 fois/jour)
            if now.hour == 4 and now.minute < 15:
                purge_old_rapports(db)
        except Exception as e:
            log(f"⚠️  Rapport: {e}")

        # 6. Résumé 17h → chengdu_resumes (avec dédup)
        if now.hour == 17 and now.minute < 15:
            if not already_have_resume_today(db):
                log("⏰ 17h00 — Génération du résumé quotidien…")
                try:
                    save_resume(db, tracking)
                except Exception as e:
                    log(f"⚠️  Résumé: {e}")
            else:
                log("⏰ 17h00 — Résumé déjà généré aujourd'hui, skip")

        log(f"   Prochain cycle dans 15 min")
        log("")

        time.sleep(INTERVAL)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run()
