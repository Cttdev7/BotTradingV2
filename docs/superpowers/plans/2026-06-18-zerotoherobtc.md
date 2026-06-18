# ZeroToHeroBTC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Polymarket trading bot (`bot/zerotoherobtc.py`) that mechanically buys the dominant side (Up or Down) on the recurring `btc-updown-5m-{timestamp}` market whenever its price reaches ≥95% with ~30 seconds left before the 5-minute window closes.

**Architecture:** Single self-contained script, no shared imports from the existing `config.py`/`trader.py`/`pm_api.py` (those stay dedicated to the ProfitWeather account). It computes the current 5-minute window from the wall clock, polls Gamma API for the market's token IDs, polls the CLOB order book for best-ask prices near the close, and places a market BUY via a dedicated `SecureClient` instance using `ZTH_*` credentials. No AI call, no Supabase persistence — console + local log file only.

**Tech Stack:** Python 3.11 (`~/.pyenv/versions/3.11.9/bin/python3` — required for the `polymarket-client` SDK), `requests`, `python-dotenv`, `polymarket-client` (`SecureClient`). No pytest in this repo — tests follow the existing project convention of plain `assert`-based scripts (`bot/test_*.py`) run directly with `python3`, executed and visually confirmed rather than wired into a test runner.

## Global Constraints

- Single file: `bot/zerotoherobtc.py` — no new shared modules, no edits to `config.py`/`trader.py`/`pm_api.py`/`loop_v2.py`.
- Env vars use the `ZTH_` prefix exclusively: `ZTH_WALLET_ADDRESS`, `ZTH_PRIVATE_KEY`, `ZTH_API_KEY`, `ZTH_API_SECRET`, `ZTH_API_PASSPHRASE`, `ZTH_DRY_RUN` — already present and verified in `bot/.env`.
- `PRICE_THRESHOLD = 0.95` — hard-coded, not configurable at runtime, no AI override.
- `BET_PCT = 0.05` — 5% of on-chain USDC/pUSD balance per trade.
- No frequency cap — every qualifying 5-minute cycle trades.
- No Claude/Anthropic call anywhere in this bot.
- No Supabase table — logging is console + `bot/zerotoherobtc_runtime.log` only.
- `ZTH_DRY_RUN=true` is the current `.env` value and must stay the default behavior (simulated orders, logged not sent) until the user flips it manually.
- Trigger window: continuous monitoring from 60s remaining down to 2s remaining (updated 2026-06-18 from the original 20-32s narrow band), exactly one trade per market window.

---

### Task 1: Window timing + market discovery

**Files:**
- Create: `bot/zerotoherobtc.py`
- Test: `bot/test_zth_timing.py`

**Interfaces:**
- Produces: `current_window_end_epoch(now: float | None = None) -> int`, `slug_for_end_epoch(end_epoch: int) -> str`, `fetch_market_tokens(slug: str) -> dict | None` (keys: `condition_id`, `up_token_id`, `down_token_id`)

- [ ] **Step 1: Create `bot/zerotoherobtc.py` with header, config, and the two pure timing functions**

```python
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
```

- [ ] **Step 2: Write the test for the pure timing functions**

Create `bot/test_zth_timing.py`:

```python
"""Test des fonctions de timing pures de zerotoherobtc.py (pas d'appel réseau)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from zerotoherobtc import current_window_end_epoch, slug_for_end_epoch

# 1781808300 est un multiple exact de 300 (confirmé via l'event réel
# btc-updown-5m-1781808300 pendant le design) -> juste avant cette frontière,
# la fin de fenêtre attendue est ce même timestamp.
assert current_window_end_epoch(1781808299) == 1781808300, "doit arrondir au prochain multiple de 300"
assert current_window_end_epoch(1781808300) == 1781808300, "pile sur la frontière -> elle-même"
assert current_window_end_epoch(1781808001) == 1781808300, "doit arrondir au-dessus, pas en dessous"
assert current_window_end_epoch(1781808300 - 300) == 1781808300 - 300, "frontière précédente"

assert slug_for_end_epoch(1781808300) == "btc-updown-5m-1781808300"

print("✅ Tous les tests de timing passent")
```

- [ ] **Step 3: Run the test and verify it fails first (file doesn't exist yet check), then passes**

Run:
```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2/bot" && ~/.pyenv/versions/3.11.9/bin/python3 test_zth_timing.py
```
Expected output:
```
✅ Tous les tests de timing passent
```
If any `assert` fails, Python prints `AssertionError: <message>` and a traceback — fix `current_window_end_epoch` until all four assertions pass.

- [ ] **Step 4: Manually verify `fetch_market_tokens` against the live API**

Run:
```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2/bot" && ~/.pyenv/versions/3.11.9/bin/python3 -c "
from zerotoherobtc import current_window_end_epoch, slug_for_end_epoch, fetch_market_tokens
slug = slug_for_end_epoch(current_window_end_epoch())
print('slug:', slug)
print(fetch_market_tokens(slug))
"
```
Expected: a dict like `{'condition_id': '0x...', 'up_token_id': '968...', 'down_token_id': '260...'}`. If it prints `None`, the market for the current window hasn't been created on Polymarket yet — wait 10-15 seconds (a new window just started) and re-run.

- [ ] **Step 5: Commit**

```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2" && git add bot/zerotoherobtc.py bot/test_zth_timing.py && git commit -m "$(cat <<'EOF'
feat(zerotoherobtc): window timing + market discovery

Pure functions to compute the current 5-min BTC up/down window and
fetch its token IDs from Gamma API.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Order book price reading

**Files:**
- Modify: `bot/zerotoherobtc.py` (append after `fetch_market_tokens`)
- Test: manual, no new file

**Interfaces:**
- Consumes: nothing from Task 1 directly (independent CLOB call), but used in Task 5 with `up_token_id`/`down_token_id` from `fetch_market_tokens`
- Produces: `best_ask_price(token_id: str) -> float | None`

- [ ] **Step 1: Append the order book function**

Add to `bot/zerotoherobtc.py` right after `fetch_market_tokens`:

```python
def best_ask_price(token_id: str) -> float | None:
    """Meilleur prix d'achat disponible (best ask) pour ce token, ou None si carnet vide."""
    r = requests.get(f"{CLOB}/book", params={"token_id": token_id}, timeout=TIMEOUT)
    r.raise_for_status()
    book = r.json()
    asks = book.get("asks", [])
    if not asks:
        return None
    return min(float(a["price"]) for a in asks)
```

- [ ] **Step 2: Manually verify against a live token from Task 1's output**

Run (reuse a `up_token_id`/`down_token_id` printed in Task 1 Step 4 — if more than ~30s have passed, re-fetch first):

```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2/bot" && ~/.pyenv/versions/3.11.9/bin/python3 -c "
from zerotoherobtc import current_window_end_epoch, slug_for_end_epoch, fetch_market_tokens, best_ask_price
tokens = fetch_market_tokens(slug_for_end_epoch(current_window_end_epoch()))
print(tokens)
print('Up ask:',   best_ask_price(tokens['up_token_id']))
print('Down ask:', best_ask_price(tokens['down_token_id']))
"
```
Expected: two float prices between 0 and 1, roughly summing close to 1 (e.g. `Up ask: 0.62`, `Down ask: 0.39`). If `tokens` is `None`, wait for a new window like in Task 1.

- [ ] **Step 3: Commit**

```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2" && git add bot/zerotoherobtc.py && git commit -m "$(cat <<'EOF'
feat(zerotoherobtc): order book best-ask price reading

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: On-chain balance reading

**Files:**
- Modify: `bot/zerotoherobtc.py` (append after `best_ask_price`)

**Interfaces:**
- Produces: `get_zth_balance_usdc() -> float`

- [ ] **Step 1: Append the balance function**

```python
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
```

- [ ] **Step 2: Manually verify**

Run:
```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2/bot" && ~/.pyenv/versions/3.11.9/bin/python3 -c "
from zerotoherobtc import get_zth_balance_usdc
print('Solde pUSD:', get_zth_balance_usdc())
"
```
Expected: `Solde pUSD: 0.0` (matches the 0 balance confirmed in `test_zth_connection.py` during design, unless funds were deposited since). No exception should be raised.

- [ ] **Step 3: Commit**

```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2" && git add bot/zerotoherobtc.py && git commit -m "$(cat <<'EOF'
feat(zerotoherobtc): on-chain pUSD balance reading

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Order execution (dry-run aware)

**Files:**
- Modify: `bot/zerotoherobtc.py` (append after `get_zth_balance_usdc`)

**Interfaces:**
- Produces: `place_buy(token_id: str, amount_usdc: float) -> dict` (keys when dry run: `dry_run`, `token_id`, `amount_usdc`, `status`; keys when real: `ok`, `order_id`, `status`, `amount_usdc`, `price`)

- [ ] **Step 1: Append the client builder and order function**

```python
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
```

- [ ] **Step 2: Verify dry-run behavior (no real order, `ZTH_DRY_RUN` is `true` in `.env`)**

Run:
```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2/bot" && ~/.pyenv/versions/3.11.9/bin/python3 -c "
from zerotoherobtc import place_buy
print(place_buy('123456', 5.0))
"
```
Expected output (log line + return value):
```
... [INFO] [DRY RUN] BUY token 123456… | \$5.00 USDC
{'dry_run': True, 'token_id': '123456', 'amount_usdc': 5.0, 'status': 'simulated'}
```
Confirm no exception is raised and no real network order call happens (the dry-run branch returns before touching `_get_client()`).

- [ ] **Step 3: Commit**

```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2" && git add bot/zerotoherobtc.py && git commit -m "$(cat <<'EOF'
feat(zerotoherobtc): dry-run-aware order execution via SecureClient

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Main loop wiring

**Files:**
- Modify: `bot/zerotoherobtc.py` (append `run_cycle`, `main`, and the `if __name__ == "__main__"` guard at the end of the file)

**Interfaces:**
- Consumes: `current_window_end_epoch`, `slug_for_end_epoch`, `fetch_market_tokens`, `best_ask_price`, `get_zth_balance_usdc`, `place_buy`, `log`, `PRICE_THRESHOLD`, `BET_PCT`, `TRIGGER_MAX_REMAINING`, `TRIGGER_MIN_REMAINING`, `POLL_INTERVAL` (all from Tasks 1-4, same file)
- Produces: `run_cycle() -> None`, `main() -> None`

- [ ] **Step 1: Append the main loop**

```python
def run_cycle() -> None:
    """Traite un cycle de marché complet : attend T-30s, vérifie le seuil, trade si besoin."""
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
            balance = get_zth_balance_usdc()
            bet = round(balance * BET_PCT, 2)
            if bet <= 0:
                log.warning(f"Solde insuffisant ({balance} USDC) — pas de trade")
            else:
                log.info(f"  -> ACHAT {outcome} @ {price:.2f} pour ${bet} USDC")
                result = place_buy(token_id, bet)
                log.info(f"  Résultat: {result}")
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
```

- [ ] **Step 2: Verify a single cycle runs end-to-end in DRY_RUN**

Run (this will block until the current 5-minute window closes — at most 5 minutes; `ZTH_DRY_RUN=true` is already set in `.env` so no real order can be sent):
```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2/bot" && ~/.pyenv/versions/3.11.9/bin/python3 -c "
from zerotoherobtc import run_cycle
run_cycle()
"
```
Expected: log lines showing `Cycle en cours : btc-updown-5m-...`, then once remaining time drops under 32s, repeated `T-Xs | Up=... Down=...` lines every ~2s, ending with either `Fin du cycle ...` (no side reached 95%) or a `[DRY RUN] BUY token ...` line followed by `Résultat: {'dry_run': True, ...}` if a side did reach 95%. No exception, no real order placed.

- [ ] **Step 3: Commit**

```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2" && git add bot/zerotoherobtc.py && git commit -m "$(cat <<'EOF'
feat(zerotoherobtc): main loop — full mechanical buy-at-95%-T-30s cycle

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Post-plan manual step (not a task — requires the user)

`ZTH_WALLET_ADDRESS` currently holds 0 USDC/pUSD/POL (confirmed via `bot/test_zth_connection.py`). Before flipping `ZTH_DRY_RUN=false` for real trading, the user must deposit USDC (and a little POL for gas, if the SDK needs it for approvals) into that wallet. This is outside the scope of code changes and isn't a task here.
