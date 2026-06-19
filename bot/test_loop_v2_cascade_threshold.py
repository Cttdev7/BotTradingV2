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
