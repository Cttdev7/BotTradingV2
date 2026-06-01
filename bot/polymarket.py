"""
Wrapper Polymarket CLOB API — appels HTTP directs.
Pas de dépendance externe au SDK officiel.
"""

import hmac
import hashlib
import base64
import time
import requests
import config

BASE = "https://clob.polymarket.com"
TIMEOUT = 10

# ── Auth ─────────────────────────────────────────────────────────────────────

def _auth_headers(method: str, path: str, body: str = "") -> dict:
    """Headers d'authentification L2 (HMAC-SHA256 sur la clé API)."""
    ts = str(int(time.time() * 1000))
    message = ts + method + path + body
    # Polymarket encode le secret en base64
    try:
        raw_key = base64.b64decode(config.API_SECRET)
    except Exception:
        raw_key = config.API_SECRET.encode()
    sig = base64.b64encode(
        hmac.new(raw_key, message.encode(), hashlib.sha256).digest()
    ).decode()
    return {
        "POLY_ADDRESS":    config.WALLET_ADDRESS,
        "POLY_SIGNATURE":  sig,
        "POLY_TIMESTAMP":  ts,
        "POLY_API_KEY":    config.API_KEY,
        "POLY_PASSPHRASE": config.API_PASSPHRASE,
        "Content-Type":    "application/json",
    }

# ── Connexion ─────────────────────────────────────────────────────────────────

def test_connection() -> bool:
    """Teste la connexion (endpoint public)."""
    r = requests.get(f"{BASE}/markets", params={"limit": 1}, timeout=TIMEOUT)
    r.raise_for_status()
    return True

# ── Endpoints publics (pas d'auth) ───────────────────────────────────────────

def get_markets(limit: int = 50) -> list:
    """Marchés actifs, première page."""
    r = requests.get(
        f"{BASE}/markets",
        params={"next_cursor": "MA==", "limit": limit},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("data", [])

def get_market(condition_id: str) -> dict:
    """Détail d'un marché."""
    r = requests.get(f"{BASE}/markets/{condition_id}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def get_order_book(token_id: str) -> dict:
    """Carnet d'ordres pour un token."""
    r = requests.get(f"{BASE}/book", params={"token_id": token_id}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

# ── Endpoints authentifiés ───────────────────────────────────────────────────

def get_balance() -> dict:
    """Solde USDC du wallet."""
    path = "/balance-allowance/total-usdc"
    r = requests.get(
        f"{BASE}{path}",
        headers=_auth_headers("GET", path),
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    usdc = float(data.get("balance", data.get("total", data.get("amount", 0))))
    return {"usdc": usdc}

def get_positions() -> list:
    """Positions ouvertes du wallet."""
    path = "/positions"
    r = requests.get(
        f"{BASE}{path}",
        headers=_auth_headers("GET", path),
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("data", [])

def get_open_orders() -> list:
    """Ordres ouverts du wallet."""
    path = "/orders"
    r = requests.get(
        f"{BASE}{path}",
        headers=_auth_headers("GET", path),
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("data", [])
