"""
loop.py — Boucle principale du bot auto-apprenant

Cycle toutes les INTERVAL_MINUTES minutes :
1. Lit la stratégie depuis strategy.json
2. Vérifie les outcomes des trades précédents (P&L réel)
3. Récupère les marchés actifs Polymarket
4. Appelle Claude (brain.py) pour décider
5. Exécute les ordres (trader.py)
6. Sauvegarde dans l'historique

Toutes les IMPROVE_HOURS heures :
→ Claude réécrit la stratégie en se basant sur les résultats
→ Nouvelle version sauvegardée automatiquement

Lance avec : python3 bot/loop.py
"""

import time
import json
import os
import datetime
import polymarket
import brain
import trader
import config

INTERVAL_MINUTES = int(os.getenv("BOT_INTERVAL", "15"))
IMPROVE_HOURS    = int(os.getenv("BOT_IMPROVE_HOURS", "6"))   # amélioration toutes les 6h
IMPROVE_INTERVAL = IMPROVE_HOURS * 60 * 60

HISTORY_FILE  = os.path.join(os.path.dirname(__file__), "history.json")
STRATEGY_FILE = os.path.join(os.path.dirname(__file__), "strategy.json")

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_strategy(bot_id: str = "polyedge") -> dict:
    if os.path.exists(STRATEGY_FILE):
        with open(STRATEGY_FILE) as f:
            data = json.load(f)
            return data.get(bot_id, {})
    return {}

def save_strategy(bot_id: str, strategy: dict):
    all_strategies = {}
    if os.path.exists(STRATEGY_FILE):
        with open(STRATEGY_FILE) as f:
            all_strategies = json.load(f)
    all_strategies[bot_id] = strategy
    with open(STRATEGY_FILE, "w") as f:
        json.dump(all_strategies, f, indent=2, ensure_ascii=False)

def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []

def save_history(history: list):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history[-500:], f, indent=2, ensure_ascii=False)

def log(msg: str):
    ts   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    log_file = os.path.join(os.path.dirname(__file__), "bot.log")
    with open(log_file, "a") as f:
        f.write(line + "\n")

def _stats(history: list) -> str:
    wins   = len([t for t in history if (t.get("pnl") or 0) > 0])
    losses = len([t for t in history if (t.get("pnl") or 0) < 0])
    pnl    = sum(t.get("pnl") or 0 for t in history)
    return f"{wins}W / {losses}L / P&L total ${pnl:.2f}"

# ── Cycle principal ───────────────────────────────────────────────────────────

def run_cycle(bot_id: str = "polyedge"):
    log("─── Nouveau cycle ───")

    # 1. Stratégie
    strategy = load_strategy(bot_id)
    if not strategy.get("enabled"):
        log("Bot désactivé — active-le dans l'onglet Stratégie du dashboard")
        return
    if not strategy.get("prompt", "").strip():
        log("Aucun prompt — écris une stratégie dans le dashboard")
        return

    # 2. Vérifie les outcomes des trades précédents
    history = load_history()
    open_trades = [t for t in history if t.get("pnl") is None and t.get("bot") == bot_id]
    if open_trades:
        log(f"Vérification outcomes de {len(open_trades)} trades ouverts…")
        updated = brain.check_market_outcomes(history)
        id_to_old = {t.get("id"): t for t in history if t.get("id")}
        resolved = sum(1 for t in updated if id_to_old.get(t.get("id"), {}).get("pnl") is None and t.get("pnl") is not None)
        if resolved:
            log(f"  {resolved} trades résolus — P&L mis à jour")
            history = updated
            save_history(history)

    # 3. Données Polymarket
    try:
        markets = polymarket.get_active_markets(limit=50)
        balance = polymarket.get_balance()
        usdc    = balance.get("usdc", 0)
        log(f"Solde : ${usdc:.2f} USDC | {len(markets)} marchés | {_stats(history)}")
    except Exception as e:
        log(f"Erreur récupération données : {e}")
        return

    if usdc < 1:
        log("Solde insuffisant (< 1 USDC) — alimente ton wallet")
        return

    # 4. Décision Claude
    try:
        decisions = brain.decide(strategy, markets, history, usdc)
        log(f"Claude a pris {len(decisions)} décision(s)")
    except Exception as e:
        log(f"Erreur Claude API : {e}")
        return

    if not decisions:
        log("Aucune opportunité détectée pour cette stratégie")
        return

    # 5. Exécution + sauvegarde
    for d in decisions:
        try:
            log(f"→ {d['action'].upper()} {d['outcome']} sur {d['condition_id'][:12]}… "
                f"${d['amount_usdc']:.2f} USDC — {d['reason']}")
            result = trader.place_market_order(
                condition_id=d["condition_id"],
                outcome=d["outcome"],
                side=d["action"],
                amount_usdc=d["amount_usdc"],
            )
            history.append({
                "time":         datetime.datetime.now().isoformat(),
                "bot":          bot_id,
                "market":       "polymarket",
                "condition_id": d["condition_id"],
                "sym":          d["outcome"],
                "side":         d["action"],
                "amount_usdc":  d["amount_usdc"],
                "price":        float(result.get("price", 0) or d.get("yes_price", 0)),
                "reason":       d["reason"],
                "result":       result,
                "pnl":          None,
            })
            log("  ✅ Ordre exécuté")
        except Exception as e:
            log(f"  ❌ Erreur ordre : {e}")

    try:
        save_history(history)
    except Exception as e:
        log(f"  ⚠️  Impossible de sauvegarder l'historique : {e}")

# ── Auto-amélioration de la stratégie ────────────────────────────────────────

def run_improvement(bot_id: str = "polyedge"):
    """
    Claude réécrit la stratégie en se basant sur tous les trades.
    La nouvelle version est sauvegardée avec l'historique des versions.
    """
    log("═══ Auto-amélioration de la stratégie ═══")

    strategy = load_strategy(bot_id)
    history  = load_history()
    bot_history = [t for t in history if t.get("bot") == bot_id]

    if not strategy.get("prompt", "").strip():
        log("Pas de stratégie à améliorer")
        return

    try:
        result = brain.improve_strategy(strategy, bot_history)
        old_prompt = strategy.get("prompt", "")
        new_prompt = result.get("new_prompt", old_prompt)
        reason     = result.get("reason", "")
        version    = result.get("version", 1)

        if new_prompt == old_prompt:
            log("Stratégie inchangée — déjà optimale selon Claude")
            return

        # Sauvegarde avec historique des versions
        strategy_history = strategy.get("history", [])
        strategy_history.append({
            "version":   strategy.get("version", 1),
            "prompt":    old_prompt,
            "time":      datetime.datetime.now().isoformat(),
            "reason":    "Remplacée par version améliorée",
        })

        strategy["prompt"]        = new_prompt
        strategy["version"]       = version
        strategy["last_improved"] = datetime.datetime.now().isoformat()
        strategy["last_reason"]   = reason
        strategy["history"]       = strategy_history[-10:]  # garde les 10 dernières versions

        save_strategy(bot_id, strategy)
        log(f"✅ Stratégie mise à jour → version {version}")
        log(f"   Raison : {reason}")
        log(f"   Nouvelle stratégie : {new_prompt[:100]}…")

    except Exception as e:
        log(f"Erreur auto-amélioration : {e}")

# ── Point d'entrée ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    config.validate()
    log(f"🤖 Bot démarré — cycle toutes les {INTERVAL_MINUTES} min")
    log(f"   Auto-amélioration : toutes les {IMPROVE_HOURS}h")
    log(f"   Mode : {'SIMULATION (DRY_RUN)' if trader.DRY_RUN else '⚠️  TRADING RÉEL'}")
    log(f"   Wallet : {config.WALLET_ADDRESS[:10]}…")
    log(f"   Modèle : {config.CLAUDE_MODEL}")

    last_improve = time.time()  # première amélioration après IMPROVE_HOURS

    while True:
        try:
            run_cycle()

            # Auto-amélioration toutes les IMPROVE_HOURS heures
            if time.time() - last_improve > IMPROVE_INTERVAL:
                run_improvement()
                last_improve = time.time()

        except KeyboardInterrupt:
            log("Bot arrêté manuellement")
            break
        except Exception as e:
            log(f"Erreur inattendue : {e}")

        log(f"Prochain cycle dans {INTERVAL_MINUTES} min…")
        time.sleep(INTERVAL_MINUTES * 60)
