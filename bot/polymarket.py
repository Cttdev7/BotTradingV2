"""
Wrapper Polymarket CLOB API — appels HTTP directs.
Fonctionne en lecture avec API_KEY + WALLET_ADDRESS.
Les ordres nécessiteront aussi PRIVATE_KEY + API_SECRET + API_PASSPHRASE.
"""

import hmac
import hashlib
import base64
import time
import requests
import config

BASE    = "https://clob.polymarket.com"
TIMEOUT = 10

# ── Auth ─────────────────────────────────────────────────────────────────────

def _public_headers() -> dict:
    """Headers pour endpoints authentifiés (lecture) avec juste l'API Key."""
    return {
        "Authorization": f"Bearer {config.API_KEY}",
        "Content-Type":  "application/json",
    }

def _signed_headers(method: str, path: str, body: str = "") -> dict:
    """Headers HMAC-SHA256 complets (pour les ordres — Phase 2)."""
    ts = str(int(time.time() * 1000))
    message = ts + method + path + body
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
    """Teste la connexion sur un endpoint public."""
    r = requests.get(f"{BASE}/markets", params={"limit": 1}, timeout=TIMEOUT)
    r.raise_for_status()
    return True

# ── Endpoints publics (aucune auth) ──────────────────────────────────────────

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

def get_prices(token_ids: list) -> dict:
    """Prix actuels pour une liste de tokens."""
    r = requests.get(
        f"{BASE}/prices",
        params={"token_id": token_ids},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()

# ── Endpoints avec API Key (lecture du compte) ───────────────────────────────

def get_balance() -> dict:
    """Solde USDC — essaie plusieurs endpoints selon la version de l'API."""
    paths = [
        "/balance-allowance/total-usdc",
        "/balance-allowance",
        "/account/balance",
    ]
    headers = _public_headers()
    for path in paths:
        try:
            r = requests.get(f"{BASE}{path}", headers=headers, timeout=TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                usdc = float(data.get("balance", data.get("total", data.get("amount", 0))))
                return {"usdc": usdc}
        except Exception:
            continue
    return {"usdc": 0, "note": "Solde non disponible avec cette clé API"}

def get_positions() -> list:
    """Positions ouvertes du wallet."""
    r = requests.get(
        f"{BASE}/positions",
        headers=_public_headers(),
        params={"user": config.WALLET_ADDRESS},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("data", [])

def get_open_orders() -> list:
    """Ordres ouverts du wallet."""
    r = requests.get(
        f"{BASE}/orders",
        headers=_public_headers(),
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("data", [])
