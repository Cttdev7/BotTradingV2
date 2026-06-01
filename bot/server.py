"""
Serveur API local — TradingBot Polymarket
Lance avec : python3 bot/server.py
Écoute sur  : http://localhost:5000
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import polymarket
import config
import json
import os

app = Flask(__name__)
CORS(app, origins=["http://localhost:8080"])

STRATEGY_FILE = os.path.join(os.path.dirname(__file__), "strategy.json")

# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_strategy() -> dict:
    if os.path.exists(STRATEGY_FILE):
        with open(STRATEGY_FILE) as f:
            return json.load(f)
    return {"prompt": "", "name": "Polymarket Edge", "enabled": False}

def _save_strategy(data: dict):
    with open(STRATEGY_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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

# ── Stratégie ────────────────────────────────────────────────────────────────

@app.route("/api/strategy", methods=["GET"])
def get_strategy():
    return _ok(_load_strategy())

@app.route("/api/strategy", methods=["POST"])
def save_strategy():
    data = request.get_json()
    if not data:
        return _err("Corps JSON manquant", 400)
    strategy = _load_strategy()
    for key in ("prompt", "name", "enabled"):
        if key in data:
            strategy[key] = data[key]
    _save_strategy(strategy)
    return _ok({"ok": True, "strategy": strategy})

# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 TradingBot — serveur Polymarket")
    print("   Dashboard : http://localhost:8080")
    print("   API       : http://localhost:5000")
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
    app.run(port=5000, debug=True, use_reloader=False)
