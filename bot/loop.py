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
import pm_api as polymarket
import brain
import trader
import config

INTERVAL_MINUTES = int(os.getenv("BOT_INTERVAL", "5"))
IMPROVE_HOURS    = int(os.getenv("BOT_IMPROVE_HOURS", "6"))
IMPROVE_INTERVAL = IMPROVE_HOURS * 60 * 60

SB_URL = os.getenv("SUPABASE_URL", "https://obqkqhlqlowxrxbyvktl.supabase.co")
SB_KEY = os.getenv("SUPABASE_KEY", "")

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
                "ont détecté un signal fort.\n\n"
                "Règle d'entrée :\n"
                "- Un signal actif d'un bot d'analyse (YES ≥ 75%) EST une opportunité à trader\n"
                "- Trouver dans les marchés disponibles le marché qui correspond à ce signal\n"
                "- Le prix YES actuel doit être entre 0.75 et 0.97\n"
                "- Volume minimum du marché : 500 USDC\n"
                "- Favoriser les villes avec un taux de victoire historique > 60%\n\n"
                "Taille des positions :\n"
                "- 10 USDC par trade maximum tant que le bot est en phase de test\n"
                "- Jamais plus de 20% du solde disponible sur un seul marché\n\n"
                "Ne rien trader si aucun signal actif des bots ne correspond à un marché disponible."
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

    # 3. Données Polymarket
    try:
        markets = polymarket.get_weather_markets()
    except Exception as e:
        log(f"Erreur marchés Polymarket : {e}")
        return

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

    # 4. Décision Claude
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

    # 5. Exécution + sauvegarde dans Supabase
    for d in decisions:
        if d.get("action") != "buy":
            continue
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
