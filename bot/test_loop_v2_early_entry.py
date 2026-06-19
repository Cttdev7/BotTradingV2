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
