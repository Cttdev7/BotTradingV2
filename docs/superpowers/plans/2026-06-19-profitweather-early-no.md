# ProfitWeather V2 — Entrée précoce NO sous prévision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire en sorte que `bot/loop_v2.py` (ProfitWeather V2) reproduise la pratique manuelle de l'utilisateur : acheter NO sur une fourchette de température clairement sous la prévision dès que le marché ouvre (sans attendre 15h locale ni la fenêtre des 20h restantes), avec un seuil de cascade plus sensible (35% au lieu de 60%) et un plafond de prix légèrement plus haut (96¢ au lieu de 95¢).

**Architecture:** Un seul fichier modifié, `bot/loop_v2.py`. La fonction `_prefilter()` est réordonnée pour calculer la direction de l'écart prévision/fourchette (`bounds`, `forecast_mean`, `early_entry_down`) **avant** les deux verrous temporels (`MAX_HOURS_REMAINING`, attente 15h locale), afin de pouvoir les contourner pour les candidats clairement sous la prévision. Deux constantes (`CASCADE_TRIGGER`, `MAX_NO_PRICE`) sont ajustées. Aucun nouveau fichier, aucune nouvelle dépendance, aucun changement à `brain.py`/`trader.py`/Supabase.

**Tech Stack:** Python 3.11 (`~/.pyenv/versions/3.11.9/bin/python3`), aucune librairie nouvelle.

## Global Constraints

- Toutes les valeurs viennent de la spec `docs/superpowers/specs/2026-06-19-profitweather-early-no-design.md` — ne pas en inventer d'autres.
- `MIN_FORECAST_GAP_DOWN` reste à `2.0` (inchangé) — c'est le seuil de gap utilisé pour décider qu'un range est "sous la prévision".
- Le chemin "range AU-DESSUS de la prévision" reste **toujours bloqué** (sauf pic METAR confirmé déjà existant) — ne pas toucher à cette règle.
- `MIN_HOURS_REMAINING` (1h) reste appliqué **sans exception**, y compris pour l'entrée précoce.
- Prix NO doit rester entre `MIN_NO_PRICE` (0.75, inchangé) et le nouveau `MAX_NO_PRICE` (0.96).
- Claude Haiku continue de valider chaque candidat retenu par `_prefilter()` — ne touche pas à `brain.py`.
- Pas de pytest dans ce projet — la vérification se fait via un script `assert`-based exécuté avec `~/.pyenv/versions/3.11.9/bin/python3`, suivant le modèle de `bot/test_zth_timing.py`.
- Ne pas committer de fichier `.env`.

---

### Task 1: Entrée précoce — réordonner `_prefilter()` pour bypasser les verrous temporels

**Files:**
- Modify: `bot/loop_v2.py:466-624` (corps de la boucle `for m in markets:` dans `_prefilter()`)
- Create: `bot/test_loop_v2_early_entry.py`

**Interfaces:**
- Consumes : `_prefilter(markets: list, history: list, usdc: float, deko_cids: set = None) -> list` (signature inchangée), `_parse_range_bounds(question: str) -> tuple[float, float] | None`, `_hours_remaining(end_date_iso: str) -> float | None`, `_detect_cascade(markets: list) -> dict`, `MIN_FORECAST_GAP_DOWN`, `MIN_HOURS_REMAINING`, `MAX_HOURS_REMAINING`, `MIN_NO_PRICE`, `MAX_NO_PRICE` (toutes déjà définies dans le fichier, ne pas les redéfinir).
- Produces : aucun nouveau symbole exporté — la fonction `_prefilter` garde exactement la même signature et le même type de retour (`list` de dicts `m` avec les mêmes clés `_hours_left`, `_gap`, `_gap_direction`, `_cascade`, etc. déjà existantes). Les tasks 2 et 3 ne dépendent pas de cette task (elles modifient des constantes indépendantes), mais doivent être appliquées sur le fichier déjà modifié par cette task.

Le code actuel de `_prefilter` (lignes 466-511) est :

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

        # Temps restant avant clôture
        hours_left = _hours_remaining(m.get("end_date_iso", ""))
        if hours_left is not None:
            if hours_left < MIN_HOURS_REMAINING:
                label = "déjà fermé" if hours_left < 0 else f"ferme dans {hours_left:.1f}h"
                log(f"  ⏰ {city} {label} — ignoré")
                continue
            if hours_left > MAX_HOURS_REMAINING:
                log(f"  ⏰ {city} ferme dans {hours_left:.1f}h — trop tôt, ignoré")
                continue
            m["_hours_left"] = hours_left  # transmis à Claude pour contexte

        # Prix NO dans la zone cible
        if not (MIN_NO_PRICE <= no_price <= MAX_NO_PRICE):
            continue

        # Parse les bornes une seule fois (réutilisé pour tous les filtres suivants)
        bounds = _parse_range_bounds(q)
```

- [ ] **Step 1: Remplacer ce bloc par la version réordonnée**

Remplace exactement ce bloc (de `kept = []` jusqu'à la ligne `bounds = _parse_range_bounds(q)` incluse) par :

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

        # Parse les bornes une seule fois (réutilisé pour tous les filtres suivants) —
        # calculé ici, avant les verrous temporels, car l'entrée précoce ci-dessous en a besoin
        bounds = _parse_range_bounds(q)

        # Entrée précoce (pratique manuelle de l'utilisateur) : si le range est déjà
        # clairement EN-DESSOUS de la prévision (gap >= MIN_FORECAST_GAP_DOWN), on sait
        # déjà que ce range est dépassé → pas besoin d'attendre 15h locale ni la fenêtre
        # des 20h restantes, on peut trader dès que le marché ouvre.
        forecast_mean = wx.get("models_avg") or wx.get("current_temp")
        early_entry_down = False
        if forecast_mean is not None and bounds:
            _low_e, _high_e = bounds
            if forecast_mean > _high_e and (forecast_mean - _high_e) >= MIN_FORECAST_GAP_DOWN:
                early_entry_down = True

        # Temps restant avant clôture
        hours_left = _hours_remaining(m.get("end_date_iso", ""))
        if hours_left is not None:
            if hours_left < MIN_HOURS_REMAINING:
                label = "déjà fermé" if hours_left < 0 else f"ferme dans {hours_left:.1f}h"
                log(f"  ⏰ {city} {label} — ignoré")
                continue
            if hours_left > MAX_HOURS_REMAINING and not early_entry_down:
                log(f"  ⏰ {city} ferme dans {hours_left:.1f}h — trop tôt, ignoré")
                continue
            m["_hours_left"] = hours_left  # transmis à Claude pour contexte

        # Prix NO dans la zone cible
        if not (MIN_NO_PRICE <= no_price <= MAX_NO_PRICE):
            continue
```

- [ ] **Step 2: Mettre à jour le filtre timing J+0 pour accepter l'entrée précoce**

Le code actuel (juste après le bloc "pic confirmé METAR", repère-le par son commentaire `# ── Filtre timing J+0`) est :

```python
        # ── Filtre timing J+0 ──────────────────────────────────────────────────
        # Attendre 15h heure locale SAUF si le pic est déjà confirmé par METAR
        if day_offset == 0 and local_hour is not None and local_hour < 15:
            if is_peak_no:
                log(f"  🏔️  {city} avant 15h mais pic METAR confirmé → trade autorisé")
            elif cid not in cascade_signals:
                log(f"  🕐 {city} marché J+0 mais {local_hour}h locale — attendre 15h")
                continue
```

Remplace-le par :

```python
        # ── Filtre timing J+0 ──────────────────────────────────────────────────
        # Attendre 15h heure locale SAUF si le pic est déjà confirmé par METAR,
        # SAUF signal cascade, SAUF entrée précoce (range déjà sous la prévision)
        if day_offset == 0 and local_hour is not None and local_hour < 15:
            if is_peak_no:
                log(f"  🏔️  {city} avant 15h mais pic METAR confirmé → trade autorisé")
            elif early_entry_down:
                log(f"  🌙 {city} avant 15h mais entrée précoce (range sous prévision) → trade autorisé")
            elif cid not in cascade_signals:
                log(f"  🕐 {city} marché J+0 mais {local_hour}h locale — attendre 15h")
                continue
```

- [ ] **Step 3: Retirer le recalcul redondant de `forecast_mean` plus bas dans la fonction**

Plus bas dans `_prefilter`, repère ce bloc (juste avant la section "Écart entre prévision météo et fourchette du marché — DIRECTIONNEL") :

```python
        forecast_mean = wx.get("models_avg") or wx.get("current_temp")
        if forecast_mean is not None and bounds and cid not in cascade_signals:
```

Remplace-le par (suppression de la ligne de recalcul, `forecast_mean` est déjà disponible depuis le Step 1 et porte exactement la même valeur) :

```python
        if forecast_mean is not None and bounds and cid not in cascade_signals:
```

- [ ] **Step 4: Écrire le script de test `bot/test_loop_v2_early_entry.py`**

```python
"""Test de l'entrée précoce NO sous prévision dans _prefilter() (pas d'appel réseau)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import datetime
from loop_v2 import _prefilter


def _end_iso(hours_from_now: float) -> str:
    end = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours_from_now)
    return end.isoformat()


def _make_market(cid, low, high, forecast, hours_left, local_hour=9, day_offset=0,
                  no_price=0.80, remaining_max=None):
    if remaining_max is None:
        remaining_max = low - 5
    return {
        "condition_id": cid,
        "city": "testville",
        "question": f"Will the highest temperature in Testville on June 20 be between {low} and {high} degrees?",
        "volume": 5000,
        "tokens": [{"outcome": "Yes", "price": round(1 - no_price, 2)},
                   {"outcome": "No", "price": no_price}],
        "local_hour": local_hour,
        "day_offset": day_offset,
        "end_date_iso": _end_iso(hours_left),
        "weather_ctx": {
            "models_avg": forecast,
            "band_prob": 10,
            "models_spread": 2,
            "ensemble_prob": 5,
            "peak_passed": False,
            "max_today": None,
            "remaining_max": remaining_max,
        },
    }


# Test 1 : range sous prévision (gap=3°F >= MIN_FORECAST_GAP_DOWN=2.0), avant 15h locale,
# 18h restantes (dans la fenêtre normale) → doit être accepté.
m1 = _make_market("cid1", 28, 29, forecast=32, hours_left=18, local_hour=9, day_offset=0)
kept1 = _prefilter([m1], [], 1000.0)
assert any(m["condition_id"] == "cid1" for m in kept1), \
    "Test1: range sous prévision avant 15h doit être accepté (entrée précoce)"

# Test 2 : même range sous prévision, mais 25h restantes (hors fenêtre MAX_HOURS_REMAINING=20h)
# → doit être accepté grâce au bypass.
m2 = _make_market("cid2", 28, 29, forecast=32, hours_left=25, local_hour=9, day_offset=0)
kept2 = _prefilter([m2], [], 1000.0)
assert any(m["condition_id"] == "cid2" for m in kept2), \
    "Test2: range sous prévision à 25h de la clôture doit être accepté (bypass MAX_HOURS_REMAINING)"

# Test 3 : range AU-DESSUS de la prévision (forecast=32 < low=34) → comportement inchangé,
# doit rester rejeté même avec les mêmes conditions de timing.
m3 = _make_market("cid3", 34, 35, forecast=32, hours_left=18, local_hour=9, day_offset=0,
                   remaining_max=20)
kept3 = _prefilter([m3], [], 1000.0)
assert not any(m["condition_id"] == "cid3" for m in kept3), \
    "Test3: range au-dessus de la prévision doit rester bloqué"

# Test 4 : range sous prévision mais ferme dans 0.5h (< MIN_HOURS_REMAINING=1h)
# → doit rester rejeté, MIN_HOURS_REMAINING reste appliqué sans exception.
m4 = _make_market("cid4", 28, 29, forecast=32, hours_left=0.5, local_hour=9, day_offset=0)
kept4 = _prefilter([m4], [], 1000.0)
assert not any(m["condition_id"] == "cid4" for m in kept4), \
    "Test4: marché qui ferme dans <1h doit rester rejeté"

print("✅ Tous les tests d'entrée précoce passent")
```

- [ ] **Step 5: Lancer le test**

Run: `~/.pyenv/versions/3.11.9/bin/python3 bot/test_loop_v2_early_entry.py`
Expected: `✅ Tous les tests d'entrée précoce passent` (aucune `AssertionError`, aucune exception d'import).

- [ ] **Step 6: Commit**

```bash
git add bot/loop_v2.py bot/test_loop_v2_early_entry.py
git commit -m "feat: ProfitWeather V2 trade dès l'ouverture du marché sur les ranges sous prévision"
```

---

### Task 2: Seuil cascade abaissé 60% → 35%

**Files:**
- Modify: `bot/loop_v2.py:61`

**Interfaces:**
- Consumes : aucune nouvelle dépendance.
- Produces : `CASCADE_TRIGGER` (constante déjà utilisée par `_detect_cascade`, Task 1 ne la modifie pas).

- [ ] **Step 1: Modifier la constante**

Code actuel (ligne 61) :

```python
CASCADE_TRIGGER = 0.60   # range dominant YES > 60% → signaux cascade activés sur le reste (40%)
```

Remplace par :

```python
CASCADE_TRIGGER = 0.35   # range dominant YES > 35% → signaux cascade activés sur le reste
```

- [ ] **Step 2: Écrire le script de test `bot/test_loop_v2_cascade_threshold.py`**

```python
"""Test du seuil de cascade abaissé à 35% (pas d'appel réseau)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from loop_v2 import _detect_cascade, CASCADE_TRIGGER

assert CASCADE_TRIGGER == 0.35, "CASCADE_TRIGGER doit être à 0.35"

markets = [
    {
        "condition_id": "dominant",
        "city": "testville",
        "end_date_iso": "2026-06-20T23:59:00Z",
        "tokens": [{"outcome": "Yes", "price": 0.40}, {"outcome": "No", "price": 0.60}],
    },
    {
        "condition_id": "adjacent",
        "city": "testville",
        "end_date_iso": "2026-06-20T23:59:00Z",
        "tokens": [{"outcome": "Yes", "price": 0.10}, {"outcome": "No", "price": 0.90}],
    },
]

cascade = _detect_cascade(markets)
assert "adjacent" in cascade, \
    "Un dominant à 40% (entre l'ancien seuil 60% et le nouveau 35%) doit déclencher la cascade sur l'autre range"
assert "dominant" not in cascade, "Le range dominant lui-même ne doit jamais être marqué cascade"

print("✅ Test seuil cascade passe")
```

- [ ] **Step 3: Lancer le test**

Run: `~/.pyenv/versions/3.11.9/bin/python3 bot/test_loop_v2_cascade_threshold.py`
Expected: `✅ Test seuil cascade passe`

- [ ] **Step 4: Commit**

```bash
git add bot/loop_v2.py bot/test_loop_v2_cascade_threshold.py
git commit -m "tweak: seuil cascade 60% → 35%"
```

---

### Task 3: Plafond prix NO 95¢ → 96¢

**Files:**
- Modify: `bot/loop_v2.py:42`

**Interfaces:**
- Consumes : aucune nouvelle dépendance.
- Produces : `MAX_NO_PRICE` (constante déjà utilisée par `_prefilter` et par la double vérification de prix avant exécution dans `run_cycle()`, lignes ~815-826 — aucune de ces deux utilisations n'a besoin d'être modifiée, elles lisent la constante).

- [ ] **Step 1: Modifier la constante**

Code actuel (ligne 42) :

```python
MAX_NO_PRICE      = 0.95    # NO maximum 95¢ (au-dessus = marge trop faible)
```

Remplace par :

```python
MAX_NO_PRICE      = 0.96    # NO maximum 96¢ (au-dessus = marge trop faible)
```

- [ ] **Step 2: Écrire le script de test `bot/test_loop_v2_price_cap.py`**

```python
"""Test du plafond de prix NO relevé à 0.96 (pas d'appel réseau)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import datetime
from loop_v2 import _prefilter, MAX_NO_PRICE

assert MAX_NO_PRICE == 0.96, "MAX_NO_PRICE doit être à 0.96"


def _end_iso(hours_from_now: float) -> str:
    end = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours_from_now)
    return end.isoformat()


def _make_market(cid, no_price):
    return {
        "condition_id": cid,
        "city": "testville",
        "question": "Will the highest temperature in Testville on June 20 be between 28 and 29 degrees?",
        "volume": 5000,
        "tokens": [{"outcome": "Yes", "price": round(1 - no_price, 2)},
                   {"outcome": "No", "price": no_price}],
        "local_hour": 16,
        "day_offset": 0,
        "end_date_iso": _end_iso(18),
        "weather_ctx": {
            "models_avg": 32, "band_prob": 10, "models_spread": 2,
            "ensemble_prob": 5, "peak_passed": False, "max_today": None,
            "remaining_max": 20,
        },
    }


# 96¢ doit passer (nouvelle limite)
kept_96 = _prefilter([_make_market("cid96", 0.96)], [], 1000.0)
assert any(m["condition_id"] == "cid96" for m in kept_96), "96¢ doit passer le filtre prix"

# 97¢ doit rester rejeté (au-dessus de la nouvelle limite)
kept_97 = _prefilter([_make_market("cid97", 0.97)], [], 1000.0)
assert not any(m["condition_id"] == "cid97" for m in kept_97), "97¢ doit rester rejeté"

print("✅ Test plafond prix passe")
```

- [ ] **Step 3: Lancer le test**

Run: `~/.pyenv/versions/3.11.9/bin/python3 bot/test_loop_v2_price_cap.py`
Expected: `✅ Test plafond prix passe`

- [ ] **Step 4: Commit**

```bash
git add bot/loop_v2.py bot/test_loop_v2_price_cap.py
git commit -m "tweak: plafond prix NO 95¢ → 96¢"
```
