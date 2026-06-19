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
