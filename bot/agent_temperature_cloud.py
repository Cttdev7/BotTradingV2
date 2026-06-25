"""
agent_temperature_cloud.py — Bot température multi-villes (Railway + Supabase)
Tourne en continu sur Railway. Toutes les 15 minutes, pour chaque ville :
- Analyse les options de température (J+0 si ouvert, sinon J+1)
- Récupère la température max prévue via Open-Meteo
- Enregistre les signaux >82% dans Supabase ({ville_id}_tracking)
- Vérifie les résolutions des marchés précédents
- Met à jour les stats globales ({ville_id}_stats)
Ajouter une ville = ajouter 1 entrée dans VILLES.
"""

import os, re, json, time, datetime, requests
from zoneinfo import ZoneInfo
from supabase import create_client

PARIS = ZoneInfo("Europe/Paris")

# Villes exclues du scan (taux de victoire trop bas — recommandation Mistral 14/06/2026)
VILLES_EXCLUES = {"shanghai", "beijing", "denver"}

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
    {
        "id":          "paris",
        "label":       "Paris",
        "slug_prefix": "highest-temperature-in-paris",
        "lat":         48.856,
        "lon":         2.352,
        "tz":          ZoneInfo("Europe/Paris"),
    },
    {
        "id":          "toronto",
        "label":       "Toronto",
        "slug_prefix": "highest-temperature-in-toronto",
        "lat":         43.653,
        "lon":         -79.383,
        "tz":          ZoneInfo("America/Toronto"),
    },
    {
        "id":          "chicago",
        "label":       "Chicago",
        "slug_prefix": "highest-temperature-in-chicago",
        "lat":         41.878,
        "lon":         -87.629,
        "tz":          ZoneInfo("America/Chicago"),
    },
    {
        "id":          "denver",
        "label":       "Denver",
        "slug_prefix": "highest-temperature-in-denver",
        "lat":         39.739,
        "lon":         -104.984,
        "tz":          ZoneInfo("America/Denver"),
    },
    {
        "id":          "houston",
        "label":       "Houston",
        "slug_prefix": "highest-temperature-in-houston",
        "lat":         29.760,
        "lon":         -95.369,
        "tz":          ZoneInfo("America/Chicago"),
    },
    {
        "id":          "taipei",
        "label":       "Taipei",
        "slug_prefix": "highest-temperature-in-taipei",
        "lat":         25.033,
        "lon":         121.565,
        "tz":          ZoneInfo("Asia/Taipei"),
    },
    {
        "id":          "beijing",
        "label":       "Beijing",
        "slug_prefix": "highest-temperature-in-beijing",
        "lat":         39.909,
        "lon":         116.397,
        "tz":          ZoneInfo("Asia/Shanghai"),
    },
    {
        "id":          "san_francisco",
        "label":       "San Francisco",
        "slug_prefix": "highest-temperature-in-san-francisco",
        "lat":         37.774,
        "lon":         -122.419,
        "tz":          ZoneInfo("America/Los_Angeles"),
    },
    {
        "id":          "dallas",
        "label":       "Dallas",
        "slug_prefix": "highest-temperature-in-dallas",
        "lat":         32.776,
        "lon":         -96.796,
        "tz":          ZoneInfo("America/Chicago"),
    },
    {
        "id":          "wellington",
        "label":       "Wellington",
        "slug_prefix": "highest-temperature-in-wellington",
        "lat":         -41.286,
        "lon":         174.776,
        "tz":          ZoneInfo("Pacific/Auckland"),
    },
    {
        "id":          "chongqing",
        "label":       "Chongqing",
        "slug_prefix": "highest-temperature-in-chongqing",
        "lat":         29.563,
        "lon":         106.551,
        "tz":          ZoneInfo("Asia/Shanghai"),
    },
    {
        "id":          "wuhan",
        "label":       "Wuhan",
        "slug_prefix": "highest-temperature-in-wuhan",
        "lat":         30.593,
        "lon":         114.305,
        "tz":          ZoneInfo("Asia/Shanghai"),
    },
    {
        "id":          "ankara",
        "label":       "Ankara",
        "slug_prefix": "highest-temperature-in-ankara",
        "lat":         39.920,
        "lon":         32.854,
        "tz":          ZoneInfo("Europe/Istanbul"),
    },
    {
        "id":          "moscow",
        "label":       "Moscou",
        "slug_prefix": "highest-temperature-in-moscow",
        "lat":         55.752,
        "lon":         37.615,
        "tz":          ZoneInfo("Europe/Moscow"),
    },
    {
        "id":          "lucknow",
        "label":       "Lucknow",
        "slug_prefix": "highest-temperature-in-lucknow",
        "lat":         26.847,
        "lon":         80.947,
        "tz":          ZoneInfo("Asia/Kolkata"),
    },
    {
        "id":          "istanbul",
        "label":       "Istanbul",
        "slug_prefix": "highest-temperature-in-istanbul",
        "lat":         41.015,
        "lon":         28.979,
        "tz":          ZoneInfo("Europe/Istanbul"),
    },
    {
        "id":          "warsaw",
        "label":       "Varsovie",
        "slug_prefix": "highest-temperature-in-warsaw",
        "lat":         52.237,
        "lon":         21.017,
        "tz":          ZoneInfo("Europe/Warsaw"),
    },
    {
        "id":          "milan",
        "label":       "Milan",
        "slug_prefix": "highest-temperature-in-milan",
        "lat":         45.464,
        "lon":         9.189,
        "tz":          ZoneInfo("Europe/Rome"),
    },
    {
        "id":          "helsinki",
        "label":       "Helsinki",
        "slug_prefix": "highest-temperature-in-helsinki",
        "lat":         60.169,
        "lon":         24.935,
        "tz":          ZoneInfo("Europe/Helsinki"),
    },
    {
        "id":          "karachi",
        "label":       "Karachi",
        "slug_prefix": "highest-temperature-in-karachi",
        "lat":         24.861,
        "lon":         67.010,
        "tz":          ZoneInfo("Asia/Karachi"),
    },
    {
        "id":          "cape_town",
        "label":       "Cape Town",
        "slug_prefix": "highest-temperature-in-cape-town",
        "lat":         -33.924,
        "lon":         18.424,
        "tz":          ZoneInfo("Africa/Johannesburg"),
    },
    {
        "id":          "jeddah",
        "label":       "Jeddah",
        "slug_prefix": "highest-temperature-in-jeddah",
        "lat":         21.485,
        "lon":         39.192,
        "tz":          ZoneInfo("Asia/Riyadh"),
    },
    {
        "id":          "shenzhen",
        "label":       "Shenzhen",
        "slug_prefix": "highest-temperature-in-shenzhen",
        "lat":         22.543,
        "lon":         114.058,
        "tz":          ZoneInfo("Asia/Shanghai"),
    },
    {
        "id":          "busan",
        "label":       "Busan",
        "slug_prefix": "highest-temperature-in-busan",
        "lat":         35.179,
        "lon":         129.075,
        "tz":          ZoneInfo("Asia/Seoul"),
    },
    {
        "id":          "qingdao",
        "label":       "Qingdao",
        "slug_prefix": "highest-temperature-in-qingdao",
        "lat":         36.066,
        "lon":         120.383,
        "tz":          ZoneInfo("Asia/Shanghai"),
    },
    {
        "id":          "kuala_lumpur",
        "label":       "Kuala Lumpur",
        "slug_prefix": "highest-temperature-in-kuala-lumpur",
        "lat":         3.140,
        "lon":         101.687,
        "tz":          ZoneInfo("Asia/Kuala_Lumpur"),
    },
    {
        "id":          "tel_aviv",
        "label":       "Tel Aviv",
        "slug_prefix": "highest-temperature-in-tel-aviv",
        "lat":         32.085,
        "lon":         34.781,
        "tz":          ZoneInfo("Asia/Jerusalem"),
    },
    {
        "id":          "manila",
        "label":       "Manila",
        "slug_prefix": "highest-temperature-in-manila",
        "lat":         14.599,
        "lon":         120.984,
        "tz":          ZoneInfo("Asia/Manila"),
    },
    {
        "id":          "munich",
        "label":       "Munich",
        "slug_prefix": "highest-temperature-in-munich",
        "lat":         48.137,
        "lon":         11.576,
        "tz":          ZoneInfo("Europe/Berlin"),
    },
]

GAMMA_API = "https://gamma-api.polymarket.com"
TIMEOUT   = 15
INTERVAL  = 900  # 15 min

MONTHS = ["january","february","march","april","may","june",
          "july","august","september","october","november","december"]

# ── Supabase ──────────────────────────────────────────────────────────────────

def get_db():
    return create_client(os.environ["SUPABASE_URL"], os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"])

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
            raw_p = m.get("outcomePrices", [])
            raw_o = m.get("outcomes", [])
            prices   = json.loads(raw_p) if isinstance(raw_p, str) else raw_p
            outcomes = json.loads(raw_o) if isinstance(raw_o, str) else raw_o
            if not prices or not outcomes:
                return None
            yes_price = next((float(p) for o, p in zip(outcomes, prices) if o.lower() == "yes"), None)
            if yes_price is None:
                return None
            closed   = m.get("closed", False)
            resolved = m.get("resolved", False)

            # Si fermé et prix ambigu (CLOB bloqué) → lire le vrai prix depuis /events
            if (closed or resolved) and 0.1 < yes_price < 0.9:
                event_slug = m.get("groupSlug") or m.get("slug", "")
                if event_slug:
                    try:
                        re2 = requests.get(f"{GAMMA_API}/events",
                                           params={"slug": event_slug},
                                           timeout=TIMEOUT)
                        if re2.status_code == 200:
                            events = re2.json()
                            if isinstance(events, list) and events:
                                for em in events[0].get("markets", []):
                                    if em.get("conditionId") == condition_id:
                                        raw_p2 = em.get("outcomePrices", [])
                                        raw_o2 = em.get("outcomes", [])
                                        p2 = json.loads(raw_p2) if isinstance(raw_p2, str) else raw_p2
                                        o2 = json.loads(raw_o2) if isinstance(raw_o2, str) else raw_o2
                                        yp2 = next((float(x) for oo, x in zip(o2, p2) if oo.lower() == "yes"), None)
                                        if yp2 is not None:
                                            yes_price = yp2
                    except Exception:
                        pass

            return {
                "condition_id": m.get("conditionId", ""),
                "yes_price":    yes_price,
                "closed":       closed,
                "resolved":     resolved,
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

def temp_range_from_question_celsius(question):
    """Retourne (low_c, high_c) en Celsius, ou None."""
    # Fahrenheit range: "between 60-61°F" ou "60 and 61°F"
    m = re.search(r'between (\d+)[-–and ]+(\d+)[°\s]*F', question, re.IGNORECASE)
    if m:
        low_c  = (int(m.group(1)) - 32) * 5 / 9
        high_c = (int(m.group(2)) - 32) * 5 / 9
        return low_c, high_c
    # Celsius exact: "be 25°C" → plage ±0.5
    m = re.search(r'be (\d+)°C', question)
    if m:
        t = int(m.group(1))
        return t - 0.5, t + 0.5
    return None

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
    final_price = 100 if resultat == "GAGNANT" else 0 if resultat == "PERDANT" else None
    update = {"resultat": resultat, "resolu_le": now}
    if final_price is not None:
        update["yes_price_actuel"] = final_price
    db.table(f"{ville['id']}_tracking").update(update).eq("condition_id", condition_id).execute()
    icon = "✅" if resultat == "GAGNANT" else "❌" if resultat == "PERDANT" else "🔚"
    log(f"  {icon} {resultat}", ville)

# ── Stats globales ────────────────────────────────────────────────────────────

def update_stats(db, ville, tracking):
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]

    # Charger stats actuelles pour ne jamais faire reculer les compteurs (protection purge tracking)
    try:
        cur = db.table(f"{ville['id']}_stats").select("gagnes,perdus,total_signaux").eq("id", ville["id"]).limit(1).execute().data
        cur = cur[0] if cur else {}
    except Exception:
        cur = {}

    final_gagnes  = max(len(gagnes),  cur.get("gagnes")         or 0)
    final_perdus  = max(len(perdus),  cur.get("perdus")         or 0)
    final_total   = max(len(tracking),cur.get("total_signaux")  or 0)
    final_resolus = final_gagnes + final_perdus
    taux          = round(final_gagnes / final_resolus * 100, 1) if final_resolus else None
    en_attente    = len([t for t in tracking if t["resultat"] is None])

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
        "total_signaux": final_total,
        "en_attente":    en_attente,
        "resolus":       final_resolus,
        "gagnes":        final_gagnes,
        "perdus":        final_perdus,
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

MONTHS_EN = ["january","february","march","april","may","june",
             "july","august","september","october","november","december"]

def build_event_slug(slug_prefix, date_marche):
    """Construit le slug événement depuis le préfixe ville + date_marche (dd/mm/yyyy)."""
    try:
        d, m, y = date_marche.split("/")
        month_name = MONTHS_EN[int(m) - 1]
        day = str(int(d))  # supprime le zéro initial
        return f"{slug_prefix}-on-{month_name}-{day}-{y}"
    except Exception:
        return None


def find_winner_in_event(event_slug):
    """
    Cherche le condition_id gagnant dans un événement Polymarket via /events.
    Retourne le condition_id avec YES > 0.55, ou None si pas encore résolu.
    N'utilise PAS le CLOB (bug: groupSlug retourne des slugs aléatoires).
    """
    if not event_slug:
        return None
    try:
        r = requests.get(f"{GAMMA_API}/events",
                         params={"slug": event_slug},
                         timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        events = r.json()
        if not (isinstance(events, list) and events):
            return None

        best_cid   = None
        best_price = 0.0
        for em in events[0].get("markets", []):
            raw_p    = em.get("outcomePrices", [])
            raw_o    = em.get("outcomes", [])
            prices   = json.loads(raw_p) if isinstance(raw_p, str) else raw_p
            outcomes = json.loads(raw_o) if isinstance(raw_o, str) else raw_o
            yp = next((float(p) for o, p in zip(outcomes, prices) if o.lower() == "yes"), None)
            if yp is not None and yp > best_price:
                best_price = yp
                best_cid   = em.get("conditionId", "")

        # Seuil 0.99 : élimine le CLOB bloqué à 51% ET les prix pré-résolution (75-98%)
        if best_cid and best_price > 0.99:
            return best_cid
        return None
    except Exception:
        return None


def check_resolved(db, ville, tracking):
    """
    Résolution via /events uniquement — ignore le bug CLOB (closed=False sur marchés résolus).
    1. Cherche le gagnant via /events (prix 0 ou 1 = marché résolu)
    2. Si trouvé → compare condition_id → GAGNANT ou PERDANT
    3. Si pas encore résolu (prix ~51%) → mise à jour du prix CLOB
    """
    pending = [t for t in tracking if t["resultat"] is None]
    if not pending:
        return
    for t in pending:
        # Construire le slug depuis le préfixe ville + date_marche (CLOB retourne des slugs faux)
        event_slug = build_event_slug(ville["slug_prefix"], t.get("date_marche", ""))
        winner_cid = find_winner_in_event(event_slug)

        if winner_cid is None:
            # Pas encore résolu — mettre à jour le prix depuis le CLOB
            m = fetch_market_by_id(t["condition_id"])
            if m is not None:
                update_price(db, ville, t["condition_id"], m["yes_price"])
            continue

        resultat = "GAGNANT" if winner_cid.lower() == t["condition_id"].lower() else "PERDANT"
        log(f"  {'✅' if resultat == 'GAGNANT' else '❌'} {resultat} — gagnant: {winner_cid[:14]}…", ville)
        resolve_signal(db, ville, t["condition_id"], resultat)

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
        res = db.table(f"{ville['id']}_rapports").select("id").order("created_at", desc=True).offset(288).limit(500).execute()
        ids = [r["id"] for r in (res.data or [])]
        if ids:
            db.table(f"{ville['id']}_rapports").delete().in_("id", ids).execute()
            log(f"  🧹 Rapports: {len(ids)} entrées supprimées", ville)
    except Exception as e:
        log(f"  ⚠️  Purge rapports: {e}", ville)

def purge_old_tracking(db, ville):
    """Supprime les signaux résolus de plus de 30 jours — les totaux sont déjà dans _stats."""
    try:
        cutoff = datetime.datetime.now(PARIS) - datetime.timedelta(days=30)
        rows = db.table(f"{ville['id']}_tracking").select("id,detecte_le,resultat").execute().data or []
        old_ids = []
        for r in rows:
            if not r.get("resultat"):
                continue
            d = (r.get("detecte_le") or "")[:10]
            try:
                if datetime.datetime.strptime(d, "%d/%m/%Y") < cutoff:
                    old_ids.append(r["id"])
            except Exception:
                pass
        if old_ids:
            db.table(f"{ville['id']}_tracking").delete().in_("id", old_ids).execute()
            log(f"  🧹 Tracking: {len(old_ids)} signaux anciens purgés", ville)
    except Exception as e:
        log(f"  ⚠️  Purge tracking: {e}", ville)

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
            flag  = "🔥" if m["yes_price"] >= 0.82 else ("📊" if m["yes_price"] >= 0.30 else "  ")
            temp  = m["question"].split("be ")[-1].split(" on")[0]
            t_int = temp_from_question(m["question"])
            match = " ← Open-Meteo" if (temp_actuel is not None and t_int == temp_actuel) else ""
            log(f"   {flag} {m['yes_price']*100:5.1f}%  {temp}{match}", ville)

        # 4. Signal dominant (1 seul par ville par jour)
        tracked_ids = {t["condition_id"] for t in tracking}
        pending_ids = {t["condition_id"] for t in tracking if t["resultat"] is None}

        candidates = [m for m in markets if m["yes_price"] >= 0.82 and not m["closed"] and not m["resolved"]]
        dominant   = max(candidates, key=lambda x: x["yes_price"]) if candidates else None

        if dominant:
            if dominant["condition_id"] not in tracked_ids:
                # Nouveau dominant — on le tracke sans toucher aux anciens signaux
                # (les anciens se résoudront naturellement via check_resolved quand le marché ferme)
                add_signal(db, ville, dominant, date_str)
                log(f"   🎯 Nouveau signal dominant !", ville)
            else:
                update_price(db, ville, dominant["condition_id"], dominant["yes_price"])
                log(f"   📊 Signal dominant inchangé ({dominant['yes_price']*100:.0f}%)", ville)
        else:
            for m in markets:
                if m["condition_id"] in pending_ids:
                    update_price(db, ville, m["condition_id"], m["yes_price"])
            log("   Aucun signal dominant (aucune option à 82%+)", ville)

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
        purge_old_rapports(db, ville)
        purge_old_tracking(db, ville)
    except Exception as e:
        log(f"⚠️  Rapport/purge: {e}", ville)


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
Le bot track les options YES >82% sur "highest temperature in [ville] on [date]".
Objectif : devenir rentable et exécuter de vrais trades.

════ MÉMOIRE — TES {len(past_analyses)} ANALYSES PRÉCÉDENTES ════
{memoire}

════ DONNÉES ACTUELLES ════
- Signaux total : {len(all_tracking)} | Résolus : {len(resolus)} | En attente : {len(all_tracking)-len(resolus)}
- Gagnés : {len(gagnes)} | Perdus : {len(perdus)} | Taux global : {taux_g}%
- Villes actives : {', '.join(v['label'] for v in villes if v['id'] not in VILLES_EXCLUES)}
- Villes exclues (taux <70%) : {', '.join(VILLES_EXCLUES)}
- Seuil actuel : 82% YES

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

def already_have_strategie_recently(db, minutes=60):
    """Évite de relancer si une analyse a été générée il y a moins de N minutes."""
    try:
        rows = db.table("strategie_analyses").select("created_at").order("created_at", desc=True).limit(1).execute().data
        if not rows:
            return False
        last = datetime.datetime.fromisoformat(rows[0]["created_at"].replace("Z", "+00:00"))
        now  = datetime.datetime.now(datetime.timezone.utc)
        return (now - last).total_seconds() < minutes * 60
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
    log(f"   Seuil : 82% YES | Scan : toutes les 15 min | Exclus : {', '.join(VILLES_EXCLUES)}")
    log("")

    while True:
        db = get_db()

        # Sync wallet toutes les 15 min
        try:
            sync_wallet(db)
        except Exception as e:
            log(f"⚠️  Wallet: {e}")

        for ville in VILLES:
            if ville["id"] in VILLES_EXCLUES:
                continue
            try:
                run_ville(db, ville)
            except Exception as e:
                log(f"❌ Erreur cycle: {e}", ville)
            log("")

        # Analyse stratégique : toutes les 15 min (juste avant que ProfitWeather lise)
        try:
            if not already_have_strategie_recently(db):
                log(f"🧠 Lancement analyse stratégique…")
                analyser_strategie(db, VILLES)
        except Exception as e:
            log(f"⚠️  Analyse stratégique: {e}")

        log(f"⏳ Prochain cycle dans 15 min\n")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    run()
