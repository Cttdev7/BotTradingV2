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
TRIGGER_MAX_REMAINING  = 60    # on commence à surveiller en continu à partir de 60s restantes
TRIGGER_MIN_REMAINING  = 2     # on arrête juste avant la clôture (marge pour l'exécution de l'ordre)
PRICE_THRESHOLD        = 0.95
BET_PCT                = 0.05
POLL_INTERVAL          = 2     # secondes entre 2 vérifications dans la fenêtre de déclenchement

ZTH_WALLET_ADDRESS = os.getenv("ZTH_WALLET_ADDRESS", "")
ZTH_PRIVATE_KEY    = os.getenv("ZTH_PRIVATE_KEY", "")
ZTH_API_KEY        = os.getenv("ZTH_API_KEY", "")
ZTH_API_SECRET     = os.getenv("ZTH_API_SECRET", "")
ZTH_API_PASSPHRASE = os.getenv("ZTH_API_PASSPHRASE", "")
ZTH_DRY_RUN        = os.getenv("ZTH_DRY_RUN", "true").lower() == "true"

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
SIMULATED_BALANCE_USDC = 100.0  # solde fictif utilisé pour la mise en DRY_RUN (vrai solde on-chain = 0)

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


def _sb_headers() -> dict:
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }


def insert_trade(slug: str, end_epoch: int, condition_id: str, outcome: str, price: float, amount_usdc: float) -> None:
    """Enregistre un trade (simulé ou réel) dans Supabase pour calcul ultérieur du taux de victoire."""
    payload = {
        "slug": slug,
        "end_epoch": end_epoch,
        "condition_id": condition_id,
        "outcome": outcome,
        "price_at_buy": price,
        "amount_usdc": amount_usdc,
        "dry_run": ZTH_DRY_RUN,
        "resolved": False,
    }
    try:
        r = requests.post(
            f"{SB_URL}/rest/v1/zerotoherobtc_trades",
            json=payload,
            headers={**_sb_headers(), "Prefer": "return=minimal"},
            timeout=10,
        )
        if r.status_code not in (200, 201):
            log.warning(f"insert_trade erreur {r.status_code} : {r.text[:200]}")
    except Exception as e:
        log.warning(f"insert_trade : {e}")


def fetch_market_outcome(slug: str) -> str | None:
    """Retourne le côté gagnant ('Up' ou 'Down') si le marché est résolu, sinon None."""
    r = requests.get(f"{GAMMA_API}/events/slug/{slug}", timeout=TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    event = r.json()
    markets = event.get("markets", [])
    if not markets:
        return None
    market = markets[0]
    raw_prices   = market.get("outcomePrices", "[]")
    raw_outcomes = market.get("outcomes", "[]")
    prices   = json.loads(raw_prices)   if isinstance(raw_prices, str)   else raw_prices
    outcomes = json.loads(raw_outcomes) if isinstance(raw_outcomes, str) else raw_outcomes
    if len(prices) != 2 or len(outcomes) != 2:
        return None
    for outcome, price in zip(outcomes, prices):
        if float(price) >= 0.99:
            return outcome
    return None


def resolve_pending_trades() -> None:
    """Vérifie les trades non résolus dont la fenêtre est terminée depuis >60s et enregistre le résultat réel."""
    now = time.time()
    try:
        r = requests.get(
            f"{SB_URL}/rest/v1/zerotoherobtc_trades",
            params={"resolved": "eq.false", "select": "id,slug,end_epoch,outcome"},
            headers=_sb_headers(),
            timeout=10,
        )
        r.raise_for_status()
        pending = r.json()
    except Exception as e:
        log.warning(f"resolve_pending_trades fetch : {e}")
        return

    for trade in pending:
        if now < trade["end_epoch"] + 60:
            continue
        try:
            actual = fetch_market_outcome(trade["slug"])
        except Exception as e:
            log.warning(f"resolve_pending_trades fetch_outcome slug={trade['slug']} : {e}")
            continue
        if actual is None:
            continue
        win = (actual == trade["outcome"])
        try:
            requests.patch(
                f"{SB_URL}/rest/v1/zerotoherobtc_trades",
                params={"id": f"eq.{trade['id']}"},
                json={
                    "resolved": True,
                    "actual_outcome": actual,
                    "win": win,
                    "resolved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                headers={**_sb_headers(), "Prefer": "return=minimal"},
                timeout=10,
            )
        except Exception as e:
            log.warning(f"resolve_pending_trades update id={trade['id']} : {e}")


def run_cycle() -> None:
    """Traite un cycle de marché complet : attend T-30s, vérifie le seuil, trade si besoin."""
    resolve_pending_trades()

    end_epoch = current_window_end_epoch()
    slug = slug_for_end_epoch(end_epoch)
    log.info(f"Cycle en cours : {slug} (fin dans {end_epoch - time.time():.0f}s)")

    traded = False
    while True:
        remaining = end_epoch - time.time()
        if remaining <= 0:
            break
        if remaining > TRIGGER_MAX_REMAINING:
            time.sleep(min(POLL_INTERVAL, remaining - TRIGGER_MAX_REMAINING))
            continue
        if remaining < TRIGGER_MIN_REMAINING:
            break
        if traded:
            time.sleep(POLL_INTERVAL)
            continue

        tokens = fetch_market_tokens(slug)
        if not tokens:
            log.warning(f"Marché {slug} introuvable à {remaining:.0f}s restantes — skip")
            time.sleep(POLL_INTERVAL)
            continue

        up_price   = best_ask_price(tokens["up_token_id"])
        down_price = best_ask_price(tokens["down_token_id"])
        log.info(f"  T-{remaining:.0f}s | Up={up_price} Down={down_price}")

        candidate = None
        if up_price is not None and up_price >= PRICE_THRESHOLD:
            candidate = ("Up", tokens["up_token_id"], up_price)
        elif down_price is not None and down_price >= PRICE_THRESHOLD:
            candidate = ("Down", tokens["down_token_id"], down_price)

        if candidate:
            outcome, token_id, price = candidate
            balance = SIMULATED_BALANCE_USDC if ZTH_DRY_RUN else get_zth_balance_usdc()
            bet = round(balance * BET_PCT, 2)
            if bet <= 0:
                log.warning(f"Solde insuffisant ({balance} USDC) — pas de trade")
            else:
                log.info(f"  -> ACHAT {outcome} @ {price:.2f} pour ${bet} USDC")
                result = place_buy(token_id, bet)
                log.info(f"  Résultat: {result}")
                insert_trade(slug, end_epoch, tokens["condition_id"], outcome, price, bet)
            traded = True

        time.sleep(POLL_INTERVAL)

    log.info(f"Fin du cycle {slug}")


def main() -> None:
    log.info(f"ZeroToHeroBTC démarré — DRY_RUN={ZTH_DRY_RUN}")
    while True:
        try:
            run_cycle()
        except Exception as e:
            log.error(f"Erreur cycle: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
