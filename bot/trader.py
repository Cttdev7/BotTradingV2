"""
trader.py — Exécution des ordres sur Polymarket

Place les ordres de marché (buy/sell) via le CLOB API.
Nécessite PRIVATE_KEY + API_SECRET + API_PASSPHRASE dans .env.

En mode simulation (DRY_RUN=true), les ordres sont loggés sans être envoyés.
"""

from __future__ import annotations
import json
import time
import hmac
import hashlib
import base64
import requests
import os
import config

CLOB    = "https://clob.polymarket.com"
TIMEOUT = 15
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"  # sécurité par défaut

# ── Auth L2 ───────────────────────────────────────────────────────────────────

def _auth_headers(method: str, path: str, body: str = "") -> dict:
    if not config.API_SECRET:
        raise ValueError("API_SECRET manquant dans .env — impossible de signer les ordres")
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

# ── Infos marché ──────────────────────────────────────────────────────────────

def get_token_id(condition_id: str, outcome: str) -> str | None:
    """Récupère le token_id d'un marché pour un outcome donné."""
    r = requests.get(f"{CLOB}/markets/{condition_id}", timeout=TIMEOUT)
    r.raise_for_status()
    market = r.json()
    for token in market.get("tokens", []):
        if token.get("outcome", "").lower() == outcome.lower():
            return token.get("token_id")
    return None

def get_best_price(token_id: str, side: str) -> float | None:
    """Récupère le meilleur prix disponible (bid pour sell, ask pour buy)."""
    r = requests.get(f"{CLOB}/book", params={"token_id": token_id}, timeout=TIMEOUT)
    r.raise_for_status()
    book = r.json()
    if side == "buy":
        asks = book.get("asks", [])
        if asks:
            return float(sorted(asks, key=lambda x: float(x["price"]))[0]["price"])
    else:
        bids = book.get("bids", [])
        if bids:
            return float(sorted(bids, key=lambda x: float(x["price"]), reverse=True)[0]["price"])
    return None

# ── Placement d'ordres ────────────────────────────────────────────────────────

def place_market_order(condition_id: str, outcome: str, side: str, amount_usdc: float) -> dict:
    """
    Place un ordre de marché.
    side    : "buy" ou "sell"
    outcome : "Yes" ou "No"
    amount_usdc : montant en USDC à engager

    Retourne un dict avec le résultat ou l'erreur.
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

    # Récupère le token_id
    token_id = get_token_id(condition_id, outcome)
    if not token_id:
        raise ValueError(f"Token introuvable : {condition_id} / {outcome}")

    # Récupère le meilleur prix
    price = get_best_price(token_id, side)
    if not price:
        raise ValueError(f"Carnet d'ordres vide pour {token_id}")

    # Calcule la quantité de shares
    size = round(amount_usdc / price, 2)

    order = {
        "token_id":   token_id,
        "price":      price,
        "side":       side.upper(),
        "size":       size,
        "type":       "FOK",   # Fill or Kill — s'exécute immédiatement ou annulé
        "fee_rate_bps": 0,
    }
    body = json.dumps(order)
    path = "/order"

    r = requests.post(
        f"{CLOB}{path}",
        headers=_auth_headers("POST", path, body),
        data=body,
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def cancel_all_orders() -> dict:
    """Annule tous les ordres ouverts."""
    if DRY_RUN:
        print("[DRY RUN] Annulation de tous les ordres")
        return {"dry_run": True}
    path = "/orders"
    r = requests.delete(
        f"{CLOB}{path}",
        headers=_auth_headers("DELETE", path),
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()
