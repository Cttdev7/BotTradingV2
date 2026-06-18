# ZeroToHeroBTC Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record every ZeroToHeroBTC trade (simulated or real) in Supabase, automatically resolve each trade's real outcome ~60s after its market window closes, and expose a win-rate readout via a small script.

**Architecture:** Extend the existing single-file `bot/zerotoherobtc.py` with a Supabase-backed trade log (REST API, same pattern as `loop_v2.py`'s `trade_history` calls) and a resolution pass that runs at the start of every `run_cycle()`. A separate standalone script `bot/zth_stats.py` reads the table and prints aggregate win/loss counts — no dashboard work in this plan (explicitly deferred).

**Tech Stack:** Same as the existing bot (`requests`, `python-dotenv`), plus Supabase REST API (`SUPABASE_URL`/`SUPABASE_KEY`, already in `bot/.env`, shared with the rest of the project). Table creation via the Supabase MCP tool (`apply_migration`). No pytest — manual verification against the live Supabase table and live Polymarket data, consistent with the rest of this codebase.

## Global Constraints

- No dashboard changes in this plan — `zerotoherobtc_trades` is written/read only from `bot/zerotoherobtc.py` and `bot/zth_stats.py`.
- Reuses the existing `SUPABASE_URL`/`SUPABASE_KEY` env vars (same Supabase project as `deko_trades`/`trade_history`) — no new env vars.
- In `ZTH_DRY_RUN=true` mode, bet sizing for logging purposes uses a fixed **simulated balance of 100 USDC** (`SIMULATED_BALANCE_USDC = 100.0`), not the real on-chain balance (which is 0). In real mode (`ZTH_DRY_RUN=false`), the existing `get_zth_balance_usdc()` real balance is used, unchanged.
- A trade is only marked `resolved` once Polymarket's own data shows a final price ≥ 0.99 on one side — never guessed early.
- No change to the trading decision logic itself (95% threshold, 60s→2s window) — this plan only adds recording and resolution.

---

### Task 1: Create the `zerotoherobtc_trades` Supabase table

**Files:** none (Supabase schema only)

**Interfaces:**
- Produces: table `zerotoherobtc_trades` with columns `id, slug, end_epoch, condition_id, outcome, price_at_buy, amount_usdc, dry_run, created_at, resolved, actual_outcome, win, resolved_at`

- [ ] **Step 1: Apply the migration via the Supabase MCP tool**

Call `mcp__plugin_supabase_supabase__apply_migration` with `name="create_zerotoherobtc_trades"` and this SQL:

```sql
create table if not exists zerotoherobtc_trades (
  id bigint generated always as identity primary key,
  slug text not null,
  end_epoch bigint not null,
  condition_id text not null,
  outcome text not null,
  price_at_buy numeric not null,
  amount_usdc numeric not null,
  dry_run boolean not null default true,
  created_at timestamptz not null default now(),
  resolved boolean not null default false,
  actual_outcome text,
  win boolean,
  resolved_at timestamptz
);
```

- [ ] **Step 2: Verify the table exists and is empty**

Use `mcp__plugin_supabase_supabase__execute_sql` with:
```sql
select count(*) from zerotoherobtc_trades;
```
Expected: a single row, `count = 0`. No error.

- [ ] **Step 3: Commit**

No file changes in this task (schema-only) — nothing to commit. Proceed directly to Task 2.

---

### Task 2: Record trades — `insert_trade()` + simulated balance in DRY_RUN

**Files:**
- Modify: `bot/zerotoherobtc.py`

**Interfaces:**
- Consumes: `ZTH_DRY_RUN`, `log`, `requests` (already defined in the file)
- Produces: `SB_URL: str`, `SB_KEY: str`, `SIMULATED_BALANCE_USDC: float`, `_sb_headers() -> dict`, `insert_trade(slug: str, end_epoch: int, condition_id: str, outcome: str, price: float, amount_usdc: float) -> None`

- [ ] **Step 1: Add Supabase config constants after the existing `ZTH_*` env vars**

In `bot/zerotoherobtc.py`, find:
```python
ZTH_DRY_RUN        = os.getenv("ZTH_DRY_RUN", "true").lower() == "true"
```
Replace with:
```python
ZTH_DRY_RUN        = os.getenv("ZTH_DRY_RUN", "true").lower() == "true"

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_KEY", "")
SIMULATED_BALANCE_USDC = 100.0  # solde fictif utilisé pour la mise en DRY_RUN (vrai solde on-chain = 0)
```

- [ ] **Step 2: Add `_sb_headers()` and `insert_trade()` after `place_buy()`**

Find the end of `place_buy()`:
```python
    return {
        "ok": resp.ok,
        "order_id": resp.order_id,
        "status": resp.status,
        "amount_usdc": amount_usdc,
        "price": price,
    }
```
Right after it (before `def run_cycle()`), add:
```python
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
```

- [ ] **Step 3: Wire simulated balance + `insert_trade` into `run_cycle()`**

Find in `run_cycle()`:
```python
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
```
Replace with:
```python
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
```

- [ ] **Step 4: Verify by inserting a test trade and reading it back**

Run:
```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2/bot" && ~/.pyenv/versions/3.11.9/bin/python3 -c "
from zerotoherobtc import insert_trade, SB_URL, SB_KEY
import requests
insert_trade('btc-updown-5m-0', 0, '0xtest', 'Up', 0.97, 5.0)
r = requests.get(f'{SB_URL}/rest/v1/zerotoherobtc_trades', params={'slug': 'eq.btc-updown-5m-0'}, headers={'apikey': SB_KEY, 'Authorization': f'Bearer {SB_KEY}'})
print(r.status_code, r.json())
"
```
Expected: status `200` and a list with one row where `slug == 'btc-updown-5m-0'`, `outcome == 'Up'`, `resolved == False`.

- [ ] **Step 5: Clean up the test row and commit**

```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2/bot" && ~/.pyenv/versions/3.11.9/bin/python3 -c "
import os, requests
from dotenv import load_dotenv
load_dotenv('.env')
SB_URL = os.getenv('SUPABASE_URL'); SB_KEY = os.getenv('SUPABASE_KEY')
requests.delete(f'{SB_URL}/rest/v1/zerotoherobtc_trades', params={'slug': 'eq.btc-updown-5m-0'}, headers={'apikey': SB_KEY, 'Authorization': f'Bearer {SB_KEY}'})
print('cleaned up')
"
```

```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2" && git add bot/zerotoherobtc.py && git commit -m "$(cat <<'EOF'
feat(zerotoherobtc): record every trade in Supabase, simulated balance in DRY_RUN

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Resolve pending trades against the real market outcome

**Files:**
- Modify: `bot/zerotoherobtc.py`

**Interfaces:**
- Consumes: `GAMMA_API`, `TIMEOUT`, `SB_URL`, `SB_KEY`, `_sb_headers()`, `log`, `time`, `json`, `requests` (all already defined)
- Produces: `fetch_market_outcome(slug: str) -> str | None`, `resolve_pending_trades() -> None`

- [ ] **Step 1: Add `fetch_market_outcome()` and `resolve_pending_trades()` after `insert_trade()`**

Right after the `insert_trade()` function body (before `def run_cycle()`), add:
```python
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
        actual = fetch_market_outcome(trade["slug"])
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
```

- [ ] **Step 2: Call `resolve_pending_trades()` at the start of `run_cycle()`**

Find:
```python
def run_cycle() -> None:
    """Traite un cycle de marché complet : attend T-30s, vérifie le seuil, trade si besoin."""
    end_epoch = current_window_end_epoch()
    slug = slug_for_end_epoch(end_epoch)
    log.info(f"Cycle en cours : {slug} (fin dans {end_epoch - time.time():.0f}s)")
```
Replace with:
```python
def run_cycle() -> None:
    """Traite un cycle de marché complet : attend T-30s, vérifie le seuil, trade si besoin."""
    resolve_pending_trades()

    end_epoch = current_window_end_epoch()
    slug = slug_for_end_epoch(end_epoch)
    log.info(f"Cycle en cours : {slug} (fin dans {end_epoch - time.time():.0f}s)")
```

- [ ] **Step 3: Verify `fetch_market_outcome()` against a known closed market**

`btc-updown-5m-1781811900` closed earlier today during bot testing (well over 60s ago) — Polymarket will have resolved it.

Run:
```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2/bot" && ~/.pyenv/versions/3.11.9/bin/python3 -c "
from zerotoherobtc import fetch_market_outcome
print(fetch_market_outcome('btc-updown-5m-1781811900'))
"
```
Expected: prints `Up` or `Down` (not `None`) — confirms the function correctly reads a resolved market.

- [ ] **Step 4: Verify `resolve_pending_trades()` end-to-end with a real closed market**

Insert a fake unresolved trade pointing at that same already-closed market, run the resolver, and check it gets resolved:
```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2/bot" && ~/.pyenv/versions/3.11.9/bin/python3 -c "
from zerotoherobtc import insert_trade, resolve_pending_trades, SB_URL, SB_KEY
import requests
insert_trade('btc-updown-5m-1781811900', 1781811900, '0xtest-resolve', 'Up', 0.97, 5.0)
resolve_pending_trades()
r = requests.get(f'{SB_URL}/rest/v1/zerotoherobtc_trades', params={'condition_id': 'eq.0xtest-resolve'}, headers={'apikey': SB_KEY, 'Authorization': f'Bearer {SB_KEY}'})
print(r.json())
"
```
Expected: one row with `resolved == True`, `actual_outcome` set to `Up` or `Down`, and `win` set to `True` or `False` accordingly (matches the value printed in Step 3).

- [ ] **Step 5: Clean up the test row and commit**

```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2/bot" && ~/.pyenv/versions/3.11.9/bin/python3 -c "
import os, requests
from dotenv import load_dotenv
load_dotenv('.env')
SB_URL = os.getenv('SUPABASE_URL'); SB_KEY = os.getenv('SUPABASE_KEY')
requests.delete(f'{SB_URL}/rest/v1/zerotoherobtc_trades', params={'condition_id': 'eq.0xtest-resolve'}, headers={'apikey': SB_KEY, 'Authorization': f'Bearer {SB_KEY}'})
print('cleaned up')
"
```

```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2" && git add bot/zerotoherobtc.py && git commit -m "$(cat <<'EOF'
feat(zerotoherobtc): resolve pending trades against real market outcome

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Win-rate readout script

**Files:**
- Create: `bot/zth_stats.py`

**Interfaces:**
- Consumes: Supabase REST API (`SUPABASE_URL`/`SUPABASE_KEY` from `bot/.env`), table `zerotoherobtc_trades` (columns `resolved`, `win`)
- Produces: console output only (no return value — standalone script)

- [ ] **Step 1: Create `bot/zth_stats.py`**

```python
"""Affiche le taux de victoire de ZeroToHeroBTC à partir de Supabase."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(".env")

import requests

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_KEY", "")

headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}

r = requests.get(
    f"{SB_URL}/rest/v1/zerotoherobtc_trades",
    params={"select": "resolved,win"},
    headers=headers,
    timeout=10,
)
r.raise_for_status()
trades = r.json()

resolved = [t for t in trades if t["resolved"]]
pending  = [t for t in trades if not t["resolved"]]
wins     = [t for t in resolved if t["win"]]
losses   = [t for t in resolved if not t["win"]]

print(f"Total trades       : {len(trades)}")
print(f"Résolus            : {len(resolved)}")
print(f"  Gagnés           : {len(wins)}")
print(f"  Perdus           : {len(losses)}")
print(f"En attente         : {len(pending)}")
if resolved:
    print(f"Taux de victoire   : {len(wins) / len(resolved) * 100:.1f}%")
else:
    print("Taux de victoire   : pas encore de trade résolu")
```

- [ ] **Step 2: Run it against the (currently empty) table**

```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2/bot" && ~/.pyenv/versions/3.11.9/bin/python3 zth_stats.py
```
Expected:
```
Total trades       : 0
Résolus            : 0
  Gagnés           : 0
  Perdus           : 0
En attente         : 0
Taux de victoire   : pas encore de trade résolu
```
(Counts will be non-zero once the bot has been running for a while and produced real simulated trades — this is expected and correct.)

- [ ] **Step 3: Commit**

```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2" && git add bot/zth_stats.py && git commit -m "$(cat <<'EOF'
feat(zerotoherobtc): add zth_stats.py win-rate readout script

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Post-plan note

Once this plan is merged, leave `bot/zerotoherobtc.py` running (`python3 bot/zerotoherobtc.py`) for a while to accumulate simulated trades, then run `python3 bot/zth_stats.py` whenever you want to check the win rate. Dashboard display of these stats is a separate, later plan.
