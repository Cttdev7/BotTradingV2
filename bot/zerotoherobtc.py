"""
zerotoherobtc.py — Bot de trading Polymarket BTC Up/Down 5 minutes.
Stratégie 100% mécanique : achète le côté >= 95% à T-30s de la clôture.
Compte Polymarket dédié, séparé de ProfitWeather V2 (variables ZTH_*).
"""

from __future__ import annotations
import sys
import os
import time
import math
import json
import logging
import requests

_PYTHON311 = os.path.expanduser("~/.pyenv/versions/3.11.9/lib/python3.11/site-packages")
if os.path.exists(_PYTHON311) and _PYTHON311 not in sys.path:
    sys.path.insert(0, _PYTHON311)

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(".env")

# ── Config ────────────────────────────────────────────────────────────────

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB      = "https://clob.polymarket.com"
POLYGON_RPC   = "https://polygon-bor-rpc.publicnode.com"
PUSD_CONTRACT = "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb"
TIMEOUT = 10

WINDOW_SECONDS         = 300   # marché toutes les 5 minutes
TRIGGER_MAX_REMAINING  = 32    # on commence à regarder à partir de 32s restantes
TRIGGER_MIN_REMAINING  = 20    # on arrête de regarder en dessous de 20s restantes
PRICE_THRESHOLD        = 0.95
BET_PCT                = 0.05
POLL_INTERVAL          = 2     # secondes entre 2 vérifications dans la fenêtre de déclenchement

ZTH_WALLET_ADDRESS = os.getenv("ZTH_WALLET_ADDRESS", "")
ZTH_PRIVATE_KEY    = os.getenv("ZTH_PRIVATE_KEY", "")
ZTH_API_KEY        = os.getenv("ZTH_API_KEY", "")
ZTH_API_SECRET     = os.getenv("ZTH_API_SECRET", "")
ZTH_API_PASSPHRASE = os.getenv("ZTH_API_PASSPHRASE", "")
ZTH_DRY_RUN        = os.getenv("ZTH_DRY_RUN", "true").lower() == "true"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("zerotoherobtc_runtime.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("zerotoherobtc")

# ── Timing & découverte du marché ────────────────────────────────────────

def current_window_end_epoch(now: float | None = None) -> int:
    """Epoch (secondes) de fin de la fenêtre de 5 min en cours."""
    now = now if now is not None else time.time()
    return int(math.ceil(now / WINDOW_SECONDS) * WINDOW_SECONDS)


def slug_for_end_epoch(end_epoch: int) -> str:
    return f"btc-updown-5m-{end_epoch}"


def fetch_market_tokens(slug: str) -> dict | None:
    """
    Récupère les infos du marché pour ce slug.
    Retourne {"condition_id": str, "up_token_id": str, "down_token_id": str}
    ou None si le marché n'existe pas encore / pas conforme.
    """
    r = requests.get(f"{GAMMA_API}/events/slug/{slug}", timeout=TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    event = r.json()
    markets = event.get("markets", [])
    if not markets:
        return None
    market = markets[0]
    raw_tokens   = market.get("clobTokenIds", "[]")
    raw_outcomes = market.get("outcomes", "[]")
    token_ids = json.loads(raw_tokens)   if isinstance(raw_tokens, str)   else raw_tokens
    outcomes  = json.loads(raw_outcomes) if isinstance(raw_outcomes, str) else raw_outcomes
    if len(token_ids) != 2 or len(outcomes) != 2:
        return None
    mapping = dict(zip(outcomes, token_ids))
    up_token   = mapping.get("Up")
    down_token = mapping.get("Down")
    if not up_token or not down_token:
        return None
    return {
        "condition_id":  market.get("conditionId", ""),
        "up_token_id":   up_token,
        "down_token_id": down_token,
    }


def best_ask_price(token_id: str) -> float | None:
    """Meilleur prix d'achat disponible (best ask) pour ce token, ou None si carnet vide."""
    r = requests.get(f"{CLOB}/book", params={"token_id": token_id}, timeout=TIMEOUT)
    r.raise_for_status()
    book = r.json()
    asks = book.get("asks", [])
    if not asks:
        return None
    return min(float(a["price"]) for a in asks)


def get_zth_balance_usdc() -> float:
    """Solde pUSD disponible on-chain pour le wallet ZeroToHeroBTC."""
    data = "0x70a08231" + ZTH_WALLET_ADDRESS[2:].lower().zfill(64)
    r = requests.post(
        POLYGON_RPC,
        json={"jsonrpc": "2.0", "method": "eth_call",
              "params": [{"to": PUSD_CONTRACT, "data": data}, "latest"], "id": 1},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    result_hex = r.json().get("result", "0x0")
    return int(result_hex, 16) / 1_000_000


_client = None

def _get_client():
    global _client
    if _client is None:
        from polymarket.clients.secure import SecureClient
        from polymarket.models.clob.api_key import ApiKeyCreds
        creds = ApiKeyCreds(apiKey=ZTH_API_KEY, secret=ZTH_API_SECRET, passphrase=ZTH_API_PASSPHRASE)
        _client = SecureClient.create(
            private_key=ZTH_PRIVATE_KEY,
            wallet=ZTH_WALLET_ADDRESS,
            credentials=creds,
        )
    return _client


def place_buy(token_id: str, amount_usdc: float) -> dict:
    """Achète amount_usdc de ce token. Simule si ZTH_DRY_RUN=true."""
    if ZTH_DRY_RUN:
        log.info(f"[DRY RUN] BUY token {token_id[:12]}… | ${amount_usdc:.2f} USDC")
        return {"dry_run": True, "token_id": token_id, "amount_usdc": amount_usdc, "status": "simulated"}

    client = _get_client()
    resp = client.place_market_order(token_id=token_id, side="BUY", amount=amount_usdc)
    making = float(resp.making_amount or 0)
    taking = float(resp.taking_amount or 0)
    price = (making / taking) if taking > 0 else 0.0
    return {
        "ok": resp.ok,
        "order_id": resp.order_id,
        "status": resp.status,
        "amount_usdc": amount_usdc,
        "price": price,
    }
