"""
fix_old_results.py — Migration one-shot

Relit tous les signaux (pending + PERDANT auto-marqués) et les résout
avec la nouvelle logique : compare le condition_id gagnant via /events.

Usage :
    python3 bot/fix_old_results.py
"""

import os, re, json, datetime, requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SB_URL  = os.getenv("SUPABASE_URL")
SB_KEY  = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
GAMMA   = "https://gamma-api.polymarket.com"
TIMEOUT = 8

MONTHS_EN = ["january","february","march","april","may","june",
             "july","august","september","october","november","december"]

# (ville_id, slug_prefix Polymarket)
VILLES = [
    ("chengdu",       "highest-temperature-in-chengdu"),
    ("seoul",         "highest-temperature-in-seoul"),
    ("hong_kong",     "highest-temperature-in-hong-kong"),
    ("nyc",           "highest-temperature-in-nyc"),
    ("london",        "highest-temperature-in-london"),
    ("tokyo",         "highest-temperature-in-tokyo"),
    ("atlanta",       "highest-temperature-in-atlanta"),
    ("seattle",       "highest-temperature-in-seattle"),
    ("miami",         "highest-temperature-in-miami"),
    ("singapore",     "highest-temperature-in-singapore"),
    ("madrid",        "highest-temperature-in-madrid"),
    ("shanghai",      "highest-temperature-in-shanghai"),
    ("los_angeles",   "highest-temperature-in-los-angeles"),
    ("guangzhou",     "highest-temperature-in-guangzhou"),
    ("mexico_city",   "highest-temperature-in-mexico-city"),
    ("amsterdam",     "highest-temperature-in-amsterdam"),
    ("paris",         "highest-temperature-in-paris"),
    ("toronto",       "highest-temperature-in-toronto"),
    ("chicago",       "highest-temperature-in-chicago"),
    ("denver",        "highest-temperature-in-denver"),
    ("houston",       "highest-temperature-in-houston"),
    ("taipei",        "highest-temperature-in-taipei"),
    ("beijing",       "highest-temperature-in-beijing"),
    ("san_francisco", "highest-temperature-in-san-francisco"),
    ("dallas",        "highest-temperature-in-dallas"),
]

db = create_client(SB_URL, SB_KEY)


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def build_event_slug(slug_prefix, date_marche):
    """Construit le slug événement depuis le préfixe ville + date_marche (dd/mm/yyyy)."""
    try:
        d, m, y = date_marche.split("/")
        month_name = MONTHS_EN[int(m) - 1]
        day = str(int(d))
        return f"{slug_prefix}-on-{month_name}-{day}-{y}"
    except Exception:
        return None


def find_winner(event_slug, condition_id_to_check=None):
    """
    Retourne le condition_id gagnant via /events (YES > 0.55), ou None si ambigu.
    N'utilise PAS le CLOB (bug: retourne des slugs aléatoires).
    """
    if not event_slug:
        return None
    try:
        r = requests.get(f"{GAMMA}/events", params={"slug": event_slug}, timeout=TIMEOUT)
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
        if best_cid and best_price > 0.55:
            return best_cid
        return None
    except Exception:
        return None


def fetch_current_price(condition_id):
    """Lit juste le prix actuel du marché depuis CLOB (pour mise à jour uniquement)."""
    try:
        r = requests.get(f"{GAMMA}/markets", params={"conditionId": condition_id}, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if not (isinstance(data, list) and data):
            return None
        m = data[0]
        raw_p    = m.get("outcomePrices", [])
        raw_o    = m.get("outcomes", [])
        prices   = json.loads(raw_p) if isinstance(raw_p, str) else raw_p
        outcomes = json.loads(raw_o) if isinstance(raw_o, str) else raw_o
        yp = next((float(p) for o, p in zip(outcomes, prices) if o.lower() == "yes"), None)
        return yp or 0.5
    except Exception:
        return None


def update_stats(ville_id, tracking):
    resolus = [t for t in tracking if t["resultat"] is not None]
    gagnes  = [t for t in resolus  if t["resultat"] == "GAGNANT"]
    perdus  = [t for t in resolus  if t["resultat"] == "PERDANT"]
    taux    = round(len(gagnes) / len(resolus) * 100, 1) if resolus else None
    # On essaie d'abord avec verdict, puis sans si la colonne n'existe pas
    payload = {
        "id":            ville_id,
        "total_signaux": len(tracking),
        "en_attente":    len(tracking) - len(resolus),
        "resolus":       len(resolus),
        "gagnes":        len(gagnes),
        "perdus":        len(perdus),
        "taux_victoire": taux,
        "updated_at":    datetime.datetime.now().isoformat(),
        "verdict": (
            "Stratégie rentable"     if taux is not None and taux >= 60 else
            "Stratégie à surveiller" if taux is not None and taux >= 50 else
            "Stratégie non rentable" if taux is not None else
            "En attente de données"
        ),
    }
    try:
        db.table(f"{ville_id}_stats").upsert(payload).execute()
    except Exception:
        payload.pop("verdict", None)
        db.table(f"{ville_id}_stats").upsert(payload).execute()
    return taux


def fix_ville(ville_id, slug_prefix):
    log(f"── {ville_id} ──")
    res = db.table(f"{ville_id}_tracking").select("*").limit(5000).execute()
    tracking = res.data or []
    if not tracking:
        log(f"  Aucun signal.")
        return

    # On retraite : pending + PERDANT (potentiellement auto-marqués par erreur)
    a_retraiter = [t for t in tracking if t["resultat"] is None or t["resultat"] == "PERDANT"]
    log(f"  {len(tracking)} signaux total — {len(a_retraiter)} à retraiter")

    modifies = 0
    for t in a_retraiter:
        cid = t["condition_id"]
        date_marche = t.get("date_marche", "")

        # Construire le slug depuis les données du tracking (CLOB retourne des slugs faux)
        event_slug = build_event_slug(slug_prefix, date_marche)
        if not event_slug:
            log(f"  ⚠️  Impossible de construire le slug pour {cid[:14]} (date_marche='{date_marche}')")
            continue

        winner_cid = find_winner(event_slug)

        if winner_cid is None:
            # Pas résolu via /events — marché encore ouvert ou prix ambigu
            yp = fetch_current_price(cid)
            update = {"yes_price_actuel": round((yp or 0.5) * 100, 1)}
            if t["resultat"] == "PERDANT":
                update["resultat"]  = None
                update["resolu_le"] = None
                log(f"  🔄 {cid[:14]}… PERDANT → pending (pas encore résolu, slug={event_slug})")
                modifies += 1
            db.table(f"{ville_id}_tracking").update(update).eq("condition_id", cid).execute()
            continue

        # Gagnant trouvé via /events
        nouveau = "GAGNANT" if winner_cid.lower() == cid.lower() else "PERDANT"
        ancien  = t["resultat"] or "pending"

        final_price = 100 if nouveau == "GAGNANT" else 0
        db.table(f"{ville_id}_tracking").update({
            "resultat":         nouveau,
            "yes_price_actuel": final_price,
            "resolu_le":        datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        }).eq("condition_id", cid).execute()

        icon = "✅" if nouveau == "GAGNANT" else "❌"
        log(f"  {icon} {cid[:14]}… {ancien} → {nouveau} (slug={event_slug})")
        if ancien != nouveau:
            modifies += 1

    # Mettre à jour les stats
    res2 = db.table(f"{ville_id}_tracking").select("*").limit(5000).execute()
    tracking_final = res2.data or []
    taux = update_stats(ville_id, tracking_final)
    resolus = [t for t in tracking_final if t["resultat"] is not None]
    gagnes  = [t for t in resolus if t["resultat"] == "GAGNANT"]
    log(f"  → {modifies} modifiés | taux: {taux}% ({len(gagnes)}G/{len(resolus)-len(gagnes)}P/{len(tracking_final)-len(resolus)} en attente)")


if __name__ == "__main__":
    log("=== Migration fix_old_results ===")
    for ville_id, slug_prefix in VILLES:
        try:
            fix_ville(ville_id, slug_prefix)
        except Exception as e:
            log(f"  ERREUR {ville_id}: {e}")
    log("=== Terminé ===")
