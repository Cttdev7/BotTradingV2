"""
auth.py — Signatures HMAC-SHA256 pour l'API Polymarket (L2 auth)
Module partagé entre trader.py et polymarket.py.
"""
from __future__ import annotations
import hmac
import hashlib
import base64
import time
import config


def create_auth_headers(method: str, path: str, body: str = "") -> dict:
    """Headers d'authentification L2 pour les endpoints Polymarket sécurisés."""
    if not config.API_SECRET:
        raise ValueError("API_SECRET manquant dans .env — impossible de signer les requêtes")
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
