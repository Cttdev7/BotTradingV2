from __future__ import annotations

"""
loop_v2.py — ProfitWeather V2.0

Stratégie inspirée de sailor82 ($11→$5 272 en 3 semaines, win rate 86%) :
- Acheter NO sur fourchettes de température clairement hors de la prévision météo
- Améliorations vs sailor82 : ECMWF ensemble, filtre canicule, timing local, mises % du solde

Règle capitale des mises :
  bet = 2–5% du solde selon certitude → 9 gains à 22% couvrent 1 perte à 100%
  Jamais plus de 6% par trade, jamais plus de 25% du solde total exposé.
"""

import time
import re
import os
import json
import uuid
import datetime
from zoneinfo import ZoneInfo
import requests
from concurrent.futures import ThreadPoolExecutor
import pm_api as polymarket
import brain
import trader
import config
import weather_validator

BOT_ID           = "polyedge2"
INTERVAL_MINUTES = int(os.getenv("BOT_V2_INTERVAL", "5"))
IMPROVE_HOURS    = int(os.getenv("BOT_V2_IMPROVE_HOURS", "6"))
IMPROVE_INTERVAL = IMPROVE_HOURS * 60 * 60

SB_URL = os.getenv("SUPABASE_URL", "https://obqkqhlqlowxrxbyvktl.supabase.co")
SB_KEY = os.getenv("SUPABASE_KEY", "")

# ── Règles hard-codées ────────────────────────────────────────────────────────

MIN_NO_PRICE      = 0.80    # NO minimum 80¢ (relevé — sous 80¢ marge insuffisante)
MAX_NO_PRICE      = 0.95    # NO maximum 95¢ (au-dessus = marge trop faible)
MAX_EXPOSURE_PCT  = 1.0     # 100% du solde peut être exposé simultanément
MAX_BET_PCT       = 0.05    # jamais plus de 5% du solde sur 1 trade (réduit de 6%)
MIN_FORECAST_GAP  = 5.0     # écart minimum °F (relevé de 3 → 5 : on veut un signal clair)
MAX_ENSEMBLE_PROB = 30      # si ECMWF prédit >30% dans ce range → INTERDIT (durci de 40)
MAX_BAND_PROB     = 20      # band_prob max (durci de 30 → 20)
MAX_MODELS_SPREAD = 10.0    # °F — si modèles ECMWF divergent >10°F → trop incertain (durci)
MIN_VOLUME        = 2_000   # volume minimum USDC (relevé de 1000 → 2000 : marchés liquides)

NO_STOP_LOSS_PCT  = -0.20   # -20% → vente automatique (durci de -25%)
NO_TAKE_PROFIT    = 0.9999  # NO ≥ 99.99% → lock profit (quasi-résolution)

# Villes à exclure si canicule ECMWF > 30% (durci de 35%)
HEATWAVE_RISK_CITIES = {"nyc", "houston", "austin", "miami", "san-francisco"}

# Fenêtre de temps optimale : refuser si trop tôt (>20h restantes) ou trop tard (<1h)
MIN_HOURS_REMAINING = 1.0   # marché qui ferme dans moins d'1h → liquidité trop faible
MAX_HOURS_REMAINING = 20.0  # marché qui ferme dans plus de 20h → trop d'incertitude

# ── Helpers ───────────────────────────────────────────────────────────────────

def _hours_remaining(end_date_iso: str) -> float | None:
    """Retourne les heures restantes avant clôture du marché, ou None si inconnu."""
    if not end_date_iso:
        return None
    try:
        # Supporte "2026-06-16T23:59:00Z" et "2026-06-16T23:59:00+00:00"
        end = datetime.datetime.fromisoformat(end_date_iso.replace("Z", "+00:00"))
        now = datetime.datetime.now(ZoneInfo("UTC"))
        delta = (end - now).total_seconds() / 3600
        return round(delta, 1)
    except Exception:
        return None

# ── Supabase helpers ──────────────────────────────────────────────────────────

def _sb_headers():
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }

def load_strategy() -> dict:
    try:
        r = requests.get(
            f"{SB_URL}/rest/v1/bot_strategies",
            params={"bot_id": f"eq.{BOT_ID}", "limit": "1"},
            headers=_sb_headers(), timeout=5,
        )
        if r.status_code == 200 and r.json():
            return r.json()[0]
    except Exception as e:
        log(f"⚠️  load_strategy : {e}")
    return {
        "bot_id":  BOT_ID,
        "enabled": True,
        "version": 1,
        "prompt": (
            "Acheter NO sur les fourchettes de température US clairement hors de la prévision météo.\n"
            "Critères : NO 0.70–0.95 · band_prob < 30% · écart prévision/fourchette ≥ 3°F · après 14h locale.\n"
            "Éviter : NYC/Houston/Austin si canicule possible · ranges proches de la prévision.\n"
            "Mises : calculées automatiquement en % du solde selon certitude."
        ),
    }

def save_strategy(strategy: dict):
    try:
        requests.post(
            f"{SB_URL}/rest/v1/bot_strategies",
            json={**strategy, "bot_id": BOT_ID, "updated_at": datetime.datetime.now().isoformat()},
            headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates"},
            timeout=5,
        )
    except Exception as e:
        log(f"⚠️  save_strategy : {e}")

def load_deko_trades(hours: int = 4) -> set:
    """Retourne les condition_id des marchés récemment achetés NO par sailor82."""
    try:
        since = (datetime.datetime.utcnow() - datetime.timedelta(hours=hours)).isoformat()
        r = requests.get(
            f"{SB_URL}/rest/v1/deko_trades",
            params={"outcome": "eq.NO", "created_at": f"gte.{since}", "select": "condition_id"},
            headers=_sb_headers(), timeout=5,
        )
        if r.status_code == 200:
            return {t["condition_id"] for t in r.json() if t.get("condition_id")}
    except Exception as e:
        log(f"⚠️  load_deko : {e}")
    return set()

def load_history() -> list:
    try:
        r = requests.get(
            f"{SB_URL}/rest/v1/trade_history",
            params={"bot_id": f"eq.{BOT_ID}", "order": "created_at.asc", "limit": "500"},
            headers=_sb_headers(), timeout=5,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log(f"⚠️  load_history : {e}")
    return []

def insert_trade(trade: dict):
    try:
        r = requests.post(
            f"{SB_URL}/rest/v1/trade_history",
            json=trade,
            headers={**_sb_headers(), "Prefer": "return=minimal"},
            timeout=5,
        )
        if r.status_code not in (200, 201):
            log(f"⚠️  insert_trade erreur {r.status_code} : {r.text[:200]}")
    except Exception as e:
        log(f"⚠️  insert_trade : {e}")

def update_trade_pnl(trade_id: str, pnl: float):
    try:
        requests.patch(
            f"{SB_URL}/rest/v1/trade_history",
            params={"id": f"eq.{trade_id}"},
            json={"pnl": pnl},
            headers={**_sb_headers(), "Prefer": "return=minimal"},
            timeout=5,
        )
    except Exception as e:
        log(f"⚠️  update_trade_pnl : {e}")

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[V2][{ts}] {msg}", flush=True)

def _stats(history: list) -> str:
    wins   = len([t for t in history if (t.get("pnl") or 0) > 0])
    losses = len([t for t in history if (t.get("pnl") or 0) < 0])
    pnl    = sum(t.get("pnl") or 0 for t in history)
    return f"{wins}W / {losses}L / P&L ${pnl:.2f}"

def _get_current_no_price(condition_id: str) -> float | None:
    try:
        r = requests.get(f"https://clob.polymarket.com/markets/{condition_id}", timeout=8)
        if r.status_code != 200:
            return None
        for token in r.json().get("tokens", []):
            if token.get("outcome", "").lower() == "no":
                return float(token.get("price", 0))
    except Exception:
        pass
    return None

def _calc_bet(usdc: float, certainty: str) -> float:
    """
    Mise en % du solde selon la certitude.

    Math : NO moyen à 82¢ → gain 22% par win.
    9 wins × 22% × mise = 198% ≫ 100% perte → les 9 gains couvrent toujours 1 perte.
    On reste conservateur : max 6% du solde par trade, max 25% total exposé.

      high   (band_prob<10%, écart>10°F) → 5% du solde
      medium (band_prob<20%, écart>5°F)  → 3% du solde
      low    (band_prob<30%, écart>3°F)  → 2% du solde
    """
    pct = {"high": 0.05, "medium": 0.03, "low": 0.02}.get(certainty, 0.025)
    raw = usdc * pct
    min_bet = max(1.5, usdc * 0.02)    # au moins 2% du solde (ou $1.5)
    max_bet = min(usdc * MAX_BET_PCT, 5.0)  # jamais plus de 5$ par trade
    return round(max(min_bet, min(raw, max_bet)), 2)

def _parse_range_bounds(question: str) -> tuple[float, float] | None:
    """Extrait les bornes (low, high) depuis 'be between X and Y' ou 'X-YF'."""
    m = re.search(r'between\s+([\d.]+)\s+and\s+([\d.]+)', question, re.I)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r'([\d.]+)[–\-]([\d.]+)\s*[°]?[FC]', question)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None

# ── Stop-loss / Take-profit ───────────────────────────────────────────────────

def check_stop_loss(history: list):
    open_trades = [t for t in history if t.get("pnl") is None]
    if not open_trades:
        return

    for t in open_trades:
        if t.get("sym", "").lower() != "no":
            continue
        entry_price = float(t.get("price") or 0)
        if entry_price <= 0:
            continue
        current_price = _get_current_no_price(t.get("condition_id", ""))
        if current_price is None:
            continue

        amount_usdc = float(t.get("amount_usdc") or 0)
        pnl_pct = (current_price - entry_price) / entry_price

        if current_price >= NO_TAKE_PROFIT:
            tokens_held = amount_usdc / entry_price
            pnl_usd     = round(tokens_held * (current_price - entry_price), 2)
            log(f"  💰 TAKE-PROFIT NO {t.get('condition_id','')[:12]}… | {current_price:.4f} | +${pnl_usd:.2f}")
            if current_price >= 1.0:
                update_trade_pnl(t["id"], pnl_usd)
            else:
                try:
                    result = trader.place_market_order(
                        condition_id=t["condition_id"], outcome="No",
                        side="sell", amount_usdc=tokens_held,
                    )
                    taking   = float(result.get("taking_amount") or 0)
                    real_pnl = round(taking - amount_usdc, 2) if taking else pnl_usd
                    update_trade_pnl(t["id"], real_pnl)
                    log(f"    ✅ Vendu +${real_pnl:.2f}")
                except Exception as e:
                    if "resting liquidity" in str(e).lower():
                        log(f"    ⏳ Pas de liquidité — réessai au prochain cycle")
                    else:
                        log(f"    ❌ {e}")
            continue

        if pnl_pct >= NO_STOP_LOSS_PCT:
            continue

        tokens_held = amount_usdc / entry_price
        pnl_usd     = round(tokens_held * (current_price - entry_price), 2)
        log(f"  🛑 STOP-LOSS NO {t.get('condition_id','')[:12]}… | {entry_price:.3f}→{current_price:.3f} ({pnl_pct*100:+.1f}%) | ${pnl_usd:.2f}")
        if current_price <= 0.005:
            update_trade_pnl(t["id"], pnl_usd)
            continue
        try:
            result = trader.place_market_order(
                condition_id=t["condition_id"], outcome="No",
                side="sell", amount_usdc=tokens_held,
            )
            taking   = float(result.get("taking_amount") or 0)
            real_pnl = round(taking - amount_usdc, 2) if taking else pnl_usd
            update_trade_pnl(t["id"], real_pnl)
            log(f"    ✅ Vendu ${real_pnl:.2f}")
        except Exception as e:
            if "resting liquidity" in str(e).lower():
                log(f"    ⏳ Pas de liquidité — réessai au prochain cycle")
            else:
                log(f"    ❌ {e}")

# ── Filtres pré-Claude ────────────────────────────────────────────────────────

def _prefilter(markets: list, history: list, usdc: float, deko_cids: set = None) -> list:
    """
    Applique les filtres hard-codés AVANT de passer à Claude.
    Retourne uniquement les marchés qui méritent d'être analysés.
    deko_cids : condition_ids récemment tradés par sailor82 (signal bonus).
    """
    open_cids    = {t.get("condition_id") for t in history if t.get("pnl") is None}
    open_cities  = {t.get("city", "") for t in history if t.get("pnl") is None}
    total_exposed = sum(float(t.get("amount_usdc") or 0) for t in history if t.get("pnl") is None)
    deko_cids = deko_cids or set()

    kept = []
    for m in markets:
        cid   = m.get("condition_id", "")
        city  = m.get("city", "")
        q     = m.get("question", "")
        vol   = float(m.get("volume") or 0)
        tokens  = m.get("tokens", [])
        no_price = next((t.get("price", 0) for t in tokens if t.get("outcome") == "No"), 0)
        local_hour = m.get("local_hour")
        day_offset = m.get("day_offset", 0)
        wx   = m.get("weather_ctx", {})

        # Déjà en position ou ville déjà jouée aujourd'hui
        if cid in open_cids:
            continue
        if city in open_cities:
            continue

        # Exposition totale dépassée
        if total_exposed >= usdc * MAX_EXPOSURE_PCT:
            log(f"  ⛔ Exposition max atteinte ({total_exposed:.0f}$ / {usdc*MAX_EXPOSURE_PCT:.0f}$)")
            break

        # Volume minimum
        if vol < MIN_VOLUME:
            continue

        # Temps restant avant clôture
        hours_left = _hours_remaining(m.get("end_date_iso", ""))
        if hours_left is not None:
            if hours_left < MIN_HOURS_REMAINING:
                label = "déjà fermé" if hours_left < 0 else f"ferme dans {hours_left:.1f}h"
                log(f"  ⏰ {city} {label} — ignoré")
                continue
            if hours_left > MAX_HOURS_REMAINING:
                log(f"  ⏰ {city} ferme dans {hours_left:.1f}h — trop tôt, ignoré")
                continue
            m["_hours_left"] = hours_left  # transmis à Claude pour contexte

        # Prix NO dans la zone cible
        if not (MIN_NO_PRICE <= no_price <= MAX_NO_PRICE):
            continue

        # Parse les bornes une seule fois (réutilisé pour remaining_max ET gap)
        bounds = _parse_range_bounds(q)

        # Trajectoire temps réel — si remaining_max peut atteindre la fourchette → trop risqué
        if bounds and wx.get("remaining_max") is not None:
            low, high = bounds
            remaining_max = wx["remaining_max"]
            if remaining_max >= low:
                log(f"  🌡️  {city} remaining_max {remaining_max}°F ≥ fourchette basse {low}°F — trop risqué")
                continue
            # Si max déjà observé est très au-dessus de la fourchette → signal fort NO
            max_today = wx.get("max_today")
            if max_today is not None and max_today > high + 3:
                m["_no_confirmed"] = True  # marché déjà gagné en temps réel

        # band_prob trop élevé → trop probable d'être dans ce range
        # Si weather_ctx manque (enrichissement raté), on refuse le trade par sécurité
        band_prob = wx.get("band_prob")
        if band_prob is None or band_prob > MAX_BAND_PROB:
            continue

        # Spread trop élevé → modèles en désaccord → température imprévisible
        models_spread = wx.get("models_spread")
        if models_spread is not None and models_spread > MAX_MODELS_SPREAD:
            log(f"  📉 Spread trop élevé {city} ({models_spread}°F > {MAX_MODELS_SPREAD}°F) — ignoré")
            continue

        # Filtre canicule : si ECMWF prédit >MAX_ENSEMBLE_PROB% d'atteindre un range chaud
        ensemble_prob = wx.get("ensemble_prob")
        if city in HEATWAVE_RISK_CITIES and ensemble_prob is not None and ensemble_prob > MAX_ENSEMBLE_PROB:
            log(f"  🌡️  Canicule détectée {city} (ensemble_prob={ensemble_prob}%) — ignoré")
            continue

        # Écart entre prévision météo et fourchette du marché
        forecast_mean = wx.get("models_avg") or wx.get("current_temp")
        if forecast_mean is not None and bounds:
            low, high = bounds
            gap = min(abs(forecast_mean - low), abs(forecast_mean - high))
            if gap < MIN_FORECAST_GAP:
                continue   # trop proche du range → trop risqué
            m["_gap"] = gap
        else:
            m["_gap"] = 0

        # Signal Deko : sailor82 est aussi positionné NO sur ce marché
        if cid in deko_cids:
            m["_deko"] = True
            log(f"  🔍 Signal Deko : sailor82 est NO sur {city} ({cid[:12]}…)")

        kept.append(m)

    return kept

# ── Cycle principal ───────────────────────────────────────────────────────────

def run_cycle():
    log("─── Nouveau cycle V2 ───")

    strategy = load_strategy()
    if not strategy.get("enabled"):
        log("Bot V2 désactivé")
        return
    if not strategy.get("prompt", "").strip():
        log("Aucun prompt — configure la stratégie dans le dashboard")
        return

    # Résolution des trades ouverts
    history = load_history()
    open_trades = [t for t in history if t.get("pnl") is None]
    if open_trades:
        log(f"Vérification {len(open_trades)} trades ouverts…")
        updated = brain.check_market_outcomes(history)
        for t_new in updated:
            t_old = next((t for t in history if t.get("id") == t_new.get("id")), None)
            if t_old and t_old.get("pnl") is None and t_new.get("pnl") is not None:
                update_trade_pnl(t_new["id"], t_new["pnl"])
                log(f"  ✅ {t_new['id'][:8]}… résolu — P&L ${t_new['pnl']:.2f}")
        history = updated

    # Stop-loss
    log(f"🛡️  Stop-loss ({NO_STOP_LOSS_PCT*100:.0f}%)…")
    check_stop_loss(history)
    history = load_history()

    # Marchés Polymarket
    try:
        markets = polymarket.get_weather_markets()
    except Exception as e:
        log(f"Erreur marchés : {e}")
        return

    # Solde
    usdc = float(os.getenv("BALANCE_USDC", "0") or "0")
    if usdc < 1:
        try:
            usdc = polymarket.get_balance().get("usdc", 0)
        except Exception:
            usdc = 0

    if trader.DRY_RUN:
        if usdc < 1:
            usdc = 100.0
        log(f"[SIM] Solde fictif ${usdc:.2f} | {_stats(history)}")
    else:
        if usdc < 1:
            log("⚠️  Solde illisible — cycle annulé")
            return
        log(f"💰 ${usdc:.2f} USDC | {_stats(history)}")

    # Heure locale par ville
    for m in markets:
        m['local_hour'] = weather_validator.get_city_local_hour(m.get('city', ''))

    # Enrichissement météo
    def _enrich(m):
        try:
            ctx = weather_validator.get_rich_weather_context(
                city_slug=m.get('city', ''),
                question=m.get('question', ''),
                slug=m.get('slug', ''),
            )
            if ctx:
                m['weather_ctx'] = ctx
        except Exception:
            pass
        return m

    log("🌤️  Enrichissement météo…")
    with ThreadPoolExecutor(max_workers=8) as pool:
        markets = list(pool.map(_enrich, markets))

    # Trades récents de sailor82 (signal bonus)
    deko_cids = load_deko_trades(hours=4)
    if deko_cids:
        log(f"🔍 {len(deko_cids)} trade(s) récent(s) de sailor82 chargés")

    # Pré-filtrage hard-codé
    candidates = _prefilter(markets, history, usdc, deko_cids=deko_cids)
    log(f"📊 {len(candidates)}/{len(markets)} marchés passent les filtres")

    if not candidates:
        log("Aucun candidat après filtrage")
        return

    if usdc < 1.0:
        log(f"💤 Solde insuffisant (${usdc:.2f})")
        return

    # Décision Claude
    try:
        decisions = brain.decide_v2(strategy, candidates, history, usdc)
        log(f"Claude V2 : {len(decisions)} décision(s)")
    except Exception as e:
        log(f"Erreur Claude : {e}")
        return

    if not decisions:
        log("Aucune opportunité NO détectée")
        return

    # Déduplication
    open_cids = {t.get("condition_id") for t in history if t.get("pnl") is None}
    decisions = [d for d in decisions if d.get("condition_id") not in open_cids]

    market_lookup  = {m["condition_id"]: m for m in candidates}
    total_exposed  = sum(float(t.get("amount_usdc") or 0) for t in history if t.get("pnl") is None)
    traded_cities  = set()  # 1 trade max par ville par cycle

    for d in decisions:
        if d.get("action") != "buy" or d.get("outcome") not in ("No", "NO"):
            continue

        cid       = d.get("condition_id", "")
        certainty = d.get("certainty", "low")
        mkt       = market_lookup.get(cid, {})
        city      = mkt.get("city", "")

        # Boost certitude si sailor82 est aussi sur ce trade (avant le filtre high)
        if mkt.get("_deko"):
            old = certainty
            certainty = {"low": "medium", "medium": "high"}.get(certainty, certainty)
            if certainty != old:
                log(f"  🔍 Deko boost : certitude {old} → {certainty} (sailor82 confirme)")

        # On joue UNIQUEMENT les signaux high — pas de medium ni low
        if certainty != "high":
            log(f"  ⏭️  {city} certitude={certainty} — ignoré (on veut uniquement high)")
            continue

        # 1 trade max par ville par cycle
        if city in traded_cities:
            log(f"  ⛔ {city} déjà tradé ce cycle — ignoré")
            continue

        # Vérif exposition globale
        if total_exposed >= usdc * MAX_EXPOSURE_PCT:
            log(f"  ⛔ Exposition max atteinte — stop")
            break

        # Calcul de la mise NO basée sur % du solde
        amount = _calc_bet(usdc, certainty)
        log(f"  💰 Mise calculée : ${amount:.2f} ({certainty}) sur solde ${usdc:.2f}")

        # Double vérif prix NO en temps réel
        price_t1 = _get_current_no_price(cid)
        if price_t1 is None:
            log(f"  🚫 CLOB inaccessible — annulé")
            continue
        if not (MIN_NO_PRICE <= price_t1 <= MAX_NO_PRICE):
            log(f"  🚫 Prix NO T1 {price_t1:.3f} hors zone [{MIN_NO_PRICE}-{MAX_NO_PRICE}] — annulé")
            continue

        no_estimate = float(d.get("no_price", 0) or 0)
        if no_estimate > 0 and abs(price_t1 - no_estimate) / no_estimate > 0.10:
            log(f"  🚫 Écart T1 trop élevé : estimé {no_estimate:.3f}, réel {price_t1:.3f} — annulé")
            continue

        time.sleep(4)
        price_t2 = _get_current_no_price(cid)
        if price_t2 is None or not (MIN_NO_PRICE <= price_t2 <= MAX_NO_PRICE):
            log(f"  🚫 Prix T2 hors zone — annulé")
            continue
        if price_t1 - price_t2 > 0.02:
            log(f"  🚫 NO en chute : {price_t1:.3f}→{price_t2:.3f} — annulé")
            continue
        log(f"  ✅ Prix NO stable T1={price_t1:.3f} T2={price_t2:.3f}")
        d["no_price"] = price_t2

        try:
            log(f"→ BUY NO | {cid[:12]}… | ${amount:.2f} [{certainty}] | {d.get('reason','')}")
            result = trader.place_market_order(
                condition_id=cid,
                outcome="No",
                side="buy",
                amount_usdc=amount,
            )
            if not result.get("ok") and not result.get("dry_run"):
                log(f"  ⚠️  Ordre rejeté")
                continue
            trade = {
                "id":           str(uuid.uuid4()),
                "bot_id":       BOT_ID,
                "time":         datetime.datetime.now().isoformat(),
                "market":       "polymarket",
                "condition_id": cid,
                "city":         mkt.get("city", ""),
                "sym":          "No",
                "side":         "buy",
                "amount_usdc":  amount,
                "price":        float(result.get("price", 0) or price_t2),
                "reason":       d.get("reason", ""),
                "result":       result,
                "pnl":          None,
            }
            insert_trade(trade)
            total_exposed += amount
            usdc -= amount
            traded_cities.add(city)
            log(f"  ✅ Enregistré | Exposition : ${total_exposed:.2f}")
        except Exception as e:
            log(f"  ❌ Erreur ordre : {e}")

# ── Auto-amélioration ─────────────────────────────────────────────────────────

def run_improvement():
    log("═══ Auto-amélioration V2 ═══")
    strategy = load_strategy()
    history  = load_history()
    resolved = [t for t in history if t.get("pnl") is not None]
    if len(resolved) < 5:
        log(f"Pas assez de trades résolus ({len(resolved)}/5)")
        return
    try:
        result = brain.improve_strategy(strategy, history)
        if result.get("new_prompt") == strategy.get("prompt"):
            log("Stratégie inchangée")
            return
        strategy["prompt"]        = result["new_prompt"]
        strategy["version"]       = result.get("version", 1)
        strategy["last_improved"] = datetime.datetime.now().isoformat()
        strategy["last_reason"]   = result.get("reason", "")
        save_strategy(strategy)
        log(f"✅ v{strategy['version']} — {result.get('reason','')}")
    except Exception as e:
        log(f"Erreur auto-amélioration : {e}")

# ── Point d'entrée ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    config.validate()
    log(f"🌤️  ProfitWeather V2.0 démarré — cycle toutes les {INTERVAL_MINUTES} min")
    log(f"   Stratégie : NO sur fourchettes température (70–95¢)")
    log(f"   Mises : 2–5% du solde selon certitude (max {MAX_BET_PCT*100:.0f}% par trade, max {MAX_EXPOSURE_PCT*100:.0f}% exposé)")
    log(f"   Mode : {'SIMULATION (DRY_RUN)' if trader.DRY_RUN else '⚠️  TRADING RÉEL'}")
    log(f"   Wallet : {config.WALLET_ADDRESS[:10]}…")

    last_improve = time.time()
    while True:
        try:
            run_cycle()
            if time.time() - last_improve > IMPROVE_INTERVAL:
                run_improvement()
                last_improve = time.time()
        except KeyboardInterrupt:
            log("Bot V2 arrêté")
            break
        except Exception as e:
            import traceback
            log(f"Erreur : {e}\n{traceback.format_exc()}")
        log(f"Prochain cycle dans {INTERVAL_MINUTES} min…")
        time.sleep(INTERVAL_MINUTES * 60)
