from __future__ import annotations

"""
loop_v2.py — ProfitWeather V2.0

Stratégie sailor82 : acheter NO sur les marchés de fourchettes de température US
quand NO se trade à 70–95 cents.

Logique : si la météo prédit clairement hors d'une fourchette étroite, NO vaut presque 1.
Ex : SF prévu à 80°F, fourchette 66-67°F → NO à 0.82 = argent quasi-gratuit.
"""

import time
import os
import json
import uuid
import datetime
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

# Limites hard-codées pour NO trades
MIN_NO_PRICE  = 0.70   # NO minimum 70 cents
MAX_NO_PRICE  = 0.95   # NO maximum 95 cents (marge trop faible au-dessus)
MIN_TRADE     = 20.0   # $20 minimum par trade
MAX_TRADE     = 1400.0 # $1 400 maximum par trade

NO_STOP_LOSS_PCT   = -0.20  # -20% → vente automatique
NO_TAKE_PROFIT     = 0.99   # NO ≥ 99% → lock profit

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
            "STRATÉGIE V2 : acheter NO sur les marchés de fourchettes de température US "
            "quand NO est à 70–95 cents et que la météo confirme que la temp sera hors range.\n\n"
            "Critères : NO 0.70–0.95 · fourchette ECMWF < 30% · écart évident entre prévision et fourchette.\n"
            "Taille : 15–25% du solde selon certitude. Min $20, max $1 400.\n"
            "Villes US préférées : san-francisco, miami, nyc, houston, atlanta, los-angeles."
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
        requests.post(
            f"{SB_URL}/rest/v1/trade_history",
            json=trade,
            headers={**_sb_headers(), "Prefer": "return=minimal"},
            timeout=5,
        )
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
    return f"{wins}W / {losses}L / P&L total ${pnl:.2f}"

def _get_current_no_price(condition_id: str) -> float | None:
    """Récupère le prix NO actuel depuis le CLOB."""
    try:
        r = requests.get(
            f"https://clob.polymarket.com/markets/{condition_id}",
            timeout=8,
        )
        if r.status_code != 200:
            return None
        for token in r.json().get("tokens", []):
            if token.get("outcome", "").lower() == "no":
                return float(token.get("price", 0))
    except Exception:
        pass
    return None

# ── Stop-loss / Take-profit sur positions NO ──────────────────────────────────

def check_stop_loss(history: list):
    open_trades = [t for t in history if t.get("pnl") is None]
    if not open_trades:
        return

    for t in open_trades:
        entry_price = float(t.get("price") or 0)
        if entry_price <= 0:
            continue

        current_price = _get_current_no_price(t.get("condition_id", ""))
        if current_price is None:
            continue

        amount_usdc = float(t.get("amount_usdc") or 0)
        pnl_pct = (current_price - entry_price) / entry_price

        # Take-profit : NO ≥ 99%
        if current_price >= NO_TAKE_PROFIT:
            tokens_held = amount_usdc / entry_price
            pnl_usd     = round(tokens_held * (current_price - entry_price), 2)
            log(f"  💰 TAKE-PROFIT NO {t.get('condition_id','')[:12]}… | prix {current_price:.4f} | P&L estimé +${pnl_usd:.2f}")
            if current_price >= 1.0:
                update_trade_pnl(t["id"], pnl_usd)
                log(f"    ✅ Résolu à 1.0 — P&L enregistré +${pnl_usd:.2f}")
            else:
                try:
                    result = trader.place_market_order(
                        condition_id=t["condition_id"],
                        outcome="No",
                        side="sell",
                        amount_usdc=tokens_held,
                    )
                    if result.get("ok") or result.get("dry_run"):
                        taking   = float(result.get("taking_amount") or 0)
                        real_pnl = round(taking - amount_usdc, 2) if taking else pnl_usd
                        update_trade_pnl(t["id"], real_pnl)
                        log(f"    ✅ Vendu — P&L réel +${real_pnl:.2f}")
                except Exception as e:
                    err = str(e)
                    if "resting liquidity" in err.lower() or "not enough balance" in err.lower():
                        update_trade_pnl(t["id"], pnl_usd)
                        log(f"    ✅ Marché fermé — P&L enregistré +${pnl_usd:.2f}")
                    else:
                        log(f"    ❌ Erreur vente take-profit : {e}")
            continue

        if pnl_pct >= NO_STOP_LOSS_PCT:
            continue

        # Stop-loss déclenché
        tokens_held = amount_usdc / entry_price
        pnl_usd     = round(tokens_held * (current_price - entry_price), 2)
        log(f"  🛑 STOP-LOSS NO {t.get('condition_id','')[:12]}… | entrée {entry_price:.3f} → actuel {current_price:.3f} ({pnl_pct*100:+.1f}%) | P&L estimé ${pnl_usd:.2f}")
        if current_price <= 0.005:
            update_trade_pnl(t["id"], pnl_usd)
            log(f"    ✅ Résolu à YES=1 — NO perdu, P&L ${pnl_usd:.2f}")
            continue
        try:
            result = trader.place_market_order(
                condition_id=t["condition_id"],
                outcome="No",
                side="sell",
                amount_usdc=tokens_held,
            )
            if result.get("ok") or result.get("dry_run"):
                taking   = float(result.get("taking_amount") or 0)
                real_pnl = round(taking - amount_usdc, 2) if taking else pnl_usd
                update_trade_pnl(t["id"], real_pnl)
                log(f"    ✅ Vendu — P&L réel ${real_pnl:.2f}")
        except Exception as e:
            err = str(e)
            if "resting liquidity" in err.lower() or "not enough balance" in err.lower():
                update_trade_pnl(t["id"], pnl_usd)
                log(f"    ✅ Marché fermé — perte enregistrée ${pnl_usd:.2f}")
            else:
                log(f"    ❌ Erreur stop-loss : {e}")

# ── Cycle principal ───────────────────────────────────────────────────────────

def run_cycle():
    log("─── Nouveau cycle V2 ───")

    strategy = load_strategy()
    if not strategy.get("enabled"):
        log("Bot V2 désactivé — active-le dans le dashboard")
        return
    if not strategy.get("prompt", "").strip():
        log("Aucun prompt — configure la stratégie dans le dashboard")
        return

    history     = load_history()
    open_trades = [t for t in history if t.get("pnl") is None]
    if open_trades:
        log(f"Vérification outcomes de {len(open_trades)} trades ouverts…")
        updated = brain.check_market_outcomes(history)
        for t_new in updated:
            t_old = next((t for t in history if t.get("id") == t_new.get("id")), None)
            if t_old and t_old.get("pnl") is None and t_new.get("pnl") is not None:
                update_trade_pnl(t_new["id"], t_new["pnl"])
                log(f"  ✅ Trade {t_new['id'][:8]}… résolu — P&L ${t_new['pnl']:.2f}")
        history = updated

    log(f"🛡️  Vérification stop-loss ({NO_STOP_LOSS_PCT*100:.0f}%)…")
    check_stop_loss(history)
    history = load_history()

    try:
        markets = polymarket.get_weather_markets()
    except Exception as e:
        log(f"Erreur marchés Polymarket : {e}")
        return

    # Filtre : garde uniquement les marchés avec NO entre 60-99 cents
    markets_no = []
    for m in markets:
        tokens   = m.get("tokens", [])
        no_price = next((t.get("price", 0) for t in tokens if t.get("outcome") == "No"), 0)
        if 0.60 <= no_price <= 0.99:
            markets_no.append(m)

    log(f"📊 {len(markets_no)}/{len(markets)} marchés avec NO > 60 cents")

    usdc = float(os.getenv("BALANCE_USDC", "0"))
    if usdc < 1:
        try:
            usdc = polymarket.get_balance().get("usdc", 0)
        except Exception:
            usdc = 0

    if trader.DRY_RUN:
        if usdc < 1:
            usdc = 100.0
        log(f"[SIMULATION] Solde fictif ${usdc:.2f} | {_stats(history)}")
    else:
        if usdc < 1:
            log(f"⚠️  Solde illisible — cycle annulé")
            return
        log(f"💰 Solde : ~${usdc:.2f} USDC | {_stats(history)}")

    # Enrichissement météo
    for m in markets_no:
        m['local_hour'] = weather_validator.get_city_local_hour(m.get('city', ''))

    def _enrich_weather(m):
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
        markets_no = list(pool.map(_enrich_weather, markets_no))
    wx_count = sum(1 for m in markets_no if m.get('weather_ctx'))
    log(f"   {wx_count}/{len(markets_no)} marchés enrichis")

    if usdc < MIN_TRADE:
        log(f"💤 Solde insuffisant (${usdc:.2f} < ${MIN_TRADE}) — en attente")
        return

    try:
        decisions = brain.decide_v2(strategy, markets_no, history, usdc)
        log(f"Claude V2 : {len(decisions)} décision(s)")
    except Exception as e:
        log(f"Erreur Claude API : {e}")
        return

    if not decisions:
        log("Aucune opportunité NO détectée")
        return

    # Déduplication
    open_cids = {t.get("condition_id") for t in history if t.get("pnl") is None}
    decisions = [d for d in decisions if d.get("condition_id") not in open_cids]
    if not decisions:
        log("Tous les signaux déjà en position")
        return

    market_lookup = {m["condition_id"]: m for m in markets_no}

    # Exécution
    for d in decisions:
        if d.get("action") != "buy" or d.get("outcome") != "No":
            continue

        no_price = float(d.get("no_price", 0) or 0)

        # Vérification prix NO en temps réel
        cid = d.get("condition_id", "")
        price_t1 = _get_current_no_price(cid)
        if price_t1 is None:
            log(f"  🚫 CLOB inaccessible — annulé")
            continue
        if price_t1 < MIN_NO_PRICE:
            log(f"  🚫 Prix NO T1 {price_t1:.3f} < {MIN_NO_PRICE} — signal insuffisant, annulé")
            continue
        if price_t1 > MAX_NO_PRICE:
            log(f"  🚫 Prix NO T1 {price_t1:.3f} > {MAX_NO_PRICE} — marge trop faible, annulé")
            continue
        if no_price > 0 and abs(price_t1 - no_price) / no_price > 0.10:
            log(f"  🚫 Écart trop élevé : Claude estimait NO={no_price:.3f}, réel {price_t1:.3f} — annulé")
            continue

        time.sleep(4)
        price_t2 = _get_current_no_price(cid)
        if price_t2 is None:
            log(f"  🚫 CLOB inaccessible en T2 — annulé")
            continue
        if price_t2 < MIN_NO_PRICE:
            log(f"  🚫 Prix NO T2 {price_t2:.3f} < {MIN_NO_PRICE} — annulé")
            continue
        if price_t2 > MAX_NO_PRICE:
            log(f"  🚫 Prix NO T2 {price_t2:.3f} > {MAX_NO_PRICE} — annulé")
            continue
        drop = price_t1 - price_t2
        if drop > 0.02:
            log(f"  🚫 NO chute : {price_t1:.3f} → {price_t2:.3f} en 4s — annulé")
            continue
        log(f"  ✅ Prix NO stable : T1={price_t1:.3f} → T2={price_t2:.3f} — OK")
        d["no_price"] = price_t2

        # Clamp montant
        amount = float(d.get("amount_usdc") or MIN_TRADE)
        amount = max(MIN_TRADE, min(MAX_TRADE, amount))
        d["amount_usdc"] = amount

        try:
            log(f"→ BUY NO | {cid[:12]}… | ${amount:.2f} | {d.get('reason','')}")
            result = trader.place_market_order(
                condition_id=cid,
                outcome="No",
                side="buy",
                amount_usdc=amount,
            )
            if not result.get("ok") and not result.get("dry_run"):
                log(f"  ⚠️  Ordre rejeté par Polymarket")
                continue
            trade = {
                "id":           str(uuid.uuid4()),
                "bot_id":       BOT_ID,
                "time":         datetime.datetime.now().isoformat(),
                "market":       "polymarket",
                "condition_id": cid,
                "sym":          "No",
                "side":         "buy",
                "amount_usdc":  amount,
                "price":        float(result.get("price", 0) or price_t2),
                "reason":       d.get("reason", ""),
                "result":       result,
                "pnl":          None,
            }
            insert_trade(trade)
            log("  ✅ Ordre enregistré")
        except Exception as e:
            log(f"  ❌ Erreur ordre : {e}")

# ── Auto-amélioration ─────────────────────────────────────────────────────────

def run_improvement():
    log("═══ Auto-amélioration V2 ═══")
    strategy = load_strategy()
    history  = load_history()
    if not strategy.get("prompt", "").strip():
        return
    resolved = [t for t in history if t.get("pnl") is not None]
    if len(resolved) < 5:
        log(f"Pas assez de trades résolus ({len(resolved)}/5)")
        return
    try:
        result     = brain.improve_strategy(strategy, history)
        old_prompt = strategy.get("prompt", "")
        new_prompt = result.get("new_prompt", old_prompt)
        if new_prompt == old_prompt:
            log("Stratégie inchangée")
            return
        strategy["prompt"]        = new_prompt
        strategy["version"]       = result.get("version", 1)
        strategy["last_improved"] = datetime.datetime.now().isoformat()
        strategy["last_reason"]   = result.get("reason", "")
        save_strategy(strategy)
        log(f"✅ Stratégie v{strategy['version']} — {result.get('reason','')}")
    except Exception as e:
        log(f"Erreur auto-amélioration : {e}")

# ── Point d'entrée ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    config.validate()
    log(f"🌤️  ProfitWeather V2.0 démarré — cycle toutes les {INTERVAL_MINUTES} min")
    log(f"   Stratégie : NO sur fourchettes température US (70–95 cents)")
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
            log(f"Erreur inattendue : {e}")
            log(traceback.format_exc())

        log(f"Prochain cycle dans {INTERVAL_MINUTES} min…")
        time.sleep(INTERVAL_MINUTES * 60)
