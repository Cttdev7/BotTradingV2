"""
loop.py — Boucle principale du bot

Cycle toutes les INTERVAL_MINUTES minutes :
1. Lit la stratégie depuis strategy.json
2. Récupère les marchés Polymarket
3. Appelle Claude (brain.py) pour décider
4. Exécute les ordres (trader.py)
5. Sauvegarde le résultat dans l'historique
6. Toutes les 24h : demande à Claude de réfléchir et suggérer des améliorations

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

INTERVAL_MINUTES = int(os.getenv("BOT_INTERVAL", "15"))  # fréquence en minutes
REFLECT_INTERVAL = 24 * 60 * 60  # réflexion toutes les 24h (en secondes)
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")
STRATEGY_FILE = os.path.join(os.path.dirname(__file__), "strategy.json")

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_strategy(bot_id: str = "polyedge") -> dict:
    if os.path.exists(STRATEGY_FILE):
        with open(STRATEGY_FILE) as f:
            data = json.load(f)
            return data.get(bot_id, {})
    return {}

def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []

def save_history(history: list):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history[-500:], f, indent=2, ensure_ascii=False)  # garde les 500 derniers

def log(msg: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    # Append au fichier de log
    log_file = os.path.join(os.path.dirname(__file__), "bot.log")
    with open(log_file, "a") as f:
        f.write(line + "\n")

# ── Cycle principal ───────────────────────────────────────────────────────────

def run_cycle(bot_id: str = "polyedge"):
    log("─── Nouveau cycle ───")

    # 1. Stratégie
    strategy = load_strategy(bot_id)
    if not strategy.get("enabled"):
        log("Bot désactivé — active-le dans l'onglet Stratégie du dashboard")
        return
    if not strategy.get("prompt", "").strip():
        log("Aucun prompt de stratégie — écris une stratégie dans le dashboard")
        return

    # 2. Données Polymarket
    try:
        markets = polymarket.get_markets(limit=50)
        balance = polymarket.get_balance()
        history = load_history()
        usdc = balance.get("usdc", 0)
        log(f"Solde : ${usdc:.2f} USDC | {len(markets)} marchés | {len(history)} trades passés")
    except Exception as e:
        log(f"Erreur récupération données : {e}")
        return

    if usdc < 1:
        log("Solde insuffisant (< 1 USDC) — alimente ton wallet")
        return

    # 3. Décision Claude
    try:
        decisions = brain.decide(strategy, markets, history, usdc)
        log(f"Claude a pris {len(decisions)} décision(s)")
    except Exception as e:
        log(f"Erreur Claude API : {e}")
        return

    if not decisions:
        log("Aucune opportunité détectée pour cette stratégie")
        return

    # 4. Exécution des ordres
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
            # 5. Sauvegarde dans l'historique
            record = {
                "time":         datetime.datetime.now().isoformat(),
                "bot":          bot_id,
                "market":       "polymarket",
                "condition_id": d["condition_id"],
                "sym":          d["outcome"],
                "side":         d["action"],
                "amount_usdc":  d["amount_usdc"],
                "reason":       d["reason"],
                "result":       result,
                "pnl":          None,  # calculé à la clôture
            }
            history = load_history()
            history.append(record)
            save_history(history)
            log(f"  ✅ Ordre exécuté")
        except Exception as e:
            log(f"  ❌ Erreur ordre : {e}")

# ── Réflexion périodique ──────────────────────────────────────────────────────

def run_reflection(bot_id: str = "polyedge"):
    log("═══ Réflexion quotidienne ═══")
    strategy = load_strategy(bot_id)
    history  = load_history()
    recent   = [t for t in history if t.get("bot") == bot_id][-20:]
    try:
        analysis = brain.reflect(strategy, recent)
        log(f"Analyse Claude :\n{analysis}")
        # Sauvegarde l'analyse dans un fichier
        reflect_file = os.path.join(os.path.dirname(__file__), "reflections.json")
        reflections = []
        if os.path.exists(reflect_file):
            with open(reflect_file) as f:
                reflections = json.load(f)
        reflections.append({
            "time":     datetime.datetime.now().isoformat(),
            "analysis": analysis,
        })
        with open(reflect_file, "w") as f:
            json.dump(reflections[-30:], f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"Erreur réflexion : {e}")

# ── Point d'entrée ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    config.validate()
    log(f"🤖 Bot démarré — cycle toutes les {INTERVAL_MINUTES} min")
    log(f"   Mode : {'SIMULATION (DRY_RUN)' if trader.DRY_RUN else '⚠️  TRADING RÉEL'}")
    log(f"   Wallet : {config.WALLET_ADDRESS[:10]}…")

    last_reflect = 0

    while True:
        try:
            run_cycle()
            # Réflexion toutes les 24h
            if time.time() - last_reflect > REFLECT_INTERVAL:
                run_reflection()
                last_reflect = time.time()
        except KeyboardInterrupt:
            log("Bot arrêté manuellement")
            break
        except Exception as e:
            log(f"Erreur inattendue : {e}")

        log(f"Prochain cycle dans {INTERVAL_MINUTES} min…")
        time.sleep(INTERVAL_MINUTES * 60)
