"""
Serveur API local — TradingBot Polymarket
Lance avec : python server.py
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

# Fichier de persistance pour la stratégie du bot
STRATEGY_FILE = os.path.join(os.path.dirname(__file__), "strategy.json")

_client = None

def _get_client():
    global _client
    if _client is None:
        config.validate()
        _client = polymarket.get_client()
    return _client

def _load_strategy() -> dict:
    if os.path.exists(STRATEGY_FILE):
        with open(STRATEGY_FILE) as f:
            return json.load(f)
    return {"prompt": "", "name": "Polymarket Edge", "enabled": False}

def _save_strategy(data: dict):
    with open(STRATEGY_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Status ───────────────────────────────────────────────────────────────────

@app.route("/api/status")
def status():
    try:
        client = _get_client()
        bal = polymarket.get_balance(client)
        return jsonify({
            "connected": True,
            "wallet": config.WALLET_ADDRESS,
            "balance": bal,
        })
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)}), 503

# ── Balance ──────────────────────────────────────────────────────────────────

@app.route("/api/balance")
def balance():
    try:
        return jsonify(polymarket.get_balance(_get_client()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Marchés ──────────────────────────────────────────────────────────────────

@app.route("/api/markets")
def markets():
    try:
        data = polymarket.get_markets(_get_client())
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/markets/<condition_id>")
def market_detail(condition_id):
    try:
        return jsonify(polymarket.get_market(_get_client(), condition_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/orderbook/<token_id>")
def orderbook(token_id):
    try:
        return jsonify(polymarket.get_order_book(_get_client(), token_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Positions & ordres ───────────────────────────────────────────────────────

@app.route("/api/positions")
def positions():
    try:
        return jsonify(polymarket.get_positions(_get_client()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/orders")
def orders():
    try:
        return jsonify(polymarket.get_open_orders(_get_client()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Stratégie (prompt) ───────────────────────────────────────────────────────

@app.route("/api/strategy", methods=["GET"])
def get_strategy():
    return jsonify(_load_strategy())

@app.route("/api/strategy", methods=["POST"])
def save_strategy():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Corps JSON manquant"}), 400
    strategy = _load_strategy()
    strategy.update({k: data[k] for k in ("prompt", "name", "enabled") if k in data})
    _save_strategy(strategy)
    return jsonify({"ok": True, "strategy": strategy})

# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 TradingBot — serveur Polymarket")
    print("   Dashboard : http://localhost:8080")
    print("   API       : http://localhost:5000")
    print()
    try:
        config.validate()
        _client = polymarket.get_client()
        print("✅ Connecté à Polymarket")
    except Exception as e:
        print(f"⚠️  Pas de connexion : {e}")
        print("   → Copie bot/.env.example en bot/.env et remplis tes clés")
    print()
    app.run(port=5000, debug=True, use_reloader=False)
