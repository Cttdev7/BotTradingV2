"""
agent_temperature_cloud.py — Bot température multi-villes (Railway + Supabase)
Tourne en continu sur Railway. Toutes les 15 minutes, pour chaque ville :
- Analyse les options de température (J+0 si ouvert, sinon J+1)
- Récupère la température max prévue via Open-Meteo
- Enregistre les signaux >80% dans Supabase ({ville_id}_tracking)
- Vérifie les résolutions des marchés précédents
- Met à jour les stats globales ({ville_id}_stats)
Ajouter une ville = ajouter 1 entrée dans VILLES.
"""

import os, re, json, time, datetime, requests
from zoneinfo import ZoneInfo
from supabase import create_client

PARIS = ZoneInfo("Europe/Paris")

# ── Config villes ─────────────────────────────────────────────────────────────

VILLES = [
    {
        "id":          "chengdu",
        "label":       "Chengdu",
        "slug_prefix": "highest-temperature-in-chengdu",
        "lat":         30.578,
        "lon":         103.947,
        "tz":          ZoneInfo("Asia/Shanghai"),
    },
    {
        "id":          "seoul",
        "label":       "Séoul",
        "slug_prefix": "highest-temperature-in-seoul",
        "lat":         37.566,
        "lon":         126.978,
        "tz":          ZoneInfo("Asia/Seoul"),
    },
]

GAMMA_API = "https://gamma-api.polymarket.com"
TIMEOUT   = 15
INTERVAL  = 900  # 15 min

MONTHS = ["january","february","march","april","may","june",
          "july","august","september","october","november","december"]

# ── Supabase ──────────────────────────────────────────────────────────────────

def get_db():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def log(msg, ville=None):
    prefix = f"[{ville['label']}] " if ville else ""
    print(f"[{datetime.datetime.now(PARIS).strftime('%d/%m %H:%M')}] {prefix}{msg}", flush=True)

# ── Slug & Fetch ──────────────────────────────────────────────────────────────

def slug_for(ville, date):
    return f"{ville['slug_prefix']}-on-{MONTHS[date.month-1]}-{date.day}-{date.year}"

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
                "resolved":     m.get("resolved", False),
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
                "resolved":     m.get("resolved", False),
            }
    except Exception as e:
        log(f"⚠️  Fetch {condition_id[:16]}: {e}")
    return None

# ── Température Open-Meteo (gratuit, sans clé) ────────────────────────────────

def fetch_temp(ville, date):
    date_str    = date.strftime("%Y-%m-%d")
    today_local = datetime.datetime.now(ville["tz"]).date()
    try:
        if date.date() >= today_local:
            r = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude":      ville["lat"],
                    "longitude":     ville["lon"],
                    "daily":         "temperature_2m_max",
                    "timezone":      str(ville["tz"]),
                    "forecast_days": 3,
                },
                timeout=TIMEOUT,
            )
        else:
            r = requests.get(
                "https://archive-api.open-meteo.com/v1/era5",
                params={
                    "latitude":   ville["lat"],
                    "longitude":  ville["lon"],
                    "daily":      "temperature_2m_max",
                    "timezone":   str(ville["tz"]),
                    "start_date": date_str,
                    "end_date":   date_str,
                },
                timeout=TIMEOUT,
            )
        r.raise_for_status()
        data = r.json()
        for d, t in zip(data["daily"]["time"], data["daily"]["temperature_2m_max"]):
            if d == date_str and t is not None:
                return int(t)
    except Exception as e:
        log(f"⚠️  Open-Meteo ({ville['label']}): {e}")
    return None

def temp_from_question(question):
    m = re.search(r'be (\d+)°C', question)
    return int(m.group(1)) if m else None

# ── Tracking Supabase ─────────────────────────────────────────────────────────

def load_tracking(db, ville):
    res = db.table(f"{ville['id']}_tracking").select("*").limit(500).execute()
    return res.data or []

def add_signal(db, ville, market, date_str):
    now = datetime.datetime.now(PARIS).strftime("%d/%m/%Y %H:%M")
    pct = round(market["yes_price"] * 100, 1)
    db.table(f"{ville['id']}_tracking").upsert({
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
    log(f"  🎯 SIGNAL: {market['question'][:60]} ({pct}%)", ville)

def update_price(db, ville, condition_id, yes_price):
    db.table(f"{ville['id']}_tracking").update({
        "yes_price_actuel": round(yes_price * 100, 1),
        "derniere_lecture": datetime.datetime.now(PARIS).strftime("%d/%m/%Y %H:%M"),
    }).eq("condition_id", condition_id).execute()

def resolve_signal(db, ville, condition_id, resultat):
    now = datetime.datetime.now(PARIS).strftime("%d/%m/%Y %H:%M")
    db.table(f"{ville['id']}_tracking").update({
        "resultat":  resultat,
        "resolu_le": now,
    }).eq("condition_id", condition_id).execute()
    icon = "✅" if resultat == "GAGNANT" else "❌" if resultat == "PERDANT" else "🔚"
    log(f"  {icon} {resultat}", ville)

# ── Stats globales ────────────────────────────────────────────────────────────

def update_stats(db, ville, tracking):
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
        if t["resultat"] == "GAGNANT":   by_date[d]["gagnes"] += 1
        elif t["resultat"] == "PERDANT": by_date[d]["perdus"] += 1
        else:                            by_date[d]["en_attente"] += 1

    db.table(f"{ville['id']}_stats").upsert({
        "id":            ville["id"],
        "total_signaux": len(tracking),
        "en_attente":    len(tracking) - len(resolus),
        "resolus":       len(resolus),
        "gagnes":        len(gagnes),
        "perdus":        len(perdus),
        "taux_victoire": taux,
        "par_date":      by_date,
        "updated_at":    datetime.datetime.now(PARIS).isoformat(),
        "verdict": (
            "Stratégie rentable"      if taux is not None and taux >= 60 else
            "Stratégie à surveiller"  if taux is not None and taux >= 50 else
            "Stratégie non rentable"  if taux is not None else
            "En attente de données"
        ),
    }).execute()

# ── Résolution des marchés en attente ─────────────────────────────────────────

def check_resolved(db, ville, tracking):
    pending = [t for t in tracking if t["resultat"] is None]
    if not pending:
        return
    for t in pending:
        m = fetch_market_by_id(t["condition_id"])
        if m is None:
            log(f"  ⚠️  API indisponible pour {t['condition_id'][:16]}, skip", ville)
            continue
        if m["closed"] or m["resolved"]:
            final = m["yes_price"]
            if final >= 0.95:
                resultat = "GAGNANT"
            elif final <= 0.05:
                resultat = "PERDANT"
            else:
                resultat = f"TERMINÉ: {round(final * 100, 1)}%"
            resolve_signal(db, ville, t["condition_id"], resultat)

            temp_marche = temp_from_question(t["question"])
            if temp_marche is not None and resultat in ("GAGNANT", "PERDANT"):
                try:
                    d = datetime.datetime.strptime(t["date_marche"], "%d/%m/%Y")
                    date_dt = d.replace(tzinfo=ville["tz"])
                    temp_om = fetch_temp(ville, date_dt)
                    if temp_om is not None:
                        if temp_om == temp_marche and resultat == "GAGNANT":
                            log(f"  📡 Open-Meteo {temp_om}°C → GAGNANT {temp_marche}°C ✅ CORRECT", ville)
                        elif temp_om == temp_marche and resultat == "PERDANT":
                            log(f"  📡 Open-Meteo {temp_om}°C → PERDANT {temp_marche}°C ⚠️ RATÉ", ville)
                        else:
                            log(f"  📡 Open-Meteo {temp_om}°C → {resultat} {temp_marche}°C ❌ INCORRECT", ville)
                except Exception:
                    pass
        else:
            update_price(db, ville, t["condition_id"], m["yes_price"])

# ── Rapport cycle ─────────────────────────────────────────────────────────────

def save_rapport(db, ville, tracking, slug, temp_actuel=None):
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    db.table(f"{ville['id']}_rapports").insert({
        "heure":         datetime.datetime.now(PARIS).strftime("%d/%m/%Y %H:%M"),
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

def purge_old_rapports(db, ville):
    try:
        res = db.table(f"{ville['id']}_rapports").select("id").order("created_at", desc=True).offset(2880).limit(200).execute()
        ids = [r["id"] for r in (res.data or [])]
        if ids:
            db.table(f"{ville['id']}_rapports").delete().in_("id", ids).execute()
            log(f"  🧹 Purge: {len(ids)} anciens rapports supprimés", ville)
    except Exception as e:
        log(f"  ⚠️  Purge: {e}", ville)

# ── Résumé quotidien 17h ──────────────────────────────────────────────────────

def already_have_resume_today(db, ville):
    today = datetime.datetime.now(PARIS).strftime("%d/%m/%Y")
    try:
        res = db.table(f"{ville['id']}_resumes").select("id").eq("date", today).limit(1).execute()
        return bool(res.data)
    except Exception:
        return False

def generate_daily_resume(ville, tracking, temp_actuel=None):
    key = os.getenv("MISTRAL_API_KEY", "")
    if not key:
        return "MISTRAL_API_KEY manquante."
    resolus  = [t for t in tracking if t["resultat"] is not None]
    gagnes   = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus   = [t for t in resolus  if t["resultat"] == "PERDANT"]
    taux     = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    lignes   = "\n".join(
        f"- {t['question'][:70]} | signalé à {t['yes_price_au_signal']}% | {t['resultat']}"
        for t in resolus[-15:]
    ) or "Aucun marché résolu."
    temp_line = f"\nTempérature max prévue demain à {ville['label']} (Open-Meteo) : {temp_actuel}°C" if temp_actuel else ""
    prompt = f"""Résume en 5 lignes max ces stats de paris sur la température à {ville['label']} (Polymarket, seuil 80%) :

Signaux: {len(tracking)} | Résolus: {len(resolus)} | Gagnés: {len(gagnes)} | Perdus: {len(perdus)} | Taux: {taux}%{temp_line}

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

def save_resume(db, ville, tracking, temp_actuel=None):
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    analyse = generate_daily_resume(ville, tracking, temp_actuel)
    db.table(f"{ville['id']}_resumes").insert({
        "date":          datetime.datetime.now(PARIS).strftime("%d/%m/%Y"),
        "trackes":       len(tracking),
        "resolus":       len(resolus),
        "gagnes":        len(gagnes),
        "perdus":        len(perdus),
        "taux_victoire": taux,
        "analyse_text":  analyse,
    }).execute()
    log(f"📋 Résumé 17h sauvegardé — taux: {taux}%", ville)

# ── Cycle pour une ville ──────────────────────────────────────────────────────

def run_ville(db, ville):
    now_p = datetime.datetime.now(PARIS)
    now_v = datetime.datetime.now(ville["tz"])

    # J+0 si encore ouvert, sinon J+1
    today_v    = now_v.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_v = today_v + datetime.timedelta(days=1)

    slug_today  = slug_for(ville, today_v)
    _, mkts_j0  = fetch_event(slug_today)
    j0_open     = any(not m["closed"] and not m["resolved"] for m in mkts_j0) if mkts_j0 else False

    target   = today_v if j0_open else tomorrow_v
    slug     = slug_for(ville, target)
    date_str = target.strftime("%d/%m/%Y")

    log(f"── {ville['label']} | {now_p.strftime('%H:%M')} (local: {now_v.strftime('%H:%M')}) | {slug.split('-on-')[1]} {'(J+0)' if j0_open else '(J+1)'} ──", ville)

    # 1. Résolutions en attente
    tracking = load_tracking(db, ville)
    check_resolved(db, ville, tracking)
    tracking = load_tracking(db, ville)

    # 2. Température Open-Meteo
    temp_actuel = fetch_temp(ville, target)
    if temp_actuel is not None:
        log(f"   🌡️  Open-Meteo : {temp_actuel}°C max prévu pour {date_str}", ville)
    else:
        log("   🌡️  Open-Meteo : donnée indisponible", ville)

    # 3. Fetch marché Polymarket
    if j0_open:
        event, markets = None, mkts_j0
    else:
        event, markets = fetch_event(slug)

    if not markets:
        log("   ⚠️  Aucun marché trouvé", ville)
    else:
        top = sorted(markets, key=lambda x: x["yes_price"], reverse=True)
        log(f"   {len(markets)} options | Top: {top[0]['question'].split('be ')[-1].split(' on')[0]} à {top[0]['yes_price']*100:.0f}%", ville)

        for m in sorted(markets, key=lambda x: x["yes_price"], reverse=True):
            flag  = "🔥" if m["yes_price"] >= 0.80 else ("📊" if m["yes_price"] >= 0.30 else "  ")
            temp  = m["question"].split("be ")[-1].split(" on")[0]
            t_int = temp_from_question(m["question"])
            match = " ← Open-Meteo" if (temp_actuel is not None and t_int == temp_actuel) else ""
            log(f"   {flag} {m['yes_price']*100:5.1f}%  {temp}{match}", ville)

        # 4. Nouveaux signaux + mise à jour prix
        tracked_ids = {t["condition_id"] for t in tracking}
        pending_ids = {t["condition_id"] for t in tracking if t["resultat"] is None}
        new_signals = 0
        for m in markets:
            if m["condition_id"] not in tracked_ids and m["yes_price"] >= 0.80 and not m["closed"] and not m["resolved"]:
                add_signal(db, ville, m, date_str)
                new_signals += 1
            elif m["condition_id"] in pending_ids:
                update_price(db, ville, m["condition_id"], m["yes_price"])

        if new_signals:
            log(f"   🎯 {new_signals} nouveau(x) signal(s) !", ville)
        else:
            log("   Aucun nouveau signal (aucune option à 80%+)", ville)

    # 5. Alerte divergence Open-Meteo
    if temp_actuel is not None:
        pending = [t for t in tracking if t["resultat"] is None]
        signal_temps = [x for x in [temp_from_question(t["question"]) for t in pending] if x is not None]
        if signal_temps and temp_actuel not in signal_temps:
            log(f"   ⚠️  Open-Meteo ({temp_actuel}°C) ≠ signaux trackés {signal_temps}", ville)
        elif signal_temps and temp_actuel in signal_temps:
            log(f"   ✅ Signal tracké {temp_actuel}°C = prévision Open-Meteo !", ville)

    # 6. Stats + rapport
    tracking = load_tracking(db, ville)
    update_stats(db, ville, tracking)

    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    log(f"📊 Signaux:{len(tracking)} | Résolus:{len(resolus)} | ✅{len(gagnes)} ❌{len(perdus)} | Taux:{taux}%", ville)

    try:
        save_rapport(db, ville, tracking, slug, temp_actuel)
        if now_p.hour == 4 and now_p.minute < 15:
            purge_old_rapports(db, ville)
    except Exception as e:
        log(f"⚠️  Rapport: {e}", ville)

    # 7. Résumé 17h
    if now_p.hour == 17 and now_p.minute < 15:
        if not already_have_resume_today(db, ville):
            log("⏰ 17h00 — Génération résumé quotidien…", ville)
            try:
                save_resume(db, ville, tracking, temp_actuel)
            except Exception as e:
                log(f"⚠️  Résumé: {e}", ville)

# ── Boucle principale ─────────────────────────────────────────────────────────

def run():
    log("🌡️  Agent Température Multi-Villes démarré (Railway + Supabase)")
    log(f"   Villes : {', '.join(v['label'] for v in VILLES)}")
    log(f"   Seuil : 80% YES | Scan : toutes les 15 min")
    log("")

    while True:
        db = get_db()
        for ville in VILLES:
            try:
                run_ville(db, ville)
            except Exception as e:
                log(f"❌ Erreur cycle: {e}", ville)
            log("")

        log(f"⏳ Prochain cycle dans 15 min\n")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run()
