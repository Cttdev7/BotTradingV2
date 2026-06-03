"""
Wrapper Polymarket API — appels HTTP directs.
- Données publiques  : clob.polymarket.com
- Données du compte  : data-api.polymarket.com (lecture par adresse wallet)
- Ordres (Phase 2)   : clob.polymarket.com avec auth L2 complète
"""

import requests
import config
from auth import create_auth_headers

CLOB      = "https://clob.polymarket.com"
DATA_API  = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
TIMEOUT   = 10

# ── Connexion ─────────────────────────────────────────────────────────────────

def test_connection() -> bool:
    r = requests.get(f"{CLOB}/markets", params={"limit": 1}, timeout=TIMEOUT)
    r.raise_for_status()
    return True

# ── Marchés — CLOB (publics) ──────────────────────────────────────────────────

def get_markets(limit: int = 50) -> list:
    """Marchés CLOB (peut inclure des marchés fermés)."""
    r = requests.get(
        f"{CLOB}/markets",
        params={"next_cursor": "MA==", "limit": limit},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("data", [])

def get_active_markets(limit: int = 50) -> list:
    """Marchés actifs via Gamma API — triés par volume, Yes/No uniquement."""
    r = requests.get(
        f"{GAMMA_API}/markets",
        params={
            "limit":      limit,
            "active":     "true",
            "closed":     "false",
            "order":      "volume24hr",
            "ascending":  "false",
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    markets = r.json()
    if not isinstance(markets, list):
        return []
    import json as _json
    # Normalise les champs pour compatibilité avec le reste du code
    result = []
    for m in markets:
        raw_prices   = m.get("outcomePrices", [])
        raw_outcomes = m.get("outcomes", [])
        # Ces champs peuvent être des strings JSON ou des listes Python
        prices   = _json.loads(raw_prices)   if isinstance(raw_prices, str)   else raw_prices
        outcomes = _json.loads(raw_outcomes) if isinstance(raw_outcomes, str) else raw_outcomes
        tokens   = []
        for outcome, price in zip(outcomes, prices):
            tokens.append({"outcome": outcome, "price": float(price or 0)})
        result.append({
            "condition_id": m.get("conditionId", ""),
            "question":     m.get("question", ""),
            "volume":       float(m.get("volume24hr") or m.get("volume") or 0),
            "active":       m.get("active", True),
            "closed":       m.get("closed", False),
            "tokens":       tokens,
        })
    return result

def get_market(condition_id: str) -> dict:
    r = requests.get(f"{CLOB}/markets/{condition_id}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def get_order_book(token_id: str) -> dict:
    r = requests.get(f"{CLOB}/book", params={"token_id": token_id}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

# ── Wallet Polygon (RPC) ──────────────────────────────────────────────────────

POLYGON_RPC   = "https://polygon-bor-rpc.publicnode.com"
USDC_CONTRACT = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"   # USDC natif
USDCE_CONTRACT= "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"   # USDC.e bridgé

def _rpc_call(method: str, params: list, id: int = 1) -> str:
    r = requests.post(POLYGON_RPC,
        json={"jsonrpc": "2.0", "method": method, "params": params, "id": id},
        timeout=TIMEOUT)
    r.raise_for_status()
    return r.json().get("result", "0x0")

def get_polygon_balance() -> dict:
    """Solde POL natif + USDC sur le wallet Polygon."""
    wallet = config.WALLET_ADDRESS
    data   = "0x70a08231" + wallet[2:].lower().zfill(64)
    try:
        pol_hex   = _rpc_call("eth_getBalance", [wallet, "latest"], 1)
        usdc_hex  = _rpc_call("eth_call", [{"to": USDC_CONTRACT,  "data": data}, "latest"], 2)
        usdce_hex = _rpc_call("eth_call", [{"to": USDCE_CONTRACT, "data": data}, "latest"], 3)
        return {
            "pol":   round(int(pol_hex,   16) / 1e18, 4),
            "usdc":  round(int(usdc_hex,  16) / 1e6,  2),
            "usdce": round(int(usdce_hex, 16) / 1e6,  2),
            "wallet": wallet,
        }
    except Exception as e:
        return {"pol": 0, "usdc": 0, "usdce": 0, "wallet": wallet, "error": str(e)}

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
        value = float(data[0]["value"]) if data and isinstance(data, list) and len(data) > 0 else 0.0
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
