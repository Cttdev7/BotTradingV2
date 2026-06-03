"""
Serveur API local — TradingBot Polymarket
Lance avec : python3 bot/server.py
Écoute sur  : http://localhost:5000
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import polymarket
import mistral
import config
import json
import os
import datetime

app = Flask(__name__)
CORS(app, origins=["http://localhost:8080"])

STRATEGY_FILE = os.path.join(os.path.dirname(__file__), "strategy.json")

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

# ── Analyse Mistral ───────────────────────────────────────────────────────────

ANALYSES_FILE = os.path.join(os.path.dirname(__file__), "analyses.json")

def _load_analyses() -> list:
    if os.path.exists(ANALYSES_FILE):
        with open(ANALYSES_FILE) as f:
            return json.load(f)
    return []

def _save_analysis(result: dict):
    analyses = _load_analyses()
    analyses.insert(0, {"time": datetime.datetime.now().isoformat(), **result})
    with open(ANALYSES_FILE, "w") as f:
        json.dump(analyses[:20], f, indent=2, ensure_ascii=False)  # garde les 20 dernières

@app.route("/api/analyse", methods=["POST"])
def analyse():
    try:
        data         = request.get_json() or {}
        category     = data.get("category", "tout")
        min_volume   = float(data.get("min_volume", 5000))
        instructions = data.get("instructions", "").strip()
        markets      = polymarket.get_active_markets(limit=100)
        result       = mistral.analyse(markets, category, min_volume, instructions)
        _save_analysis(result)
        return _ok(result)
    except Exception as e:
        return _err(e)

@app.route("/api/analyse/history", methods=["GET"])
def analyse_history():
    return _ok(_load_analyses())

# ── Agent Météo (Supabase + fallback JSON local) ──────────────────────────────

SUPABASE_URL     = os.getenv("SUPABASE_URL", "https://obqkqhlqlowxrxbyvktl.supabase.co")
SUPABASE_KEY     = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9icWtxaGxxbG93eHJ4Ynl2a3RsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA1MDAyNzksImV4cCI6MjA5NjA3NjI3OX0.YhuQqvqxNJmjoBYdFnmTa1aa_v8mmh3uRjrg8I3c728")
METEO_RAPPORTS   = os.path.join(os.path.dirname(__file__), "meteo_rapports.json")
METEO_TRACKING   = os.path.join(os.path.dirname(__file__), "meteo_tracking.json")
METEO_RESUMES    = os.path.join(os.path.dirname(__file__), "meteo_resumes.json")

def _supabase_get(table, order="created_at", limit=1):
    try:
        import urllib.request
        url = f"{SUPABASE_URL}/rest/v1/{table}?order={order}.desc&limit={limit}"
        req = urllib.request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        })
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return None

@app.route("/api/meteo/rapport")
def meteo_rapport():
    data = _supabase_get("meteo_rapports", limit=1)
    if data:
        return _ok(data[0] if data else {})
    if os.path.exists(METEO_RAPPORTS):
        with open(METEO_RAPPORTS) as f:
            rapports = json.load(f)
        return _ok(rapports[0] if rapports else {})
    return _ok({})

@app.route("/api/meteo/tracking")
def meteo_tracking():
    data = _supabase_get("meteo_tracking", order="created_at", limit=100)
    if data is not None:
        return _ok(data)
    if os.path.exists(METEO_TRACKING):
        with open(METEO_TRACKING) as f:
            return _ok(json.load(f))
    return _ok([])

@app.route("/api/meteo/resumes")
def meteo_resumes():
    data = _supabase_get("meteo_resumes", order="created_at", limit=90)
    if data is not None:
        return _ok(data)
    if os.path.exists(METEO_RESUMES):
        with open(METEO_RESUMES) as f:
            return _ok(json.load(f))
    return _ok([])

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
