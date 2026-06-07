"""
agent_chengdu_cloud.py — Bot Chengdu température maximale (Railway + Supabase)
Tourne en continu sur Railway. Toutes les 15 minutes :
- Analyse les 11 options de température du lendemain à Chengdu (J+1 heure Chengdu)
- Récupère la température max prévue via Open-Meteo (station ZUUU approx.)
- Enregistre les signaux >80% dans Supabase
- Vérifie les résolutions des marchés précédents
- Met à jour les stats globales
"""

import os, re, json, time, datetime, requests
from zoneinfo import ZoneInfo
from supabase import create_client

PARIS   = ZoneInfo("Europe/Paris")
CHENGDU = ZoneInfo("Asia/Shanghai")   # UTC+8, pas de changement d'heure

def now_paris():
    return datetime.datetime.now(PARIS)

def now_chengdu():
    return datetime.datetime.now(CHENGDU)

GAMMA_API    = "https://gamma-api.polymarket.com"
TIMEOUT      = 15
INTERVAL     = 900  # 15 min

CHENGDU_LAT  = 30.578   # Chengdu Shuangliu Airport (ZUUU)
CHENGDU_LON  = 103.947

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

# ── Température réelle Chengdu (Open-Meteo, gratuit, pas de clé) ──────────────

def fetch_chengdu_temp(date):
    """
    Température max prévue/relevée à ZUUU via Open-Meteo.
    Retourne un entier en °C (arrondi, comme Wunderground), ou None.
    """
    date_str = date.strftime("%Y-%m-%d")
    today_chengdu = now_chengdu().date()
    try:
        if date.date() >= today_chengdu:
            # Prévision (J+0, J+1, J+2)
            r = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude":     CHENGDU_LAT,
                    "longitude":    CHENGDU_LON,
                    "daily":        "temperature_2m_max",
                    "timezone":     "Asia/Shanghai",
                    "forecast_days": 3,
                },
                timeout=TIMEOUT,
            )
        else:
            # Historique (journées passées)
            r = requests.get(
                "https://archive-api.open-meteo.com/v1/era5",
                params={
                    "latitude":   CHENGDU_LAT,
                    "longitude":  CHENGDU_LON,
                    "daily":      "temperature_2m_max",
                    "timezone":   "Asia/Shanghai",
                    "start_date": date_str,
                    "end_date":   date_str,
                },
                timeout=TIMEOUT,
            )
        r.raise_for_status()
        data = r.json()
        for d, t in zip(data["daily"]["time"], data["daily"]["temperature_2m_max"]):
            if d == date_str and t is not None:
                return int(t)  # troncature comme Wunderground (23.9°C → 23°C, pas 24°C)
    except Exception as e:
        log(f"⚠️  Open-Meteo: {e}")
    return None

def temp_from_question(question):
    """Extrait la température en °C depuis la question Polymarket."""
    m = re.search(r'be (\d+)°C', question)
    return int(m.group(1)) if m else None

# ── Tracking Supabase ─────────────────────────────────────────────────────────

def load_tracking(db):
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
        if m is None:
            # Erreur réseau → skip, réessayer au prochain cycle
            log(f"  ⚠️  API indisponible pour {t['condition_id'][:16]}, skip")
            continue
        if m["closed"] or m["resolved"]:
            final = m["yes_price"]
            if final >= 0.95:
                resultat = "GAGNANT"
            elif final <= 0.05:
                resultat = "PERDANT"
            else:
                pct = round(final * 100, 1)
                resultat = f"TERMINÉ: {pct}%"
            resolve_signal(db, t["condition_id"], resultat)

            # Comparaison avec Open-Meteo au moment de la résolution
            temp_marche = temp_from_question(t["question"])
            if temp_marche is not None and resultat in ("GAGNANT", "PERDANT"):
                try:
                    d = datetime.datetime.strptime(t["date_marche"], "%d/%m/%Y")
                    date_dt = d.replace(tzinfo=CHENGDU)
                    temp_om = fetch_chengdu_temp(date_dt)
                    if temp_om is not None:
                        if temp_om == temp_marche and resultat == "GAGNANT":
                            log(f"  📡 Open-Meteo avait prévu {temp_om}°C → résolu GAGNANT à {temp_marche}°C ✅ STATION CORRECTE")
                        elif temp_om == temp_marche and resultat == "PERDANT":
                            log(f"  📡 Open-Meteo avait prévu {temp_om}°C → résolu PERDANT à {temp_marche}°C ⚠️ RATÉ (même temp)")
                        else:
                            log(f"  📡 Open-Meteo avait prévu {temp_om}°C → résolu {resultat} à {temp_marche}°C ❌ STATION INCORRECTE")
                except Exception:
                    pass
        else:
            update_price(db, t["condition_id"], m["yes_price"])

# ── Rapport cycle + purge ─────────────────────────────────────────────────────

def save_rapport(db, tracking, slug, temp_actuel=None):
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    row = {
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
    }
    db.table("chengdu_rapports").insert(row).execute()

def purge_old_rapports(db):
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
    today = now_paris().strftime("%d/%m/%Y")
    try:
        res = db.table("chengdu_resumes").select("id").eq("date", today).limit(1).execute()
        return bool(res.data)
    except Exception:
        return False

def build_open_meteo_bilan(tracking):
    """Pour chaque marché résolu GAGNANT/PERDANT, compare avec la prévision Open-Meteo."""
    resolus = [t for t in tracking if t["resultat"] in ("GAGNANT", "PERDANT")]
    if not resolus:
        return ""
    lines = []
    seen_dates = {}
    for t in resolus[-10:]:
        date_str_raw = t.get("date_marche", "")
        temp_marche  = temp_from_question(t["question"])
        if not date_str_raw or temp_marche is None:
            continue
        if date_str_raw not in seen_dates:
            try:
                d = datetime.datetime.strptime(date_str_raw, "%d/%m/%Y").replace(tzinfo=CHENGDU)
                seen_dates[date_str_raw] = fetch_chengdu_temp(d)
            except Exception:
                seen_dates[date_str_raw] = None
        temp_om = seen_dates[date_str_raw]
        if temp_om is None:
            continue
        match = (temp_om == temp_marche and t["resultat"] == "GAGNANT")
        verdict = "✅ STATION CORRECTE" if match else "❌ STATION INCORRECTE"
        lines.append(
            f"- {date_str_raw} | Open-Meteo prévoyait {temp_om}°C → résolu {t['resultat']} à {temp_marche}°C | {verdict}"
        )
    return "\n".join(lines)

def generate_daily_resume(tracking, temp_actuel=None):
    key = os.getenv("MISTRAL_API_KEY", "")
    if not key:
        return "MISTRAL_API_KEY manquante."
    resolus  = [t for t in tracking if t["resultat"] is not None]
    gagnes   = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus   = [t for t in resolus  if t["resultat"] == "PERDANT"]
    termines = [t for t in resolus  if t["resultat"] not in ("GAGNANT", "PERDANT")]
    taux     = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    lignes   = "\n".join(
        f"- {t['question'][:70]} | signalé à {t['yes_price_au_signal']}% | {t['resultat']}"
        for t in resolus[-15:]
    ) or "Aucun marché résolu."
    temp_line   = f"\nTempérature max prévue demain à Chengdu (Open-Meteo/ZUUU) : {temp_actuel}°C" if temp_actuel else ""
    om_bilan    = build_open_meteo_bilan(tracking)
    om_section  = f"\n\nBilan Open-Meteo vs résolutions réelles :\n{om_bilan}" if om_bilan else ""
    prompt = f"""Résume en 5 lignes max ces stats de paris sur la température à Chengdu (Polymarket, seuil 80%) :

Signaux: {len(tracking)} | Résolus: {len(resolus)} | Gagnés: {len(gagnes)} | Perdus (PERDANT): {len(perdus)} | Terminés ambigus: {len(termines)} | Taux victoire: {taux}%{temp_line}

Note: "TERMINÉ: X%" = marché fermé entre 5% et 95% (ambiguïté), ne pas compter comme perte.

Derniers résolus:
{lignes}{om_section}

Réponds en français, très court. Donne :
1. Le taux de réussite (sur GAGNANT/PERDANT uniquement)
2. Si la stratégie vaut le coup (oui/non, 1 phrase)
3. Si Open-Meteo a été fiable (oui/non, 1 phrase)
4. Un conseil pour demain"""
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

def save_resume(db, tracking, temp_actuel=None):
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    analyse = generate_daily_resume(tracking, temp_actuel)
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
    log("   Seuil : 80% YES | Scan : toutes les 15 min | Fuseau : Chengdu (UTC+8)")
    log("")

    while True:
        db  = get_db()
        now_p = now_paris()
        now_c = now_chengdu()

        # Date du marché : J+0 si encore ouvert sur Polymarket, sinon J+1 (heure Chengdu)
        today_c    = now_c.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_c = today_c + datetime.timedelta(days=1)

        # Vérifie si le marché du jour est encore ouvert
        _slug_today = slug_for(today_c)
        _, _mkts_j0 = fetch_event(_slug_today)
        _j0_open    = any(not m["closed"] and not m["resolved"] for m in _mkts_j0) if _mkts_j0 else False

        target   = today_c if _j0_open else tomorrow_c
        slug     = slug_for(target)
        date_str = target.strftime("%d/%m/%Y")

        log(f"── Cycle {now_p.strftime('%d/%m/%Y %H:%M')} (Chengdu: {now_c.strftime('%d/%m %H:%M')}) ──")
        if _j0_open:
            log(f"   Marché suivi : {slug}  (J+0 encore ouvert)")
        else:
            log(f"   Marché suivi : {slug}  (J+1)")

        # 1. Vérifier résolutions des marchés en attente
        log("Vérification des marchés résolus…")
        tracking = load_tracking(db)
        check_resolved(db, tracking)
        tracking = load_tracking(db)

        # 2. Température actuelle à Chengdu (Open-Meteo)
        temp_actuel = fetch_chengdu_temp(target)
        if temp_actuel is not None:
            log(f"   🌡️  Open-Meteo (ZUUU) : {temp_actuel}°C max prévu pour {date_str}")
        else:
            log("   🌡️  Open-Meteo : donnée indisponible")

        # 3. Fetch marché Chengdu (réutilise le fetch J+0 si applicable, sinon fetch J+1)
        log("Fetch marché Chengdu…")
        if _j0_open:
            event, markets = None, _mkts_j0
        else:
            event, markets = fetch_event(slug)

        if not markets:
            log("   ⚠️  Aucun marché trouvé")
        else:
            top = sorted(markets, key=lambda x: x["yes_price"], reverse=True)
            log(f"   {len(markets)} options | Top: {top[0]['question'].split('be ')[-1].split(' on')[0]} à {top[0]['yes_price']*100:.0f}%")

            for m in sorted(markets, key=lambda x: x["yes_price"], reverse=True):
                flag  = "🔥" if m["yes_price"] >= 0.80 else ("📊" if m["yes_price"] >= 0.30 else "  ")
                temp  = m["question"].split("be ")[-1].split(" on")[0]
                # Comparer avec la prévision Open-Meteo
                t_int = temp_from_question(m["question"])
                match = " ← Open-Meteo" if (temp_actuel is not None and t_int == temp_actuel) else ""
                log(f"   {flag} {m['yes_price']*100:5.1f}%  {temp}{match}")

            # 4. Nouveaux signaux >80% + mise à jour prix signaux en attente
            tracked_ids = {t["condition_id"] for t in tracking}
            pending_ids = {t["condition_id"] for t in tracking if t["resultat"] is None}
            new_signals = 0
            for m in markets:
                if m["condition_id"] not in tracked_ids and m["yes_price"] >= 0.80 and not m["closed"] and not m["resolved"]:
                    add_signal(db, m, date_str)
                    new_signals += 1
                elif m["condition_id"] in pending_ids:
                    update_price(db, m["condition_id"], m["yes_price"])

            if new_signals:
                log(f"   🎯 {new_signals} nouveau(x) signal(s) !")
            else:
                log("   Aucun nouveau signal (aucune option à 80%+)")

        # 5. Alerte si Open-Meteo et signaux trackés divergent
        if temp_actuel is not None:
            pending = [t for t in tracking if t["resultat"] is None]
            signal_temps = [temp_from_question(t["question"]) for t in pending]
            signal_temps = [x for x in signal_temps if x is not None]
            if signal_temps and temp_actuel not in signal_temps:
                log(f"   ⚠️  Open-Meteo ({temp_actuel}°C) ne correspond à aucun signal tracké {signal_temps}")
            elif signal_temps and temp_actuel in signal_temps:
                log(f"   ✅ Signal tracké {temp_actuel}°C = prévision Open-Meteo !")

        # 6. Mise à jour stats
        tracking = load_tracking(db)
        update_stats(db, tracking)

        resolus = [t for t in tracking if t["resultat"] is not None]
        gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
        perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]
        taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
        log(f"📊 Signaux:{len(tracking)} | Résolus:{len(resolus)} | ✅{len(gagnes)} ❌{len(perdus)} | Taux:{taux}%")

        # 7. Rapport cycle → chengdu_rapports
        try:
            save_rapport(db, tracking, slug, temp_actuel)
            if now_p.hour == 4 and now_p.minute < 15:
                purge_old_rapports(db)
        except Exception as e:
            log(f"⚠️  Rapport: {e}")

        # 8. Résumé 17h → chengdu_resumes
        if now_p.hour == 17 and now_p.minute < 15:
            if not already_have_resume_today(db):
                log("⏰ 17h00 — Génération du résumé quotidien…")
                try:
                    save_resume(db, tracking, temp_actuel)
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
