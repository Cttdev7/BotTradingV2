"""
trader.py — Exécution des ordres sur Polymarket via le nouveau polymarket-client SDK.
En mode simulation (DRY_RUN=true), les ordres sont loggés sans être envoyés.
"""

from __future__ import annotations
import sys
import os
import config

# Python 3.11 requis pour polymarket-client
_PYTHON311 = os.path.expanduser("~/.pyenv/versions/3.11.9/lib/python3.11/site-packages")
if os.path.exists(_PYTHON311) and _PYTHON311 not in sys.path:
    sys.path.insert(0, _PYTHON311)

TIMEOUT = 15
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

_client = None

def _get_client():
    global _client
    if _client is None:
        from polymarket.clients.secure import SecureClient
        from polymarket.models.clob.api_key import ApiKeyCreds
        creds = ApiKeyCreds(
            apiKey=config.API_KEY,
            secret=config.API_SECRET,
            passphrase=config.API_PASSPHRASE,
        )
        _client = SecureClient.create(
            private_key=config.PRIVATE_KEY,
            wallet=config.WALLET_ADDRESS,
            credentials=creds,
        )
    return _client

# ── Infos marché ──────────────────────────────────────────────────────────────

def get_token_id(condition_id: str, outcome: str) -> "str | None":
    import requests
    r = requests.get(f"https://clob.polymarket.com/markets/{condition_id}", timeout=TIMEOUT)
    r.raise_for_status()
    market = r.json()
    for token in market.get("tokens", []):
        if token.get("outcome", "").lower() == outcome.lower():
            return token.get("token_id")
    return None

# ── Placement d'ordres ────────────────────────────────────────────────────────

def place_market_order(condition_id: str, outcome: str, side: str, amount_usdc: float) -> dict:
    """
    Place un ordre de marché via le nouveau polymarket-client SDK.
    side    : "buy" ou "sell"
    outcome : "Yes" ou "No"
    amount_usdc : montant en USDC à engager
    """
    if DRY_RUN:
        result = {
            "dry_run": True,
            "condition_id": condition_id,
            "outcome": outcome,
            "side": side,
            "amount_usdc": amount_usdc,
            "status": "simulated",
        }
        print(f"[DRY RUN] {side.upper()} {outcome} sur {condition_id[:12]}… | ${amount_usdc:.2f} USDC")
        return result

    if not config.can_trade():
        raise ValueError("Clés incomplètes — PRIVATE_KEY, API_SECRET et API_PASSPHRASE requis pour trader")

    token_id = get_token_id(condition_id, outcome)
    if not token_id:
        raise ValueError(f"Token introuvable : {condition_id} / {outcome}")

    client = _get_client()
    is_sell = side.lower() == "sell"
    resp = client.place_market_order(
        token_id=token_id,
        side="SELL" if is_sell else "BUY",
        # BUY  : amount en USDC | SELL : shares = nombre de tokens à vendre
        **{"shares": amount_usdc} if is_sell else {"amount": amount_usdc},
    )
    making = float(resp.making_amount or 0)
    taking = float(resp.taking_amount or 0)
    price  = (making / taking) if taking > 0 else 0.0  # 0 → loop.py utilisera yes_price comme fallback
    return {
        "ok":            resp.ok,
        "order_id":      resp.order_id,
        "status":        resp.status,
        "making_amount": making,
        "taking_amount": taking,
        "price":         price,
    }


def cancel_all_orders() -> dict:
    if DRY_RUN:
        print("[DRY RUN] Annulation de tous les ordres")
        return {"dry_run": True}
    client = _get_client()
    resp = client.cancel_all()
    return {"status": str(resp)}
