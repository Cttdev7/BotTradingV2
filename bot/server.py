"""
Serveur API local — TradingBot Polymarket
Lance avec : python3 bot/server.py
Écoute sur  : http://localhost:5050
(port 5000 évité — capté par AirPlay Receiver / ControlCenter sur macOS, renvoie 403)
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import pm_api as polymarket
import config
import json
import os
import datetime

app = Flask(__name__)
CORS(app, origins=["http://localhost:8080", "http://127.0.0.1:8080"])

STRATEGY_FILE   = os.path.join(os.path.dirname(__file__), "strategy.json")
PERF_RESET_DATE = "2026-06-17T15:34:00"  # stats V2 remises à 0 à cette heure
SUPABASE_URL    = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY    = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")

# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_all_strategies() -> dict:
    if os.path.exists(STRATEGY_FILE):
        with open(STRATEGY_FILE) as f:
            data = json.load(f)
            # Migration ancien format (objet plat) → nouveau format (par bot_id)
            if "prompt" in data and not any(isinstance(v, dict) for v in data.values()):
                return {"polyedge": data}
            return data
    return {}

def _load_strategy(bot_id: str) -> dict:
    return _load_all_strategies().get(bot_id, {"prompt": "", "enabled": False})

def _save_strategy(bot_id: str, data: dict):
    all_strategies = _load_all_strategies()
    all_strategies[bot_id] = data
    with open(STRATEGY_FILE, "w") as f:
        json.dump(all_strategies, f, indent=2, ensure_ascii=False)

def _ok(data):
    return jsonify(data)

def _err(msg, code=500):
    return jsonify({"error": str(msg)}), code

# ── Status ───────────────────────────────────────────────────────────────────

@app.route("/api/status")
def status():
    try:
        config.validate()
        polymarket.test_connection()
        bal = polymarket.get_balance()
        return _ok({
            "connected": True,
            "wallet": config.WALLET_ADDRESS,
            "balance": bal,
        })
    except Exception as e:
        return _ok({"connected": False, "error": str(e)})

# ── Balance ──────────────────────────────────────────────────────────────────

@app.route("/api/balance")
def balance():
    try:
        return _ok(polymarket.get_balance())
    except Exception as e:
        return _err(e)

@app.route("/api/wallet")
def wallet():
    try:
        return _ok(polymarket.get_polygon_balance())
    except Exception as e:
        return _err(e)

# ── Marchés ──────────────────────────────────────────────────────────────────

@app.route("/api/markets")
def markets():
    try:
        limit = request.args.get("limit", 50, type=int)
        return _ok(polymarket.get_markets(limit))
    except Exception as e:
        return _err(e)

@app.route("/api/markets/<condition_id>")
def market_detail(condition_id):
    try:
        return _ok(polymarket.get_market(condition_id))
    except Exception as e:
        return _err(e)

@app.route("/api/orderbook/<token_id>")
def orderbook(token_id):
    try:
        return _ok(polymarket.get_order_book(token_id))
    except Exception as e:
        return _err(e)

# ── Positions & ordres ───────────────────────────────────────────────────────

@app.route("/api/positions")
def positions():
    try:
        return _ok(polymarket.get_positions())
    except Exception as e:
        return _err(e)

@app.route("/api/activity")
def activity():
    try:
        limit = request.args.get("limit", 50, type=int)
        return _ok(polymarket.get_activity(limit))
    except Exception as e:
        return _err(e)

# ── P&L horaire ──────────────────────────────────────────────────────────────

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "history.json")

@app.route("/api/pnl/hourly")
def pnl_hourly():
    try:
        if not os.path.exists(HISTORY_FILE):
            return _ok([])
        with open(HISTORY_FILE) as f:
            history = json.load(f)

        # Regroupe les trades résolus par heure
        buckets = {}
        for t in history:
            if t.get("pnl") is None:
                continue
            ts = t.get("time", "")
            if not ts:
                continue
            try:
                dt = datetime.datetime.fromisoformat(ts)
                key = dt.strftime("%d/%m %Hh")
                if key not in buckets:
                    buckets[key] = {"heure": key, "pnl": 0.0, "trades": 0, "gagnes": 0}
                buckets[key]["pnl"]    = round(buckets[key]["pnl"] + float(t["pnl"]), 2)
                buckets[key]["trades"] += 1
                if float(t["pnl"]) > 0:
                    buckets[key]["gagnes"] += 1
            except Exception:
                continue

        result = sorted(buckets.values(), key=lambda x: x["heure"])
        # P&L cumulé
        cumul = 0.0
        for b in result:
            cumul += b["pnl"]
            b["pnl_cumul"] = round(cumul, 2)
        return _ok(result[-48:])  # 48h max
    except Exception as e:
        return _err(e)

# ── Stratégie (par bot) ───────────────────────────────────────────────────────

@app.route("/api/strategy/<bot_id>", methods=["GET"])
def get_strategy(bot_id):
    return _ok(_load_strategy(bot_id))

@app.route("/api/strategy/<bot_id>/history", methods=["GET"])
def get_strategy_history(bot_id):
    strategy = _load_strategy(bot_id)
    return _ok(strategy.get("history", []))

@app.route("/api/strategy/<bot_id>", methods=["POST"])
def save_strategy(bot_id):
    data = request.get_json()
    if not data:
        return _err("Corps JSON manquant", 400)
    strategy = _load_strategy(bot_id)
    for key in ("prompt", "enabled", "analyse_instructions", "analyse_category"):
        if key in data:
            strategy[key] = data[key]
    _save_strategy(bot_id, strategy)
    return _ok({"ok": True, "strategy": strategy})

# ── bot_strategies (Supabase réel, lu par loop_v2.py) ────────────────────────
# Écriture protégée : passe par la clé service (jamais exposée au navigateur).
# bot_strategies n'autorise plus l'écriture anon depuis le 23/06 (faille corrigée :
# n'importe qui pouvait sinon réécrire le prompt qui pilote le trading réel).

@app.route("/api/bot_strategies/<bot_id>", methods=["POST"])
def save_bot_strategy(bot_id):
    data = request.get_json()
    if not data:
        return _err("Corps JSON manquant", 400)
    allowed = {"prompt", "enabled", "analyse_instructions", "analyse_category"}
    payload = {k: v for k, v in data.items() if k in allowed}
    if not payload:
        return _err("Aucun champ autorisé dans le corps", 400)
    payload["bot_id"] = bot_id
    payload["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/bot_strategies",
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            },
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
        return _ok({"ok": True})
    except Exception as e:
        return _err(e)

# ── ProfitWeather V2 ──────────────────────────────────────────────────────────

def _supabase_get_filtered(table, params: dict):
    """Requête Supabase avec paramètres de filtre custom."""
    try:
        import urllib.request, urllib.parse
        qs  = urllib.parse.urlencode(params)
        url = f"{SUPABASE_URL}/rest/v1/{table}?{qs}"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        })
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return []

@app.route("/api/v2/trades")
def v2_trades():
    """Derniers trades de ProfitWeather V2 depuis PERF_RESET_DATE."""
    data = _supabase_get_filtered("trade_history", {
        "bot_id": "eq.polyedge2",
        "time":   f"gte.{PERF_RESET_DATE}",
        "order":  "time.desc",
        "limit":  "200",
    })
    return _ok(data if data else [])

@app.route("/api/v2/calendar")
def v2_calendar():
    """Statistiques journalières ProfitWeather V2 pour le calendrier PNL."""
    data = _supabase_get_filtered("trade_history", {
        "bot_id": "eq.polyedge2",
        "time":   f"gte.{PERF_RESET_DATE}",
        "order":  "time.asc",
        "limit":  "500",
    })
    if not data:
        return _ok({})

    # Groupement par jour (YYYY-MM-DD)
    days = {}
    for t in data:
        pnl  = t.get("pnl")
        ts   = t.get("time", "")
        day  = ts[:10] if ts else None
        if not day:
            continue
        if day not in days:
            days[day] = {"pnl": 0.0, "wins": 0, "losses": 0, "open": 0, "trades": 0}
        days[day]["trades"] += 1
        if pnl is None:
            days[day]["open"] += 1
        elif pnl > 0:
            days[day]["wins"]   += 1
            days[day]["pnl"]    += pnl
        elif pnl < 0:
            days[day]["losses"] += 1
            days[day]["pnl"]    += pnl
        # pnl == 0 → résolu sans gain/perte (rare)

    # Arrondi
    for d in days.values():
        d["pnl"] = round(d["pnl"], 2)

    return _ok(days)

# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 TradingBot — serveur Polymarket")
    print("   Dashboard : http://localhost:8080")
    print("   API       : http://localhost:5050")
    print()
    try:
        config.validate()
        polymarket.test_connection()
        print("✅ Connecté à Polymarket")
        bal = polymarket.get_balance()
        print(f"   Solde : {bal['usdc']:.2f} USDC")
    except Exception as e:
        print(f"⚠️  {e}")
        print("   → Crée bot/.env à partir de bot/.env.example")
    print()
    app.run(port=5050, debug=True, use_reloader=False)
