from __future__ import annotations

"""
loop.py — Boucle principale ProfitWeather (Railway-ready)

Cycle toutes les INTERVAL_MINUTES minutes :
1. Lit la stratégie depuis Supabase (bot_strategies)
2. Vérifie les outcomes des trades ouverts
3. Récupère les marchés météo Polymarket
4. Appelle Claude (brain.py) pour décider
5. Exécute les ordres (trader.py)
6. Sauvegarde dans Supabase (trade_history)

Toutes les IMPROVE_HOURS heures :
→ Claude réécrit la stratégie en se basant sur les résultats
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

INTERVAL_MINUTES = int(os.getenv("BOT_INTERVAL", "5"))
IMPROVE_HOURS    = int(os.getenv("BOT_IMPROVE_HOURS", "6"))
IMPROVE_INTERVAL = IMPROVE_HOURS * 60 * 60

SB_URL = os.getenv("SUPABASE_URL", "https://obqkqhlqlowxrxbyvktl.supabase.co")
SB_KEY = os.getenv("SUPABASE_KEY", "")

# Villes blacklistées — jamais de trade, peu importe le signal
CITY_BLACKLIST = {"jeddah"}

# ── Supabase helpers ──────────────────────────────────────────────────────────

def _sb_headers():
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }

def load_strategy(bot_id: str = "polyedge") -> dict:
    try:
        r = requests.get(
            f"{SB_URL}/rest/v1/bot_strategies",
            params={"bot_id": f"eq.{bot_id}", "limit": "1"},
            headers=_sb_headers(), timeout=5,
        )
        if r.status_code == 200 and r.json():
            return r.json()[0]
    except Exception as e:
        log(f"⚠️  load_strategy : {e}")
    # Fallback 1 : fichier local strategy.json
    local_path = os.path.join(os.path.dirname(__file__), "strategy.json")
    try:
        with open(local_path) as f:
            data = json.load(f)
            if bot_id in data:
                log(f"📂 Stratégie chargée depuis strategy.json local")
                return data[bot_id]
    except Exception:
        pass
    # Fallback 2 : stratégie embarquée (Railway sans fichier local ni Supabase)
    if bot_id == "polyedge":
        log("📦 Stratégie par défaut embarquée (Railway fallback)")
        return {
            "bot_id":  "polyedge",
            "enabled": True,
            "version": 1,
            "prompt": (
                "STRATÉGIE : acheter YES sur les marchés température où les bots d'analyse "
                "ont détecté un signal fort. Minimum 10 USDC par trade, autant de positions que les signaux le justifient.\n\n"
                "Règle d'entrée :\n"
                "- Un signal actif d'un bot d'analyse (YES ≥ 75%) EST une opportunité à évaluer\n"
                "- Le prix YES actuel doit être entre 0.76 et 0.92\n"
                "- Zone idéale : YES 0.76-0.87 (meilleur rapport valeur/risque)\n"
                "- Volume minimum du marché : 1 000 USDC\n"
                "- Favoriser les villes avec un taux de victoire historique > 60%\n\n"
                "Taille des positions (jamais en dessous de 10 USDC) :\n"
                "- Signal standard : 15% du solde, min 10 USDC\n"
                "- Signal fort (ville Tier 1, win rate >65%) : 20% du solde\n"
                "- Signal exceptionnel (convergence bots + Mistral) : 25% du solde\n"
                "- Max 55% du solde total engagé simultanément\n\n"
                "Villes Tier 1 prioritaires : toronto, miami, houston, singapore, tokyo, seoul, shanghai, dubai.\n\n"
                "Ne rien trader si aucun signal qualifié. Mieux vaut attendre le prochain cycle."
            ),
        }
    return {}

def save_strategy(bot_id: str, strategy: dict):
    try:
        requests.post(
            f"{SB_URL}/rest/v1/bot_strategies",
            json={**strategy, "bot_id": bot_id, "updated_at": datetime.datetime.now().isoformat()},
            headers={**_sb_headers(), "Prefer": "resolution=merge-duplicates"},
            timeout=5,
        )
    except Exception as e:
        log(f"⚠️  save_strategy : {e}")

def load_history(bot_id: str = "polyedge") -> list:
    try:
        r = requests.get(
            f"{SB_URL}/rest/v1/trade_history",
            params={"bot_id": f"eq.{bot_id}", "order": "created_at.asc", "limit": "500"},
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
    ts   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def _stats(history: list) -> str:
    wins   = len([t for t in history if (t.get("pnl") or 0) > 0])
    losses = len([t for t in history if (t.get("pnl") or 0) < 0])
    pnl    = sum(t.get("pnl") or 0 for t in history)
    return f"{wins}W / {losses}L / P&L total ${pnl:.2f}"

# ── Stop-loss automatique ─────────────────────────────────────────────────────

STOP_LOSS_PCT    = -0.15  # -15% → vente automatique
TAKE_PROFIT_PRICE = 0.99   # YES ≥ 99% → vente automatique (lock profit)

def _get_current_yes_price(condition_id: str) -> float | None:
    """Récupère le prix YES actuel depuis le CLOB."""
    try:
        r = requests.get(
            f"https://clob.polymarket.com/markets/{condition_id}",
            timeout=8,
        )
        if r.status_code != 200:
            return None
        for token in r.json().get("tokens", []):
            if token.get("outcome", "").lower() == "yes":
                return float(token.get("price", 0))
    except Exception:
        pass
    return None

def check_stop_loss(history: list, bot_id: str = "polyedge"):
    """
    Pour chaque position ouverte, vérifie si le prix a chuté de plus de STOP_LOSS_PCT.
    Si oui, vend immédiatement et enregistre le P&L.
    """
    open_trades = [t for t in history if t.get("pnl") is None]
    if not open_trades:
        return

    for t in open_trades:
        entry_price = float(t.get("price") or 0)
        if entry_price <= 0:
            continue

        current_price = _get_current_yes_price(t.get("condition_id", ""))
        if current_price is None:
            continue

        amount_usdc = float(t.get("amount_usdc") or 0)
        pnl_pct = (current_price - entry_price) / entry_price
        # Take-profit : YES ≥ 99.9% → vendre maintenant, ne pas attendre la résolution
        if current_price >= TAKE_PROFIT_PRICE:
            tokens_held = amount_usdc / entry_price
            pnl_usd     = round(tokens_held * (current_price - entry_price), 2)
            log(f"  💰 TAKE-PROFIT {t.get('sym','Yes')} {t.get('condition_id','')[:12]}… "
                f"| prix {current_price:.4f} ≥ {TAKE_PROFIT_PRICE} | P&L estimé +${pnl_usd:.2f}")
            # Si prix = 1.0 exact → marché déjà résolu, Polymarket a crédité le wallet
            # L'orderbook est fermé → pas de vente possible, on enregistre le P&L directement
            if current_price >= 1.0:
                update_trade_pnl(t["id"], pnl_usd)
                log(f"    ✅ Résolu à 1.0 — P&L enregistré +${pnl_usd:.2f} (Polymarket a déjà crédité)")
            else:
                try:
                    result = trader.place_market_order(
                        condition_id=t["condition_id"],
                        outcome=t.get("sym", "Yes"),
                        side="sell",
                        amount_usdc=tokens_held,
                    )
                    if result.get("ok") or result.get("dry_run"):
                        taking   = float(result.get("taking_amount") or 0)
                        real_pnl = round(taking - amount_usdc, 2) if taking else pnl_usd
                        update_trade_pnl(t["id"], real_pnl)
                        log(f"    ✅ Vendu — P&L réel +${real_pnl:.2f}")
                    else:
                        log(f"    ⚠️  Vente rejetée par Polymarket")
                except Exception as e:
                    err = str(e)
                    if "resting liquidity" in err.lower() or "not enough balance" in err.lower():
                        # Marché résolu ou tokens déjà absents → enregistre le P&L estimé
                        update_trade_pnl(t["id"], pnl_usd)
                        log(f"    ✅ Marché fermé — P&L enregistré +${pnl_usd:.2f}")
                    else:
                        log(f"    ❌ Erreur vente take-profit : {e}")
            continue

        if pnl_pct >= STOP_LOSS_PCT:
            continue

        # Stop-loss déclenché
        tokens_held = amount_usdc / entry_price
        pnl_usd     = round(tokens_held * (current_price - entry_price), 2)

        log(f"  🛑 STOP-LOSS {t.get('sym','Yes')} {t.get('condition_id','')[:12]}… "
            f"| entrée {entry_price:.3f} → actuel {current_price:.3f} "
            f"({pnl_pct*100:+.1f}%) | P&L estimé ${pnl_usd:.2f}")
        # Prix à 0.001 = marché résolu à NO, orderbook fermé → enregistre la perte directement
        if current_price <= 0.005:
            update_trade_pnl(t["id"], pnl_usd)
            log(f"    ✅ Résolu à NO — P&L enregistré ${pnl_usd:.2f} (Polymarket a tranché)")
            continue
        try:
            result = trader.place_market_order(
                condition_id=t["condition_id"],
                outcome=t.get("sym", "Yes"),
                side="sell",
                amount_usdc=tokens_held,
            )
            if result.get("ok") or result.get("dry_run"):
                taking = float(result.get("taking_amount") or 0)
                real_pnl = round(taking - amount_usdc, 2) if taking else pnl_usd
                update_trade_pnl(t["id"], real_pnl)
                log(f"    ✅ Vendu — P&L réel ${real_pnl:.2f}")
            else:
                log(f"    ⚠️  Vente rejetée par Polymarket")
        except Exception as e:
            err = str(e)
            if "resting liquidity" in err.lower() or "not enough balance" in err.lower():
                update_trade_pnl(t["id"], pnl_usd)
                log(f"    ✅ Marché fermé — perte enregistrée ${pnl_usd:.2f}")
            else:
                log(f"    ❌ Erreur vente stop-loss : {e}")

# ── Cycle principal ───────────────────────────────────────────────────────────

def run_cycle(bot_id: str = "polyedge"):
    log("─── Nouveau cycle ───")

    # 1. Stratégie depuis Supabase
    strategy = load_strategy(bot_id)
    if not strategy.get("enabled"):
        log("Bot désactivé — active-le dans l'onglet Stratégie du dashboard")
        return
    if not strategy.get("prompt", "").strip():
        log("Aucun prompt — écris une stratégie dans le dashboard")
        return

    # 2. Vérifie les outcomes des trades ouverts
    history     = load_history(bot_id)
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

    # 2b. Stop-loss automatique (-15%)
    log(f"🛡️  Vérification stop-loss ({STOP_LOSS_PCT*100:.0f}%)…")
    check_stop_loss(history, bot_id)
    history = load_history(bot_id)  # Recharge après éventuelles ventes

    # 3. Données Polymarket
    try:
        markets = polymarket.get_weather_markets()
    except Exception as e:
        log(f"Erreur marchés Polymarket : {e}")
        return

    # Filtre volume minimum par ville : $20 000 total cumulé
    CITY_MIN_VOLUME = 20_000
    from collections import defaultdict
    city_vol = defaultdict(float)
    for m in markets:
        city_vol[m.get("city", "")] += float(m.get("volume") or 0)
    before = len(markets)
    markets = [m for m in markets if city_vol[m.get("city", "")] >= CITY_MIN_VOLUME]
    excluded = before - len(markets)
    if excluded:
        low_vol = {c for c, v in city_vol.items() if v < CITY_MIN_VOLUME}
        log(f"🔍 Filtre volume : {excluded} marchés exclus ({', '.join(sorted(low_vol))})")

    # Solde : override manuel > API > fictif (simulation) > bloquant (réel)
    usdc = float(os.getenv("BALANCE_USDC", "0"))
    if usdc < 1:
        try:
            usdc = polymarket.get_balance().get("usdc", 0)
        except Exception:
            usdc = 0

    if trader.DRY_RUN:
        if usdc < 1:
            usdc = 100.0
        log(f"[SIMULATION] Solde fictif ${usdc:.2f} | {len(markets)} marchés | {_stats(history)}")
    else:
        if usdc < 1:
            log(f"⚠️  Solde illisible (API inaccessible, BALANCE_USDC non défini) — cycle annulé pour éviter des ordres sans fonds")
            return
        log(f"💰 Solde : ~${usdc:.2f} USDC | {len(markets)} marchés | {_stats(history)}")

    # Enrichit chaque marché avec l'heure locale de la ville
    for m in markets:
        m['local_hour'] = weather_validator.get_city_local_hour(m.get('city', ''))

    # 4. Enrichissement météo complet (ensemble + multi-modèles + temp actuelle)
    # Cache 30 min par ville — coût API minimal même à cycle court
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

    log("🌤️  Enrichissement météo (ensemble ECMWF + 4 modèles)…")
    with ThreadPoolExecutor(max_workers=8) as pool:
        markets = list(pool.map(_enrich_weather, markets))
    wx_count = sum(1 for m in markets if m.get('weather_ctx'))
    log(f"   {wx_count}/{len(markets)} marchés enrichis")

    # 5. Décision Claude
    if usdc < 10:
        log(f"💤 Solde insuffisant (${usdc:.2f} < $10) — aucun achat, en attente de résolution des trades")
        return

    try:
        decisions = brain.decide(strategy, markets, history, usdc)
        log(f"Claude : {len(decisions)} décision(s)")
    except Exception as e:
        log(f"Erreur Claude API : {e}")
        return

    if not decisions:
        log("Aucune opportunité détectée")
        return

    # Déduplication
    open_cids = {t.get("condition_id") for t in history if t.get("pnl") is None}
    decisions = [d for d in decisions if d.get("condition_id") not in open_cids]
    if not decisions:
        log("Tous les signaux déjà en position — rien à ajouter")
        return

    # Lookup condition_id → infos marché (ville, question, slug) pour la validation météo
    market_lookup = {m["condition_id"]: m for m in markets}

    # 5. Exécution + sauvegarde dans Supabase
    MIN_TRADE  = 10.0
    MIN_PRICE  = 0.78  # Relevé de 0.76 → signal doit être plus fort
    MAX_PRICE  = 0.92  # Abaissé de 0.95 → marge de sécurité plus large
    for d in decisions:
        if d.get("action") != "buy":
            continue
        yes_price = float(d.get("yes_price", 0) or 0)
        if yes_price >= MAX_PRICE:
            log(f"  🚫 Bloqué (prix {yes_price:.3f} ≥ {MAX_PRICE}) — règle hard-coded")
            continue
        if yes_price > 0 and yes_price < MIN_PRICE:
            log(f"  🚫 Bloqué (prix {yes_price:.3f} < {MIN_PRICE}) — signal insuffisant")
            continue
        # Blacklist villes — bloqué à jamais
        mkt = market_lookup.get(d.get("condition_id", ""), {})
        if mkt.get("city", "") in CITY_BLACKLIST:
            log(f"  🚫 Bloqué ({mkt.get('city')}) — ville blacklistée")
            continue
        # Vérification prix en temps réel + détection de crash
        # T1 → attente 4s → T2 : vérifie limites à CHAQUE sample
        cid = d.get("condition_id", "")
        price_t1 = _get_current_yes_price(cid)
        if price_t1 is None:
            # API CLOB inaccessible — on ne peut pas vérifier le prix réel → annulé
            log(f"  🚫 CLOB inaccessible — impossible de vérifier le prix, annulé")
            continue
        if price_t1 < MIN_PRICE:
            log(f"  🚫 Prix T1 {price_t1:.3f} < {MIN_PRICE} — marché crashé, annulé")
            continue
        if price_t1 >= MAX_PRICE:
            log(f"  🚫 Prix T1 {price_t1:.3f} ≥ {MAX_PRICE} — trop cher, annulé")
            continue
        if yes_price > 0 and abs(price_t1 - yes_price) / yes_price > 0.10:
            log(f"  🚫 Écart trop élevé : Claude estimait {yes_price:.3f}, réel {price_t1:.3f} ({abs(price_t1-yes_price)/yes_price*100:.0f}%) — annulé")
            continue
        # 2ème sample 4 secondes plus tard — re-vérifie aussi les limites
        time.sleep(4)
        price_t2 = _get_current_yes_price(cid)
        if price_t2 is None:
            log(f"  ⚠️  T2 inaccessible — utilise T1={price_t1:.3f}")
            price_t2 = price_t1
        if price_t2 < MIN_PRICE:
            log(f"  🚫 Prix T2 {price_t2:.3f} < {MIN_PRICE} — a crashé entre T1 et T2, annulé")
            continue
        if price_t2 >= MAX_PRICE:
            log(f"  🚫 Prix T2 {price_t2:.3f} ≥ {MAX_PRICE} — a monté entre T1 et T2, annulé")
            continue
        drop = price_t1 - price_t2
        if drop > 0.01:
            log(f"  🚫 Crash détecté : {price_t1:.3f} → {price_t2:.3f} (-{drop/price_t1*100:.1f}% en 4s) — annulé")
            continue
        log(f"  ✅ Prix stable : T1={price_t1:.3f} → T2={price_t2:.3f} — OK")
        d["yes_price"] = price_t2
        # Validation météo Open-Meteo — limite le risque avant exécution
        if mkt:
            wx = weather_validator.validate_yes_trade(
                city_slug=mkt.get("city", ""),
                question=mkt.get("question", ""),
                slug=mkt.get("slug", ""),
            )
            if not wx["ok"]:
                log(f"  🌤️ VETO MÉTÉO : {wx['reason']}")
                continue
            log(f"  🌤️ Météo OK : {wx['reason']}")
        # Enforce minimum absolu
        if d.get("amount_usdc", 0) < MIN_TRADE:
            d["amount_usdc"] = MIN_TRADE
        try:
            log(f"→ {d['action'].upper()} {d['outcome']} | {d['condition_id'][:12]}… | ${d['amount_usdc']:.2f} | {d['reason']}")
            result = trader.place_market_order(
                condition_id=d["condition_id"],
                outcome=d["outcome"],
                side=d["action"],
                amount_usdc=d["amount_usdc"],
            )
            if not result.get("ok") and not result.get("dry_run"):
                log(f"  ⚠️  Ordre rejeté par Polymarket (ok=False) — non enregistré")
                continue
            trade = {
                "id":           str(uuid.uuid4()),
                "bot_id":       bot_id,
                "time":         datetime.datetime.now().isoformat(),
                "market":       "polymarket",
                "condition_id": d["condition_id"],
                "sym":          d["outcome"],
                "side":         d["action"],
                "amount_usdc":  d["amount_usdc"],
                "price":        float(result.get("price", 0) or d.get("yes_price", 0)),
                "reason":       d["reason"],
                "result":       result,
                "pnl":          None,
            }
            insert_trade(trade)
            log("  ✅ Ordre enregistré")
        except Exception as e:
            log(f"  ❌ Erreur ordre : {e}")

# ── Auto-amélioration de la stratégie ────────────────────────────────────────

def run_improvement(bot_id: str = "polyedge"):
    log("═══ Auto-amélioration de la stratégie ═══")

    strategy    = load_strategy(bot_id)
    history     = load_history(bot_id)

    if not strategy.get("prompt", "").strip():
        log("Pas de stratégie à améliorer")
        return

    resolved = [t for t in history if t.get("pnl") is not None]
    if len(resolved) < 5:
        log(f"Pas assez de trades résolus ({len(resolved)}/5 minimum)")
        return

    try:
        result     = brain.improve_strategy(strategy, history)
        old_prompt = strategy.get("prompt", "")
        new_prompt = result.get("new_prompt", old_prompt)
        reason     = result.get("reason", "")
        version    = result.get("version", 1)

        if new_prompt == old_prompt:
            log("Stratégie inchangée — déjà optimale")
            return

        history_list = strategy.get("history", [])
        history_list.append({
            "version": strategy.get("version", 1),
            "prompt":  old_prompt,
            "time":    datetime.datetime.now().isoformat(),
            "reason":  "Remplacée par version améliorée",
        })

        strategy["prompt"]        = new_prompt
        strategy["version"]       = version
        strategy["last_improved"] = datetime.datetime.now().isoformat()
        strategy["last_reason"]   = reason
        strategy["history"]       = history_list[-10:]

        save_strategy(bot_id, strategy)
        log(f"✅ Stratégie v{version} — {reason}")

    except Exception as e:
        log(f"Erreur auto-amélioration : {e}")

# ── Point d'entrée ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    config.validate()
    log(f"🤖 ProfitWeather démarré — cycle toutes les {INTERVAL_MINUTES} min")
    log(f"   Mode : {'SIMULATION (DRY_RUN)' if trader.DRY_RUN else '⚠️  TRADING RÉEL'}")
    log(f"   Wallet : {config.WALLET_ADDRESS[:10]}…")
    log(f"   Supabase : {SB_URL[:40]}…")

    last_improve = time.time()

    while True:
        try:
            run_cycle()
            if time.time() - last_improve > IMPROVE_INTERVAL:
                run_improvement()
                last_improve = time.time()
        except KeyboardInterrupt:
            log("Bot arrêté")
            break
        except Exception as e:
            import traceback
            log(f"Erreur inattendue : {e}")
            log(traceback.format_exc())

        log(f"Prochain cycle dans {INTERVAL_MINUTES} min…")
        time.sleep(INTERVAL_MINUTES * 60)
