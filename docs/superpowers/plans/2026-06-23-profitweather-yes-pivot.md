# ProfitWeather V2 — Voie YES haute conviction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second, independent buying path (YES) to ProfitWeather V2 (`bot/loop_v2.py` + `bot/brain.py`), restricted to 4 cities with proven historical accuracy, without changing any existing NO behavior.

**Architecture:** `_prefilter()` in `loop_v2.py` marks YES-eligible candidates (whitelist + price band + volume) alongside the existing NO candidates. `brain.decide_v2()` shows both kinds of candidates to Claude and validates the returned outcome against the whitelist (defense-in-depth). `run_cycle()`'s decision loop branches on outcome to apply outcome-specific price bands, exposure caps, and a YES-only dry-run switch, then records the trade with `sym="YES"` or `sym="NO"` exactly as today.

**Tech Stack:** Python 3.11, no new dependencies. Existing test convention: plain assert-based scripts (`bot/test_*.py`), no pytest, run via `python3 test_xxx.py` from the `bot/` directory.

## Global Constraints

- NO behavior (filters, mises, take-profit, stop-loss, hedge, cascade) must not change — every existing `bot/test_loop_v2_*.py` must still pass unmodified.
- All new risk limits (whitelist, price band, exposure cap) are Python constants in `loop_v2.py`, never read from `bot_strategies`/Claude — same rule as existing `MIN_NO_PRICE`/`MAX_NO_PRICE`/etc (see `feedback_hard_limits` lesson: Claude Haiku ignores prompt-only limits).
- YES orders are simulated (no real money) while `YES_DRY_RUN` env var is `"true"` (the default), independent of the global `DRY_RUN` used by the NO path which is already live.
- YES trigger is the market price (≥ `MIN_YES_PRICE`), not ECMWF agreement — no backtest exists proving ECMWF accuracy, only price→outcome history (confirmed during brainstorming).
- Whitelist for now: `chengdu`, `seoul`, `london`, `tokyo` (lowercase city slugs, matching `m.get("city")` convention already used in `loop_v2.py`).

---

### Task 1: Hard-coded YES parameters in `loop_v2.py`

**Files:**
- Modify: `bot/loop_v2.py:45-58` (constants block, right after the existing NO constants)
- Test: `bot/test_loop_v2_yes_constants.py`

**Interfaces:**
- Produces: module-level constants `YES_WHITELIST_CITIES: set[str]`, `MIN_YES_PRICE: float`, `MAX_YES_PRICE: float`, `MAX_YES_EXPOSURE_PCT: float`, `YES_DRY_RUN: bool` — consumed by Tasks 2 and 4.

- [ ] **Step 1: Write the failing test**

```python
"""Test des nouvelles constantes YES (pas d'appel réseau)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from loop_v2 import (
    YES_WHITELIST_CITIES, MIN_YES_PRICE, MAX_YES_PRICE,
    MAX_YES_EXPOSURE_PCT, YES_DRY_RUN,
)

assert YES_WHITELIST_CITIES == {"chengdu", "seoul", "london", "tokyo"}, \
    "Whitelist YES doit être exactement les 4 villes validées"
assert MIN_YES_PRICE == 0.75, "MIN_YES_PRICE doit miroiter MIN_NO_PRICE"
assert MAX_YES_PRICE == 0.96, "MAX_YES_PRICE doit miroiter MAX_NO_PRICE"
assert MAX_YES_EXPOSURE_PCT == 0.20, "Plafond exposition YES séparé à 20%"
assert YES_DRY_RUN is True, "YES_DRY_RUN doit défaut à True (pas de variable d'env positionnée dans ce test)"

print("✅ Test constantes YES passe")
```

Save this to `bot/test_loop_v2_yes_constants.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "bot" && python3 test_loop_v2_yes_constants.py`
Expected: `ImportError: cannot import name 'YES_WHITELIST_CITIES' from 'loop_v2'`

- [ ] **Step 3: Add the constants to `loop_v2.py`**

In `bot/loop_v2.py`, immediately after the existing line `MIN_VOLUME        = 1_500   # volume minimum USDC` (part of the hard-coded NO rules block, before `NO_STOP_LOSS_PCT`), insert:

```python

# ── Règles hard-codées YES (voie indépendante, ajout 23/06/2026) ──────────────
# Donnée prouvée : prix marché >= MIN_YES_PRICE sur ces 4 villes => 92-100% de réussite
# observée (london_stats/seoul_stats/tokyo_stats/chengdu_stats). PAS basé sur l'accord
# ECMWF (aucun backtest ECMWF<->résultat réel n'existe) — voir spec du 23/06/2026.
YES_WHITELIST_CITIES = {"chengdu", "seoul", "london", "tokyo"}
MIN_YES_PRICE         = 0.75   # miroir de MIN_NO_PRICE
MAX_YES_PRICE         = 0.96   # miroir de MAX_NO_PRICE
MAX_YES_EXPOSURE_PCT  = 0.20   # plafond séparé du NO : max 20% du portefeuille total en YES ouverts
YES_DRY_RUN = os.getenv("YES_DRY_RUN", "true").lower() in ("true", "1", "yes")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "bot" && python3 test_loop_v2_yes_constants.py`
Expected: `✅ Test constantes YES passe`

- [ ] **Step 5: Run the full existing NO test suite to confirm no regression**

Run: `cd "bot" && for f in test_loop_v2_*.py; do python3 "$f" || echo "FAILED: $f"; done`
Expected: every test prints its `✅` line, no `FAILED` line.

- [ ] **Step 6: Commit**

```bash
git add bot/loop_v2.py bot/test_loop_v2_yes_constants.py
git commit -m "feat: ajoute les constantes hard-codées de la voie YES (whitelist, prix, exposition)"
```

---

### Task 2: `_prefilter` surfaces YES-eligible candidates

**Files:**
- Modify: `bot/loop_v2.py:486-512` (inside the `for m in markets:` loop of `_prefilter`, right after the volume check, before the NO-specific `bounds`/timing/ECMWF logic)
- Test: `bot/test_loop_v2_yes_prefilter.py`

**Interfaces:**
- Consumes: `YES_WHITELIST_CITIES`, `MIN_YES_PRICE`, `MAX_YES_PRICE` (Task 1), `MIN_VOLUME`, `MIN_HOURS_REMAINING` (existing).
- Produces: candidate markets returned by `_prefilter()` may now carry `m["_yes_eligible"] = True` — consumed by Task 3 (`brain._format_markets_v2`) and Task 4 (decision loop).

- [ ] **Step 1: Write the failing test**

```python
"""Test de la détection des candidats YES dans _prefilter() (pas d'appel réseau)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import datetime
from loop_v2 import _prefilter


def _end_iso(hours_from_now: float) -> str:
    end = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours_from_now)
    return end.isoformat()


def _make_market(cid, city, yes_price, volume=5000, hours_left=10):
    no_price = round(1 - yes_price, 2)
    return {
        "condition_id": cid,
        "city": city,
        "question": f"Will the highest temperature in {city.title()} on June 25 be between 30 and 31 degrees?",
        "volume": volume,
        "tokens": [{"outcome": "Yes", "price": yes_price}, {"outcome": "No", "price": no_price}],
        "local_hour": 10,
        "day_offset": 0,
        "end_date_iso": _end_iso(hours_left),
        "weather_ctx": {},
    }


# Cas 1 : ville whitelistée, prix YES dans la zone -> éligible
kept = _prefilter([_make_market("cid_london", "london", 0.90)], [], 1000.0)
m = next((x for x in kept if x["condition_id"] == "cid_london"), None)
assert m is not None, "Le marché London à YES=0.90 doit passer le préfiltre"
assert m.get("_yes_eligible") is True, "Doit être marqué _yes_eligible"

# Cas 2 : ville NON whitelistée, même prix -> pas éligible YES (et pas de NO non plus, no_price trop bas)
kept2 = _prefilter([_make_market("cid_paris", "paris", 0.90)], [], 1000.0)
assert not any(x["condition_id"] == "cid_paris" for x in kept2), \
    "Paris (hors whitelist) à YES=0.90 ne doit pas passer (no_price=0.10 hors zone NO, pas éligible YES)"

# Cas 3 : ville whitelistée mais prix YES hors zone (trop bas) -> pas éligible
kept3 = _prefilter([_make_market("cid_seoul_low", "seoul", 0.50)], [], 1000.0)
assert not any(x["condition_id"] == "cid_seoul_low" for x in kept3), \
    "Seoul à YES=0.50 (hors [0.75-0.96]) ne doit pas être éligible YES"

# Cas 4 : ville whitelistée, volume insuffisant -> pas éligible
kept4 = _prefilter([_make_market("cid_tokyo_lowvol", "tokyo", 0.90, volume=500)], [], 1000.0)
assert not any(x["condition_id"] == "cid_tokyo_lowvol" for x in kept4), \
    "Volume sous MIN_VOLUME doit rejeter même un candidat YES whitelisté"

print("✅ Test détection candidats YES passe")
```

Save this to `bot/test_loop_v2_yes_prefilter.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "bot" && python3 test_loop_v2_yes_prefilter.py`
Expected: `AssertionError: Le marché London à YES=0.90 doit passer le préfiltre`

- [ ] **Step 3: Implement YES detection in `_prefilter`**

In `bot/loop_v2.py`, inside `_prefilter`, the loop currently reads (around line 486-512):

```python
    kept = []
    for m in markets:
        cid   = m.get("condition_id", "")
        city  = m.get("city", "")
        q     = m.get("question", "")
        vol   = float(m.get("volume") or 0)
        tokens  = m.get("tokens", [])
        no_price = next((t.get("price", 0) for t in tokens if t.get("outcome") == "No"), 0)
        local_hour = m.get("local_hour")
        day_offset = m.get("day_offset", 0)
        wx   = m.get("weather_ctx", {})

        # Déjà en position sur ce marché précis
        if cid in open_cids:
            continue
        # Max 2 positions ouvertes par ville par jour (trade 1 + cascade trade 2)
        market_date = (m.get("end_date_iso") or "")[:10]
        if open_city_date_count.get(f"{city}|{market_date}", 0) >= 2:
            continue

        # Exposition totale dépassée (calculée sur portefeuille total, pas juste le cash)
        if total_exposed >= total_portfolio * MAX_EXPOSURE_PCT:
            log(f"  ⛔ Exposition max atteinte ({total_exposed:.0f}$ / {total_portfolio*MAX_EXPOSURE_PCT:.0f}$)")
            break

        # Volume minimum
        if vol < MIN_VOLUME:
            continue
```

Replace it with (adds `yes_price` extraction and the YES branch right after the volume check, before any NO-specific logic):

```python
    kept = []
    for m in markets:
        cid   = m.get("condition_id", "")
        city  = m.get("city", "")
        q     = m.get("question", "")
        vol   = float(m.get("volume") or 0)
        tokens  = m.get("tokens", [])
        no_price  = next((t.get("price", 0) for t in tokens if t.get("outcome") == "No"),  0)
        yes_price = next((t.get("price", 0) for t in tokens if t.get("outcome") == "Yes"), 0)
        local_hour = m.get("local_hour")
        day_offset = m.get("day_offset", 0)
        wx   = m.get("weather_ctx", {})

        # Déjà en position sur ce marché précis
        if cid in open_cids:
            continue
        # Max 2 positions ouvertes par ville par jour (trade 1 + cascade trade 2) — compteur
        # partagé entre NO et YES, une ville ne doit pas accumuler plus de 2 positions/jour au total
        market_date = (m.get("end_date_iso") or "")[:10]
        if open_city_date_count.get(f"{city}|{market_date}", 0) >= 2:
            continue

        # Volume minimum (s'applique aussi bien au NO qu'au YES)
        if vol < MIN_VOLUME:
            continue

        # ── Voie YES (indépendante du NO, villes whitelistées uniquement) ──────
        # Donnée prouvée : prix marché déjà élevé, pas l'accord ECMWF (voir Task 1).
        if city.lower() in YES_WHITELIST_CITIES and MIN_YES_PRICE <= yes_price <= MAX_YES_PRICE:
            hours_left_yes = _hours_remaining(m.get("end_date_iso", ""))
            if hours_left_yes is None or hours_left_yes >= MIN_HOURS_REMAINING:
                m["_yes_eligible"] = True
                m["_hours_left"] = hours_left_yes
                log(f"  🟢 YES éligible {city} | prix={yes_price:.2f} | vol=${vol:,.0f}")
                kept.append(m)
                continue

        # Exposition NO totale dépassée (calculée sur portefeuille total, pas juste le cash)
        if total_exposed >= total_portfolio * MAX_EXPOSURE_PCT:
            log(f"  ⛔ Exposition max atteinte ({total_exposed:.0f}$ / {total_portfolio*MAX_EXPOSURE_PCT:.0f}$)")
            break
```

Note: the exposure-cap check (previously right after the volume check) is moved to *after* the YES branch and now only gates the NO path — YES exposure is checked separately in Task 4, inside `run_cycle`'s decision loop, against `MAX_YES_EXPOSURE_PCT`. This is intentional: a NO exposure cap hit must not prevent YES candidates (different budget) from being surfaced.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "bot" && python3 test_loop_v2_yes_prefilter.py`
Expected: `✅ Test détection candidats YES passe`

- [ ] **Step 5: Run the full existing NO test suite to confirm no regression**

Run: `cd "bot" && for f in test_loop_v2_*.py; do python3 "$f" || echo "FAILED: $f"; done`
Expected: every test prints its `✅` line, no `FAILED` line. Pay special attention to
`test_loop_v2_price_cap.py` and `test_loop_v2_early_entry.py` since they exercise the same loop body.

- [ ] **Step 6: Commit**

```bash
git add bot/loop_v2.py bot/test_loop_v2_yes_prefilter.py
git commit -m "feat: _prefilter detecte les candidats YES sur les villes whitelistees"
```

---

### Task 3: `brain.py` — afficher les candidats YES à Claude et valider sa réponse

**Files:**
- Modify: `bot/brain.py:491-579` (`_format_markets_v2`)
- Modify: `bot/brain.py:591-697` (`decide_v2` — prompt + post-processing)
- Test: `bot/test_brain_yes_outcome.py`

**Interfaces:**
- Consumes: `m["_yes_eligible"]` (Task 2), `m.get("city")`.
- Produces: `_validate_decision_outcome(outcome: str, city: str) -> str | None` — pure helper, returns `"No"`, `"Yes"`, or `None` (rejected). Consumed inside `decide_v2`'s post-processing loop and directly unit-tested.

- [ ] **Step 1: Write the failing test**

```python
"""Test de la validation defense-in-depth de l'outcome YES (pas d'appel réseau, pas d'appel API Claude)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from brain import _validate_decision_outcome

# NO toujours accepté, quelle que soit la ville
assert _validate_decision_outcome("No", "paris") == "No"
assert _validate_decision_outcome("NO", "paris") == "No"

# YES accepté uniquement sur les villes whitelistées
assert _validate_decision_outcome("Yes", "london") == "Yes"
assert _validate_decision_outcome("YES", "Tokyo") == "Yes"  # insensible à la casse de la ville

# YES rejeté hors whitelist
assert _validate_decision_outcome("Yes", "paris") is None
assert _validate_decision_outcome("Yes", "") is None

# Valeur inconnue rejetée
assert _validate_decision_outcome("Maybe", "london") is None

print("✅ Test validation outcome YES passe")
```

Save this to `bot/test_brain_yes_outcome.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "bot" && python3 test_brain_yes_outcome.py`
Expected: `ImportError: cannot import name '_validate_decision_outcome' from 'brain'`

- [ ] **Step 3a: Add the whitelist constant and validation helper to `brain.py`**

Near the top of `bot/brain.py`, right after the `_WEATHER_VILLES` block (around line 30+), add:

```python
# Villes éligibles pour la voie YES haute conviction (doit rester synchronisé avec
# loop_v2.YES_WHITELIST_CITIES — duplication volontaire, brain.py ne dépend pas de loop_v2).
_YES_WHITELIST_CITIES = {"chengdu", "seoul", "london", "tokyo"}


def _validate_decision_outcome(outcome: str, city: str) -> str | None:
    """
    Defense-in-depth : valide l'outcome renvoyé par Claude.
    "No" toujours accepté. "Yes" accepté uniquement sur une ville whitelistée.
    Retourne "No", "Yes", ou None si la décision doit être rejetée.
    """
    o = (outcome or "").strip().lower()
    if o == "no":
        return "No"
    if o == "yes" and (city or "").strip().lower() in _YES_WHITELIST_CITIES:
        return "Yes"
    return None
```

- [ ] **Step 3b: Run test to verify it passes**

Run: `cd "bot" && python3 test_brain_yes_outcome.py`
Expected: `✅ Test validation outcome YES passe`

- [ ] **Step 4: Wire the helper into `decide_v2`'s post-processing**

In `bot/brain.py`, the `decide_v2` post-processing loop currently reads (around line 687-697):

```python
    resolved = []
    for d in decisions:
        if d.get("action") != "buy":
            continue
        idx = d.get("market_index")
        if idx is None or idx not in index_map:
            continue
        d["condition_id"] = index_map[idx]
        d["outcome"] = "No"
        resolved.append(d)
    return resolved
```

Replace with:

```python
    city_by_cid = {m.get("condition_id", ""): m.get("city", "") for m in markets}

    resolved = []
    for d in decisions:
        if d.get("action") != "buy":
            continue
        idx = d.get("market_index")
        if idx is None or idx not in index_map:
            continue
        cid = index_map[idx]
        city = city_by_cid.get(cid, "")
        validated_outcome = _validate_decision_outcome(d.get("outcome", "No"), city)
        if validated_outcome is None:
            continue
        d["condition_id"] = cid
        d["outcome"] = validated_outcome
        resolved.append(d)
    return resolved
```

- [ ] **Step 5: Update `_format_markets_v2` to show YES-eligible markets to Claude**

In `bot/brain.py`, `_format_markets_v2` currently reads (around line 514-518):

```python
        tokens    = m.get("tokens", [])
        yes_price = next((t.get("price", 0) for t in tokens if t.get("outcome") == "Yes"), 0)
        no_price  = next((t.get("price", 0) for t in tokens if t.get("outcome") == "No"),  0)
        if no_price < 0.60:
            continue  # marché non affiché → idx inchangé, pas de gap dans la numérotation
```

Replace with:

```python
        tokens    = m.get("tokens", [])
        yes_price = next((t.get("price", 0) for t in tokens if t.get("outcome") == "Yes"), 0)
        no_price  = next((t.get("price", 0) for t in tokens if t.get("outcome") == "No"),  0)
        if no_price < 0.60 and not m.get("_yes_eligible"):
            continue  # marché non affiché → idx inchangé, pas de gap dans la numérotation
```

Then, still in `_format_markets_v2`, right after the existing tag block (around line 566-569, where `_no_confirmed` and `_deko` tags are appended to `market_line`), add the YES tag:

```python
        if m.get("_no_confirmed"):
            market_line += "\n    ✅ NO CONFIRMÉ EN TEMPS RÉEL : max observé aujourd'hui dépasse déjà la fourchette haute"
        if m.get("_yes_eligible"):
            market_line += "\n    🟢 SIGNAL YES HAUTE CONVICTION : ville historique fiable (92-100% observé) — YES éligible"
        if m.get("_deko"):
            market_line += "\n    🔍 SIGNAL DEKO : sailor82 est NO sur ce marché (win rate 86%)"
```

- [ ] **Step 6: Add the YES strategy section to `decide_v2`'s system prompt**

In `bot/brain.py`, inside `decide_v2`'s `system_prompt` string, right before the closing
`Si aucun cas évident → retourner []"""` (end of the prompt, around line 649), insert a new
section. The prompt currently ends with:

```python
Tu réponds UNIQUEMENT en JSON valide :
[
  {
    "action": "buy",
    "market_index": 3,
    "outcome": "No",
    "no_price": 0.82,
    "certainty": "high",
    "reason": "SF prévu 80°F, fourchette 66-67°F → 14°F d'écart, band_prob=5% → NO évident"
  }
]
Si aucun cas évident → retourner []"""
```

Replace with:

```python
STRATÉGIE YES (nouvelle, ajout 23/06/2026) — villes whitelistées UNIQUEMENT (Chengdu, Seoul,
London, Tokyo) marquées "🟢 SIGNAL YES HAUTE CONVICTION" dans la liste des marchés :
- Acheter YES (pas NO) quand le prix YES est déjà élevé (0.75–0.96) sur l'une de ces 4 villes —
  c'est le signal lui-même qui fait foi, PAS besoin d'accord ECMWF (contrairement au NO).
- Toute autre ville : NE JAMAIS proposer "outcome": "Yes" — uniquement "No".
- Même barème de certitude/mise que le NO (high/medium/low → 5/3/2% du solde).

Tu réponds UNIQUEMENT en JSON valide :
[
  {
    "action": "buy",
    "market_index": 3,
    "outcome": "No",
    "no_price": 0.82,
    "certainty": "high",
    "reason": "SF prévu 80°F, fourchette 66-67°F → 14°F d'écart, band_prob=5% → NO évident"
  },
  {
    "action": "buy",
    "market_index": 7,
    "outcome": "Yes",
    "yes_price": 0.91,
    "certainty": "high",
    "reason": "London signal YES haute conviction à 0.91 — ville whitelistée"
  }
]
Si aucun cas évident → retourner []"""
```

- [ ] **Step 7: Run all brain.py and loop_v2 tests to confirm no regression**

Run: `cd "bot" && for f in test_loop_v2_*.py test_brain_*.py; do python3 "$f" || echo "FAILED: $f"; done`
Expected: every test prints its `✅` line, no `FAILED` line.

- [ ] **Step 8: Commit**

```bash
git add bot/brain.py bot/test_brain_yes_outcome.py
git commit -m "feat: brain.py affiche et valide les candidats YES haute conviction"
```

---

### Task 4: `run_cycle` exécute les décisions YES (prix, exposition, dry-run séparé)

**Files:**
- Modify: `bot/loop_v2.py:191-201` (`_get_current_no_price` — no change needed, reused alongside `_get_both_prices`)
- Modify: `bot/loop_v2.py:784-900` (decision loop inside `run_cycle`)
- Modify: `bot/loop_v2.py:928-934` (startup log banner)

**Interfaces:**
- Consumes: `YES_WHITELIST_CITIES`, `MIN_YES_PRICE`, `MAX_YES_PRICE`, `MAX_YES_EXPOSURE_PCT`, `YES_DRY_RUN` (Task 1), `_get_both_prices(condition_id) -> tuple[float|None, float|None]` (existing, returns `(no_price, yes_price)`), validated `d["outcome"] in ("No","Yes")` (Task 3).
- Produces: trades recorded via `insert_trade` with `"sym": "YES"` when `outcome=="Yes"`, matching the format already used by the existing auto-hedge code path (`loop_v2.py:352`).

**Pre-check (no code change needed, verified during planning):** `brain.check_market_outcomes`
(used by `run_cycle` to resolve open trades) already reads `outcome = t.get("sym", "Yes")` and
compares it case-insensitively against the Polymarket API's `outcomes` field — it already works
correctly for `sym="YES"` rows (proof: the existing auto-hedge code path at `loop_v2.py:352`
already inserts `sym="YES"` trades today and they resolve fine). No task required for this part
of the spec.

- [ ] **Step 1: Update the decision loop's setup (exposure tracking)**

In `bot/loop_v2.py`, `run_cycle`'s decision loop setup currently reads (around line 784-791):

```python
    # Déduplication
    open_cids = {t.get("condition_id") for t in history if t.get("pnl") is None}
    decisions = [d for d in decisions if d.get("condition_id") not in open_cids]

    market_lookup   = {m["condition_id"]: m for m in candidates}
    total_exposed   = sum(float(t.get("amount_usdc") or 0) for t in history if t.get("pnl") is None)
    total_portfolio = usdc + total_exposed
    traded_city_dates = []  # trades par ville+date ce cycle (max 2 par ville par jour)
```

Replace with:

```python
    # Déduplication
    open_cids = {t.get("condition_id") for t in history if t.get("pnl") is None}
    decisions = [d for d in decisions if d.get("condition_id") not in open_cids]

    market_lookup     = {m["condition_id"]: m for m in candidates}
    total_exposed     = sum(
        float(t.get("amount_usdc") or 0) for t in history
        if t.get("pnl") is None and t.get("sym", "").upper() != "YES"
    )
    total_exposed_yes = sum(
        float(t.get("amount_usdc") or 0) for t in history
        if t.get("pnl") is None and t.get("sym", "").upper() == "YES"
    )
    total_portfolio    = usdc + total_exposed + total_exposed_yes
    traded_city_dates  = []  # trades par ville+date ce cycle (max 2 par ville par jour, NO+YES partagés)
```

Note: `total_exposed` previously summed *all* open trades (including hedge YES trades from
`check_stop_loss`). It now excludes `sym=="YES"` rows so the NO exposure cap isn't polluted by
hedge or new YES positions — those are now tracked in `total_exposed_yes`. `total_portfolio`
still sums everything, unchanged in spirit.

- [ ] **Step 2: Update the decision filter and per-decision outcome resolution**

The loop currently starts with (around line 793-801):

```python
    for d in decisions:
        if d.get("action") != "buy" or d.get("outcome") not in ("No", "NO"):
            continue

        cid       = d.get("condition_id", "")
        certainty = d.get("certainty", "low")
        mkt       = market_lookup.get(cid, {})
        city      = mkt.get("city", "")
```

Replace with:

```python
    for d in decisions:
        if d.get("action") != "buy":
            continue
        outcome = d.get("outcome")
        if outcome not in ("No", "NO", "Yes", "YES"):
            continue
        is_yes = outcome.upper() == "YES"

        cid       = d.get("condition_id", "")
        certainty = d.get("certainty", "low")
        mkt       = market_lookup.get(cid, {})
        city      = mkt.get("city", "")

        # Defense-in-depth : le YES n'est jamais autorisé hors whitelist, même si Claude
        # (ou un bug amont) renvoie "Yes" pour une autre ville.
        if is_yes and city.lower() not in YES_WHITELIST_CITIES:
            log(f"  ⛔ {city} YES hors whitelist — rejeté")
            continue
```

- [ ] **Step 3: Skip NO-only signal boosts for YES decisions**

The next block (around line 802-817) handles the Deko boost and METAR peak-confirmed boost,
which are NO-specific (ECMWF/market-momentum signals not used by the YES path). It currently
reads:

```python
        # Boost certitude si sailor82 est aussi sur ce trade (avant le filtre high)
        if mkt.get("_deko"):
            old = certainty
            certainty = {"low": "medium", "medium": "high"}.get(certainty, certainty)
            if certainty != old:
                log(f"  🔍 Deko boost : certitude {old} → {certainty} (sailor82 confirme)")

        # Pic METAR confirmé → on accepte medium aussi (max journalier connu = quasi-certitude)
        if mkt.get("_peak_confirmed_no") and certainty == "medium":
            log(f"  🏔️  Pic confirmé : certitude medium → accepté (max_station={mkt.get('_max_observed')})")
            certainty = "high"   # traiter comme high pour le calcul de mise
```

Replace with (wrap both boosts in `if not is_yes:`):

```python
        # Boosts de certitude NO-uniquement (signaux Deko/METAR n'existent pas pour le YES)
        if not is_yes:
            # Boost certitude si sailor82 est aussi sur ce trade (avant le filtre high)
            if mkt.get("_deko"):
                old = certainty
                certainty = {"low": "medium", "medium": "high"}.get(certainty, certainty)
                if certainty != old:
                    log(f"  🔍 Deko boost : certitude {old} → {certainty} (sailor82 confirme)")

            # Pic METAR confirmé → on accepte medium aussi (max journalier connu = quasi-certitude)
            if mkt.get("_peak_confirmed_no") and certainty == "medium":
                log(f"  🏔️  Pic confirmé : certitude medium → accepté (max_station={mkt.get('_max_observed')})")
                certainty = "high"   # traiter comme high pour le calcul de mise
```

- [ ] **Step 4: Branch the exposure cap check**

The exposure check currently reads (around line 831-834):

```python
        # Vérif exposition globale (sur portefeuille total)
        if total_exposed >= total_portfolio * MAX_EXPOSURE_PCT:
            log(f"  ⛔ Exposition max atteinte — stop")
            break
```

Replace with:

```python
        # Vérif exposition — plafonds séparés NO/YES (sur portefeuille total)
        if is_yes:
            if total_exposed_yes >= total_portfolio * MAX_YES_EXPOSURE_PCT:
                log(f"  ⛔ Exposition YES max atteinte ({total_exposed_yes:.0f}$ / {total_portfolio*MAX_YES_EXPOSURE_PCT:.0f}$) — ignoré")
                continue
        else:
            if total_exposed >= total_portfolio * MAX_EXPOSURE_PCT:
                log(f"  ⛔ Exposition NO max atteinte — stop")
                break
```

- [ ] **Step 5: Branch the price double-check (T1/T2)**

The double price-check currently reads (around line 843-866):

```python
        # Double vérif prix NO en temps réel
        price_t1 = _get_current_no_price(cid)
        if price_t1 is None:
            log(f"  🚫 CLOB inaccessible — annulé")
            continue
        if not (MIN_NO_PRICE <= price_t1 <= MAX_NO_PRICE):
            log(f"  🚫 Prix NO T1 {price_t1:.3f} hors zone [{MIN_NO_PRICE}-{MAX_NO_PRICE}] — annulé")
            continue

        no_estimate = float(d.get("no_price", 0) or 0)
        if no_estimate > 0 and abs(price_t1 - no_estimate) / no_estimate > 0.10:
            log(f"  🚫 Écart T1 trop élevé : estimé {no_estimate:.3f}, réel {price_t1:.3f} — annulé")
            continue

        time.sleep(4)
        price_t2 = _get_current_no_price(cid)
        if price_t2 is None or not (MIN_NO_PRICE <= price_t2 <= MAX_NO_PRICE):
            log(f"  🚫 Prix T2 hors zone — annulé")
            continue
        if price_t1 - price_t2 > 0.02:
            log(f"  🚫 NO en chute : {price_t1:.3f}→{price_t2:.3f} — annulé")
            continue
        log(f"  ✅ Prix NO stable T1={price_t1:.3f} T2={price_t2:.3f}")
        d["no_price"] = price_t2
```

Replace with:

```python
        # Double vérif prix en temps réel — bornes et champ d'estimation selon NO/YES
        min_price, max_price = (MIN_YES_PRICE, MAX_YES_PRICE) if is_yes else (MIN_NO_PRICE, MAX_NO_PRICE)
        estimate_field = "yes_price" if is_yes else "no_price"
        label = "YES" if is_yes else "NO"

        if is_yes:
            _, price_t1 = _get_both_prices(cid)
        else:
            price_t1 = _get_current_no_price(cid)
        if price_t1 is None:
            log(f"  🚫 CLOB inaccessible — annulé")
            continue
        if not (min_price <= price_t1 <= max_price):
            log(f"  🚫 Prix {label} T1 {price_t1:.3f} hors zone [{min_price}-{max_price}] — annulé")
            continue

        estimate = float(d.get(estimate_field, 0) or 0)
        if estimate > 0 and abs(price_t1 - estimate) / estimate > 0.10:
            log(f"  🚫 Écart T1 trop élevé : estimé {estimate:.3f}, réel {price_t1:.3f} — annulé")
            continue

        time.sleep(4)
        if is_yes:
            _, price_t2 = _get_both_prices(cid)
        else:
            price_t2 = _get_current_no_price(cid)
        if price_t2 is None or not (min_price <= price_t2 <= max_price):
            log(f"  🚫 Prix T2 hors zone — annulé")
            continue
        if price_t1 - price_t2 > 0.02:
            log(f"  🚫 {label} en chute : {price_t1:.3f}→{price_t2:.3f} — annulé")
            continue
        log(f"  ✅ Prix {label} stable T1={price_t1:.3f} T2={price_t2:.3f}")
        d[estimate_field] = price_t2
```

- [ ] **Step 6: Branch order placement (YES_DRY_RUN simulation) and trade recording**

The order placement currently reads (around line 868-898):

```python
        try:
            log(f"→ BUY NO | {cid[:12]}… | ${amount:.2f} [{certainty}] | {d.get('reason','')}")
            result = trader.place_market_order(
                condition_id=cid,
                outcome="No",
                side="buy",
                amount_usdc=amount,
            )
            if not result.get("ok") and not result.get("dry_run"):
                log(f"  ⚠️  Ordre rejeté")
                continue
            trade = {
                "id":           str(uuid.uuid4()),
                "bot_id":       BOT_ID,
                "time":         datetime.datetime.now().isoformat(),
                "market":       "polymarket",
                "condition_id": cid,
                "city":         mkt.get("city", ""),
                "sym":          "NO",
                "side":         "buy",
                "amount_usdc":  amount,
                "price":        float(result.get("price", 0) or price_t2),
                "reason":       d.get("reason", ""),
                "result":       result,
                "pnl":          None,
            }
            insert_trade(trade)
            total_exposed += amount
            usdc -= amount
            traded_city_dates.append(city_date_key)
            log(f"  ✅ Enregistré | Exposition : ${total_exposed:.2f}")
        except Exception as e:
            log(f"  ❌ Erreur ordre : {e}")
```

Replace with:

```python
        try:
            log(f"→ BUY {label} | {cid[:12]}… | ${amount:.2f} [{certainty}] | {d.get('reason','')}")
            if is_yes and YES_DRY_RUN:
                log(f"  [YES_DRY_RUN] Ordre simulé — pas d'appel réel au SDK (indépendant du DRY_RUN global)")
                result = {
                    "dry_run": True,
                    "condition_id": cid,
                    "outcome": "Yes",
                    "side": "buy",
                    "amount_usdc": amount,
                    "price": price_t2,
                    "status": "simulated_yes_dry_run",
                }
            else:
                result = trader.place_market_order(
                    condition_id=cid,
                    outcome="Yes" if is_yes else "No",
                    side="buy",
                    amount_usdc=amount,
                )
            if not result.get("ok") and not result.get("dry_run"):
                log(f"  ⚠️  Ordre rejeté")
                continue
            trade = {
                "id":           str(uuid.uuid4()),
                "bot_id":       BOT_ID,
                "time":         datetime.datetime.now().isoformat(),
                "market":       "polymarket",
                "condition_id": cid,
                "city":         mkt.get("city", ""),
                "sym":          "YES" if is_yes else "NO",
                "side":         "buy",
                "amount_usdc":  amount,
                "price":        float(result.get("price", 0) or price_t2),
                "reason":       d.get("reason", ""),
                "result":       result,
                "pnl":          None,
            }
            insert_trade(trade)
            if is_yes:
                total_exposed_yes += amount
            else:
                total_exposed += amount
            usdc -= amount
            traded_city_dates.append(city_date_key)
            log(f"  ✅ Enregistré | Exposition NO : ${total_exposed:.2f} | Exposition YES : ${total_exposed_yes:.2f}")
        except Exception as e:
            log(f"  ❌ Erreur ordre : {e}")
```

- [ ] **Step 7: Update the startup log banner**

In `bot/loop_v2.py`, the `if __name__ == "__main__":` block currently logs (around line 930-933):

```python
    log(f"🌤️  ProfitWeather V2.0 démarré — cycle toutes les {INTERVAL_MINUTES} min")
    log(f"   Stratégie : NO sur fourchettes température (70–95¢)")
    log(f"   Mises : 2–5% du solde selon certitude (max {MAX_BET_PCT*100:.0f}% par trade, max {MAX_EXPOSURE_PCT*100:.0f}% exposé)")
    log(f"   Mode : {'SIMULATION (DRY_RUN)' if trader.DRY_RUN else '⚠️  TRADING RÉEL'}")
```

Replace with:

```python
    log(f"🌤️  ProfitWeather V2.0 démarré — cycle toutes les {INTERVAL_MINUTES} min")
    log(f"   Stratégie : NO sur fourchettes température (70–95¢)")
    log(f"   Mises : 2–5% du solde selon certitude (max {MAX_BET_PCT*100:.0f}% par trade, max {MAX_EXPOSURE_PCT*100:.0f}% exposé)")
    log(f"   Mode NO  : {'SIMULATION (DRY_RUN)' if trader.DRY_RUN else '⚠️  TRADING RÉEL'}")
    log(f"   Voie YES : villes {sorted(YES_WHITELIST_CITIES)} | prix [{MIN_YES_PRICE}-{MAX_YES_PRICE}] | exposition max {MAX_YES_EXPOSURE_PCT*100:.0f}% | mode {'SIMULATION (YES_DRY_RUN)' if YES_DRY_RUN else '⚠️  TRADING RÉEL'}")
```

- [ ] **Step 8: Run the full existing test suite to confirm no regression**

Run: `cd "bot" && for f in test_loop_v2_*.py test_brain_*.py; do python3 "$f" || echo "FAILED: $f"; done`
Expected: every test prints its `✅` line, no `FAILED` line.

- [ ] **Step 9: Manual smoke test in DRY_RUN (real Supabase, real Polymarket reads, no real orders)**

This step can't be unit-tested (it needs the live Claude API, live Polymarket market data, and a
real Supabase connection) — run it manually and read the logs:

Run: `cd "bot" && source .env && YES_DRY_RUN=true ~/.pyenv/versions/3.11.9/bin/python3 -c "
import loop_v2
loop_v2.run_cycle()
"`

Expected in the output:
- The startup-style banner isn't printed by `run_cycle()` itself, but you should see
  `📊 N/M marchés passent les filtres` where N may now include `🟢 YES éligible <ville>` log lines
  for Chengdu/Seoul/London/Tokyo if any of their markets are currently in the `[0.75-0.96]` YES
  price band.
- If Claude proposes a YES trade, the log shows `→ BUY YES | ...` followed by
  `[YES_DRY_RUN] Ordre simulé...` — confirm no real order was placed (check Polymarket UI / wallet
  balance unchanged).
- Confirm the existing NO flow still logs `→ BUY NO | ...` with real `trader.place_market_order`
  calls exactly as before (unchanged behavior).

- [ ] **Step 10: Commit**

```bash
git add bot/loop_v2.py
git commit -m "feat: run_cycle execute les decisions YES (prix, exposition et dry-run separes du NO)"
```

---

### Task 5: Documentation

**Files:**
- Modify: `CLAUDE.md` (ProfitWeather V2 section)
- Modify: `STRATEGIE_BOT.md` (langage simple pour l'utilisateur)

**Interfaces:**
- None (docs only).

- [ ] **Step 1: Update `CLAUDE.md`**

In the `## ProfitWeather V2 — Bot de trading (local)` section of `CLAUDE.md`, after the existing
"Paramètres hard-codés loop_v2.py" code block, add a new subsection:

```markdown
### Voie YES haute conviction (ajout 23/06/2026)
En plus du NO ci-dessus (inchangé), le bot achète aussi du **YES** sur 4 villes où l'historique
prouvé est de 92-100% de réussite (mesuré sur le signal prix ≥75% du bot 45 villes, PAS sur
l'accord ECMWF — aucun backtest ECMWF↔résultat réel n'existe) :
```python
YES_WHITELIST_CITIES = {"chengdu", "seoul", "london", "tokyo"}
MIN_YES_PRICE         = 0.75
MAX_YES_PRICE         = 0.96
MAX_YES_EXPOSURE_PCT  = 0.20   # plafond séparé du NO
```
- Déclenchement : prix YES déjà élevé sur ces 4 villes (pas de filtre ECMWF, contrairement au NO).
- `YES_DRY_RUN` (variable d'env, défaut `true`) : interrupteur indépendant du `DRY_RUN` global —
  permet de tester le YES en simulation pendant que le NO continue de trader en réel.
- Pas de take-profit/stop-loss/hedge sur les positions YES pour l'instant — tenues jusqu'à
  résolution naturelle.
- Spec complète : `docs/superpowers/specs/2026-06-23-profitweather-yes-pivot-design.md`
```

- [ ] **Step 2: Update `STRATEGIE_BOT.md`**

Read the existing file first (`cat STRATEGIE_BOT.md`) to match its tone (langage simple, sans
jargon), then add a short paragraph near the ProfitWeather section explaining: "Le bot achète
maintenant aussi des paris 'OUI' (et pas seulement 'NON') sur 4 villes où on a vérifié qu'il a
presque toujours raison (Chengdu, Séoul, Londres, Tokyo), en plus de sa stratégie habituelle. Ces
nouveaux paris sont d'abord testés en simulation avant d'utiliser de l'argent réel."

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md STRATEGIE_BOT.md
git commit -m "docs: documente la voie YES haute conviction de ProfitWeather V2"
```

---

## After implementation

Once Task 4's manual smoke test (Step 9) looks correct over a few real cycles with
`YES_DRY_RUN=true`, the user can flip `YES_DRY_RUN=false` in `bot/.env` to start trading YES with
real money — this is a manual decision, not part of this plan.
