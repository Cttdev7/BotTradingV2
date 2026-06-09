"""
agent_temperature_cloud.py — Bot température multi-villes (Railway + Supabase)
Tourne en continu sur Railway. Toutes les 15 minutes, pour chaque ville :
- Analyse les options de température (J+0 si ouvert, sinon J+1)
- Récupère la température max prévue via Open-Meteo
- Enregistre les signaux >75% dans Supabase ({ville_id}_tracking)
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
    {
        "id":          "hong_kong",
        "label":       "Hong Kong",
        "slug_prefix": "highest-temperature-in-hong-kong",
        "lat":         22.319,
        "lon":         114.169,
        "tz":          ZoneInfo("Asia/Hong_Kong"),
    },
    {
        "id":          "nyc",
        "label":       "NYC",
        "slug_prefix": "highest-temperature-in-nyc",
        "lat":         40.713,
        "lon":         -74.006,
        "tz":          ZoneInfo("America/New_York"),
    },
    {
        "id":          "london",
        "label":       "Londres",
        "slug_prefix": "highest-temperature-in-london",
        "lat":         51.507,
        "lon":         -0.128,
        "tz":          ZoneInfo("Europe/London"),
    },
    {
        "id":          "tokyo",
        "label":       "Tokyo",
        "slug_prefix": "highest-temperature-in-tokyo",
        "lat":         35.676,
        "lon":         139.650,
        "tz":          ZoneInfo("Asia/Tokyo"),
    },
    {
        "id":          "atlanta",
        "label":       "Atlanta",
        "slug_prefix": "highest-temperature-in-atlanta",
        "lat":         33.749,
        "lon":         -84.388,
        "tz":          ZoneInfo("America/New_York"),
    },
    {
        "id":          "seattle",
        "label":       "Seattle",
        "slug_prefix": "highest-temperature-in-seattle",
        "lat":         47.606,
        "lon":         -122.332,
        "tz":          ZoneInfo("America/Los_Angeles"),
    },
    {
        "id":          "miami",
        "label":       "Miami",
        "slug_prefix": "highest-temperature-in-miami",
        "lat":         25.775,
        "lon":         -80.208,
        "tz":          ZoneInfo("America/New_York"),
    },
    {
        "id":          "singapore",
        "label":       "Singapour",
        "slug_prefix": "highest-temperature-in-singapore",
        "lat":         1.352,
        "lon":         103.820,
        "tz":          ZoneInfo("Asia/Singapore"),
    },
    {
        "id":          "madrid",
        "label":       "Madrid",
        "slug_prefix": "highest-temperature-in-madrid",
        "lat":         40.416,
        "lon":         -3.703,
        "tz":          ZoneInfo("Europe/Madrid"),
    },
    {
        "id":          "shanghai",
        "label":       "Shanghai",
        "slug_prefix": "highest-temperature-in-shanghai",
        "lat":         31.230,
        "lon":         121.473,
        "tz":          ZoneInfo("Asia/Shanghai"),
    },
    {
        "id":          "los_angeles",
        "label":       "Los Angeles",
        "slug_prefix": "highest-temperature-in-los-angeles",
        "lat":         34.052,
        "lon":         -118.244,
        "tz":          ZoneInfo("America/Los_Angeles"),
    },
    {
        "id":          "guangzhou",
        "label":       "Guangzhou",
        "slug_prefix": "highest-temperature-in-guangzhou",
        "lat":         23.129,
        "lon":         113.264,
        "tz":          ZoneInfo("Asia/Shanghai"),
    },
    {
        "id":          "mexico_city",
        "label":       "Mexico City",
        "slug_prefix": "highest-temperature-in-mexico-city",
        "lat":         19.433,
        "lon":         -99.133,
        "tz":          ZoneInfo("America/Mexico_City"),
    },
    {
        "id":          "amsterdam",
        "label":       "Amsterdam",
        "slug_prefix": "highest-temperature-in-amsterdam",
        "lat":         52.374,
        "lon":         4.898,
        "tz":          ZoneInfo("Europe/Amsterdam"),
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
    res = db.table(f"{ville['id']}_tracking").select("*").limit(5000).execute()
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
        final = m["yes_price"]
        # Résolution officielle OU prix quasi-certain (marché "En cours de révision")
        if m["closed"] or m["resolved"] or final >= 0.99 or final <= 0.01:
            if final >= 0.95:
                resultat = "GAGNANT"
            elif final <= 0.05:
                resultat = "PERDANT"
            else:
                resultat = f"TERMINÉ: {round(final * 100, 1)}%"
            if not (m["closed"] or m["resolved"]):
                log(f"  🔍 Prix={round(final*100,1)}% → résolution anticipée ({resultat})", ville)
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
                except Exception as e:
                    log(f"  ⚠️ Erreur parsing date/Open-Meteo : {e}", ville)
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
    prompt = f"""Résume en 5 lignes max ces stats de paris sur la température à {ville['label']} (Polymarket, seuil 75%) :

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
            flag  = "🔥" if m["yes_price"] >= 0.75 else ("📊" if m["yes_price"] >= 0.30 else "  ")
            temp  = m["question"].split("be ")[-1].split(" on")[0]
            t_int = temp_from_question(m["question"])
            match = " ← Open-Meteo" if (temp_actuel is not None and t_int == temp_actuel) else ""
            log(f"   {flag} {m['yes_price']*100:5.1f}%  {temp}{match}", ville)

        # 4. Signal dominant (1 seul par ville par jour)
        tracked_ids = {t["condition_id"] for t in tracking}
        pending_ids = {t["condition_id"] for t in tracking if t["resultat"] is None}

        candidates = [m for m in markets if m["yes_price"] >= 0.75 and not m["closed"] and not m["resolved"]]
        dominant   = max(candidates, key=lambda x: x["yes_price"]) if candidates else None

        if dominant:
            if dominant["condition_id"] not in tracked_ids:
                # Nouveau dominant — annuler tout signal en attente
                for old in [t for t in tracking if t["resultat"] is None]:
                    temp_old = old["question"].split("be ")[-1].split(" on")[0]
                    log(f"   🔄 {temp_old} → PERDANT (remplacé par {dominant['yes_price']*100:.0f}%)", ville)
                    resolve_signal(db, ville, old["condition_id"], "PERDANT")
                add_signal(db, ville, dominant, date_str)
                log(f"   🎯 Nouveau signal dominant !", ville)
            else:
                update_price(db, ville, dominant["condition_id"], dominant["yes_price"])
                log(f"   📊 Signal dominant inchangé ({dominant['yes_price']*100:.0f}%)", ville)
        else:
            for m in markets:
                if m["condition_id"] in pending_ids:
                    update_price(db, ville, m["condition_id"], m["yes_price"])
            log("   Aucun signal dominant (aucune option à 75%+)", ville)

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


# ── Agent Stratège Mistral (cross-ville) ─────────────────────────────────────

def analyser_strategie(db, villes):
    key = os.getenv("MISTRAL_API_KEY", "")
    if not key:
        log("⚠️  MISTRAL_API_KEY manquante — analyse stratégique impossible")
        return

    # Collecter tous les signaux de toutes les villes
    all_tracking = []
    for ville in villes:
        rows = load_tracking(db, ville)
        for r in rows:
            r["ville"] = ville["label"]
        all_tracking.extend(rows)

    if not all_tracking:
        log("⚠️  Aucune donnée pour l'analyse stratégique")
        return

    resolus = [t for t in all_tracking if t.get("resultat")]
    gagnes  = [t for t in resolus if t.get("resultat") == "GAGNANT"]
    perdus  = [t for t in resolus if t.get("resultat") == "PERDANT"]
    taux_g  = round(len(gagnes) / len(resolus) * 100, 1) if resolus else 0

    # Stats par ville
    by_ville = {}
    for t in resolus:
        v = t["ville"]
        if v not in by_ville:
            by_ville[v] = {"gagnes": 0, "perdus": 0, "signaux": []}
        by_ville[v]["gagnes" if t["resultat"] == "GAGNANT" else "perdus"] += 1
        by_ville[v]["signaux"].append(t.get("yes_price_au_signal", 0))

    stats_ville = "\n".join([
        f"- {v}: {s['gagnes']}G/{s['perdus']}P ({round(s['gagnes']/(s['gagnes']+s['perdus'])*100) if s['gagnes']+s['perdus'] else 0}%) | seuils: {sorted(s['signaux'])}"
        for v, s in by_ville.items()
    ]) or "Aucun résultat résolu pour le moment."

    # Détail des 60 derniers signaux
    details = "\n".join([
        f"- {t['ville']} | {t.get('question','?')[:65]} | signal:{t.get('yes_price_au_signal')}% | {t.get('resultat','en attente')} | {(t.get('detecte_le','?') or '?')[:16]}"
        for t in all_tracking[-60:]
    ])

    # Charger les analyses passées pour la mémoire de Mistral
    past_analyses = []
    try:
        rows = db.table("strategie_analyses").select("date,nb_signaux,analyse_text") \
            .order("created_at", desc=True).limit(7).execute().data or []
        past_analyses = list(reversed(rows))  # chronologique
    except Exception:
        pass

    memoire = ""
    if past_analyses:
        blocs = []
        for a in past_analyses:
            blocs.append(f"[{a['date']} — {a['nb_signaux']} signaux]\n{a['analyse_text'][:600]}…")
        memoire = "\n\n---\n".join(blocs)
    else:
        memoire = "Aucune analyse précédente — c'est la première."

    prompt = f"""Tu es un stratège IA dédié à un bot de trading sur Polymarket, spécialisé marchés météo température.
Le bot track les options YES >75% sur "highest temperature in [ville] on [date]".
Objectif : devenir rentable et exécuter de vrais trades.

════ MÉMOIRE — TES {len(past_analyses)} ANALYSES PRÉCÉDENTES ════
{memoire}

════ DONNÉES ACTUELLES ════
- Signaux total : {len(all_tracking)} | Résolus : {len(resolus)} | En attente : {len(all_tracking)-len(resolus)}
- Gagnés : {len(gagnes)} | Perdus : {len(perdus)} | Taux global : {taux_g}%
- Villes actives : {', '.join(v['label'] for v in villes)}
- Seuil actuel : 75% YES

PERFORMANCE PAR VILLE
{stats_ville}

HISTORIQUE SIGNAUX (60 derniers)
{details}

════ INSTRUCTIONS ════
OBJECTIF ABSOLU : chaque analyse doit être meilleure que la précédente. Tu dois mesurer la progression et orienter toutes tes recommandations vers une amélioration concrète du taux de victoire.

Produis une analyse structurée en 3 parties.

1. BILAN DE PERFORMANCE
Commence par : "Taux actuel : {taux_g}%". Compare avec le taux de tes analyses passées. Est-ce qu'on progresse ? Pourquoi ? Quelles recommandations précédentes ont été appliquées et avec quel résultat ? Identifie les patterns gagnants à amplifier et les patterns perdants à éliminer.

2. RECOMMANDATIONS CONCRÈTES
Chaque recommandation doit viser à faire monter le taux au-dessus de {taux_g}%. Sois précis : quel seuil (ex: monter à 82%), quelles villes à prioriser/abandonner, quel timing (heure locale de détection), comment filtrer les faux signaux.

3. FEUILLE DE ROUTE — 3 PRIORITÉS POUR PROGRESSER
Les 3 actions qui auront le plus d'impact sur le taux de victoire. Pour chaque action, indique l'impact attendu en points de % (ex: "+5% taux"). Si une priorité de la dernière analyse n'a pas été faite, rappelle-la en premier.

Maximum 400 mots. Direct, factuel. La progression est la seule métrique qui compte."""

    try:
        r = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "mistral-small-latest", "messages": [{"role": "user", "content": prompt}], "max_tokens": 700},
            timeout=30
        )
        r.raise_for_status()
        analyse = r.json()["choices"][0]["message"]["content"]
        now = datetime.datetime.now(PARIS).strftime("%d/%m/%Y %H:%M")
        db.table("strategie_analyses").insert({
            "date":         now,
            "nb_signaux":   len(all_tracking),
            "nb_villes":    len(villes),
            "nb_resolus":   len(resolus),
            "nb_gagnes":    len(gagnes),
            "taux_global":  taux_g,
            "analyse_text": analyse,
        }).execute()
        log(f"🧠 Analyse stratégique générée ({len(all_tracking)} signaux, {len(villes)} villes)")
        # Réinitialiser le flag trigger
        db.table("strategie_config").update({"trigger": False}).eq("id", "main").execute()
    except Exception as e:
        log(f"⚠️  Erreur analyse stratégique : {e}")

def check_strategie_trigger(db):
    """Retourne True si un trigger on-demand a été demandé depuis le dashboard."""
    try:
        row = db.table("strategie_config").select("trigger").eq("id", "main").single().execute()
        return row.data.get("trigger", False)
    except Exception:
        return False

def already_have_strategie_today(db):
    """Évite de générer 2 fois la même analyse dans la même heure."""
    try:
        now = datetime.datetime.now(PARIS)
        prefix = now.strftime("%d/%m/%Y %H:")
        rows = db.table("strategie_analyses").select("date").order("created_at", desc=True).limit(1).execute().data
        return bool(rows and rows[0]["date"].startswith(prefix))
    except Exception:
        return False

# ── Wallet balance ────────────────────────────────────────────────────────────

POLYGON_RPC = "https://polygon-bor-rpc.publicnode.com"

def sync_wallet(db):
    """Lit la balance Polymarket (PUSD) + POL on-chain et écrit dans bot_status."""
    wallet = os.environ.get("WALLET_ADDRESS", "")
    if not wallet:
        return
    try:
        # Valeur portfolio Polymarket (inclut PUSD)
        r = requests.get("https://data-api.polymarket.com/value",
                         params={"user": wallet.lower()}, timeout=10)
        data = r.json()
        pusd = float(data[0]["value"]) if data and isinstance(data, list) and data else 0.0
    except Exception:
        pusd = 0.0
    try:
        # Solde POL natif on-chain
        r2 = requests.post(POLYGON_RPC,
            json={"jsonrpc": "2.0", "method": "eth_getBalance",
                  "params": [wallet, "latest"], "id": 1}, timeout=10)
        pol = int(r2.json().get("result", "0x0"), 16) / 1e18
    except Exception:
        pol = 0.0
    try:
        db.table("bot_status").upsert({
            "id":         "polyedge",
            "wallet":     wallet,
            "usdc":       round(pusd, 2),
            "usdce":      0,
            "pol":        round(pol, 4),
            "updated_at": datetime.datetime.now(PARIS).isoformat(),
        }).execute()
        log(f"💰 Wallet sync : PUSD ${pusd:.2f} | POL {pol:.4f}")
    except Exception as e:
        log(f"⚠️  Wallet sync: {e}")

# ── Boucle principale ─────────────────────────────────────────────────────────

def run():
    log("🌡️  Agent Température Multi-Villes démarré (Railway + Supabase)")
    log(f"   Villes : {', '.join(v['label'] for v in VILLES)}")
    log(f"   Seuil : 75% YES | Scan : toutes les 15 min")
    log("")

    while True:
        db = get_db()

        # Sync wallet toutes les 15 min
        try:
            sync_wallet(db)
        except Exception as e:
            log(f"⚠️  Wallet: {e}")

        for ville in VILLES:
            try:
                run_ville(db, ville)
            except Exception as e:
                log(f"❌ Erreur cycle: {e}", ville)
            log("")

        # Analyse stratégique : 18h auto + trigger on-demand
        now_p = datetime.datetime.now(PARIS)
        try:
            on_demand = check_strategie_trigger(db)
            run_strategie = on_demand or (now_p.hour == 18 and now_p.minute < 15)
            if run_strategie and not already_have_strategie_today(db):
                source = "on-demand" if on_demand else "18h auto"
                log(f"🧠 Lancement analyse stratégique ({source})…")
                analyser_strategie(db, VILLES)
        except Exception as e:
            log(f"⚠️  Analyse stratégique: {e}")

        log(f"⏳ Prochain cycle dans 15 min\n")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run()
