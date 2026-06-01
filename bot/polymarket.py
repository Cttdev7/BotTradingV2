"""
Wrapper Polymarket API — appels HTTP directs.
- Données publiques  : clob.polymarket.com
- Données du compte  : data-api.polymarket.com (lecture par adresse wallet)
- Ordres (Phase 2)   : clob.polymarket.com avec auth L2 complète
"""

import hmac
import hashlib
import base64
import time
import requests
import config

CLOB     = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
TIMEOUT  = 10

# ── Auth (Phase 2 — ordres) ───────────────────────────────────────────────────

def _signed_headers(method: str, path: str, body: str = "") -> dict:
    """Headers HMAC-SHA256 complets — nécessaires pour passer des ordres."""
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
    r = requests.get(f"{CLOB}/markets", params={"limit": 1}, timeout=TIMEOUT)
    r.raise_for_status()
    return True

# ── Marchés — CLOB (publics) ──────────────────────────────────────────────────

def get_markets(limit: int = 50) -> list:
    r = requests.get(
        f"{CLOB}/markets",
        params={"next_cursor": "MA==", "limit": limit},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("data", [])

def get_market(condition_id: str) -> dict:
    r = requests.get(f"{CLOB}/markets/{condition_id}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def get_order_book(token_id: str) -> dict:
    r = requests.get(f"{CLOB}/book", params={"token_id": token_id}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

# ── Compte — data-api (lecture par adresse) ───────────────────────────────────

def _addr() -> str:
    """Adresse wallet en minuscules (format attendu par data-api)."""
    return config.WALLET_ADDRESS.lower()

def get_positions() -> list:
    """Positions ouvertes — retourne [] si wallet vide ou timeout."""
    try:
        r = requests.get(
            f"{DATA_API}/positions",
            params={"user": _addr(), "sizeThreshold": "0.01"},
            timeout=TIMEOUT,
        )
        if r.status_code in (408, 504):
            return []
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return []

def get_balance() -> dict:
    """Valeur totale du portefeuille — retourne 0 si wallet vide ou timeout."""
    try:
        r = requests.get(
            f"{DATA_API}/value",
            params={"user": _addr()},
            timeout=TIMEOUT,
        )
        if r.status_code in (408, 504):
            return {"usdc": 0.0}
        r.raise_for_status()
        data = r.json()
        value = float(data[0]["value"]) if data else 0.0
        return {"usdc": value}
    except requests.exceptions.Timeout:
        return {"usdc": 0.0}

def get_activity(limit: int = 50) -> list:
    """Historique des trades du wallet."""
    try:
        r = requests.get(
            f"{DATA_API}/activity",
            params={"user": _addr(), "limit": limit},
            timeout=TIMEOUT,
        )
        if r.status_code in (408, 504):
            return []
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        return []
