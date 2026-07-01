"""
backtest_weather_sources.py — Compare la précision de plusieurs sources de prévision
météo par rapport à la résolution réelle des marchés température Polymarket.

Sources comparées :
  - open_meteo_blend : Open-Meteo sans modèle spécifié (blend par défaut)
  - ecmwf             : Open-Meteo modèle ecmwf_ifs025
  - gfs               : Open-Meteo modèle gfs_global
  - icon              : Open-Meteo modèle icon_seamless
  - meteofrance       : Open-Meteo modèle meteofrance_seamless

Méthodologie :
  Pour chaque marché résolu récemment (J-1 à J-4, toutes villes), on identifie
  la fourchette gagnante (celle qui a resolved YES). On interroge chaque source
  pour sa prévision de température max ce jour-là (limite : les APIs de prévision
  ne conservent pas l'historique des prévisions passées, donc on interroge "au mieux"
  ce que le modèle donne aujourd'hui pour cette date passée — proxy raisonnable mais
  pas une reconstruction exacte de ce qu'aurait vu le bot au moment du trade).
  On regarde ensuite si la valeur de la source tombe dans la fourchette gagnante.

Usage : python3 backtest_weather_sources.py
"""
from __future__ import annotations
import re
import sys
import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, ".")
from weather_validator import CITY_COORDS, CITY_TZ

GAMMA_API = "https://gamma-api.polymarket.com/events"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 10
DAYS_BACK = 4  # J-1 à J-4

MODELS = {
    "open_meteo_blend": None,
    "ecmwf":             "ecmwf_ifs025",
    "gfs":               "gfs_global",
    "icon":              "icon_seamless",
    "meteofrance":       "meteofrance_seamless",
}

CITIES = list(CITY_COORDS.keys())


def _event_slug(city: str, date: datetime.date) -> str:
    return f"highest-temperature-in-{city}-on-{date.strftime('%B').lower()}-{date.day}-{date.year}"


def _detect_unit(question: str) -> str:
    m = re.search(r"°\s*([FC])\b", question, re.IGNORECASE)
    if m:
        return "fahrenheit" if m.group(1).upper() == "F" else "celsius"
    return "fahrenheit"  # défaut si non détecté


def _parse_range(question: str) -> tuple[float, float, str] | None:
    unit = _detect_unit(question)
    m = re.search(r"between (\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", question, re.IGNORECASE)
    if m:
        return float(m.group(1)), float(m.group(2)), unit
    m = re.search(r"(\d+(?:\.\d+)?)\s*°?[FC]?\s+or below", question, re.IGNORECASE)
    if m:
        return -200.0, float(m.group(1)), unit
    m = re.search(r"(\d+(?:\.\d+)?)\s*°?[FC]?\s+or higher", question, re.IGNORECASE)
    if m:
        return float(m.group(1)), 200.0, unit
    m = re.search(r"be (\d+(?:\.\d+)?)\s*°?[FC]\b", question, re.IGNORECASE)
    if m:
        v = float(m.group(1))
        return v, v + 1, unit  # bucket "exact degree" = [v, v+1)
    return None


def fetch_resolved_market(city: str, date: datetime.date) -> dict | None:
    """Retourne {city, date, winning_range, station, all_ranges} si le marché est résolu, sinon None."""
    slug = _event_slug(city, date)
    try:
        r = requests.get(GAMMA_API, params={"slug": slug}, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        events = r.json()
        if not events:
            return None
        ev = events[0]
        if not ev.get("closed"):
            return None

        winning_range = None
        unit = None
        import json as _json
        for m in ev.get("markets", []):
            question = m.get("question", "")
            rng = _parse_range(question)
            if not rng:
                continue
            raw_prices = m.get("outcomePrices", [])
            prices = _json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
            if not prices:
                continue
            if float(prices[0]) >= 0.5:  # Yes gagnant
                winning_range = (rng[0], rng[1])
                unit = rng[2]

        if not winning_range:
            return None

        resolution_source = ev.get("resolutionSource", "") or ""
        station = resolution_source.rstrip("/").split("/")[-1] if resolution_source else None

        return {
            "city": city, "date": date.isoformat(),
            "winning_range": winning_range, "unit": unit, "station": station,
        }
    except Exception:
        return None


def fetch_model_max(lat: float, lon: float, date: datetime.date, model: str | None, unit="fahrenheit") -> float | None:
    params = {
        "latitude": lat, "longitude": lon,
        "daily": "temperature_2m_max",
        "temperature_unit": unit,
        "timezone": "UTC",
        "start_date": str(date), "end_date": str(date),
    }
    if model:
        params["models"] = model
    try:
        r = requests.get(OPEN_METEO_FORECAST, params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        vals = r.json().get("daily", {}).get("temperature_2m_max", [])
        return float(vals[0]) if vals and vals[0] is not None else None
    except Exception:
        return None


def main():
    today = datetime.date.today()
    targets = [(city, today - datetime.timedelta(days=d))
               for city in CITIES for d in range(1, DAYS_BACK + 1)]

    print(f"Scanning {len(targets)} (city, date) combos for resolved markets...")
    resolved = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(fetch_resolved_market, c, d): (c, d) for c, d in targets}
        for f in as_completed(futures):
            res = f.result()
            if res:
                resolved.append(res)

    print(f"Found {len(resolved)} resolved temperature markets.\n")

    # Pour chaque marché résolu, interroge chaque source
    results = {name: {"hits": 0, "total": 0, "abs_errors": []} for name in MODELS}

    def process(market):
        city = market["city"]
        coords = CITY_COORDS.get(city)
        if not coords:
            return
        lat, lon = coords
        date = datetime.date.fromisoformat(market["date"])
        low, high = market["winning_range"]
        unit = market["unit"] or "fahrenheit"
        clamp_lo, clamp_hi = (-70, 60) if unit == "celsius" else (-100, 150)
        mid = (max(low, clamp_lo) + min(high, clamp_hi)) / 2  # proxy pour l'erreur absolue

        row = {"city": city, "date": market["date"], "winning_range": market["winning_range"],
               "unit": unit, "sources": {}}
        for name, model_id in MODELS.items():
            val = fetch_model_max(lat, lon, date, model_id, unit=unit)
            if val is None:
                continue
            hit = low <= val <= high
            row["sources"][name] = {"value": round(val, 1), "hit": hit}
            results[name]["total"] += 1
            if hit:
                results[name]["hits"] += 1
            results[name]["abs_errors"].append(abs(val - mid))
        return row

    rows = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(process, m) for m in resolved]
        for f in as_completed(futures):
            row = f.result()
            if row:
                rows.append(row)

    print("=== Résultat par source (global) ===")
    for name, stats in results.items():
        total = stats["total"]
        hits = stats["hits"]
        errs = stats["abs_errors"]
        hit_rate = hits / total * 100 if total else 0
        mae = sum(errs) / len(errs) if errs else 0
        print(f"  {name:18s} n={total:4d}  hit_rate={hit_rate:5.1f}%  MAE={mae:4.2f}")

    print(f"\nTotal marchés résolus analysés : {len(rows)}")

    print("\n=== Résultat par source, par région (unit fahrenheit≈US, celsius≈reste du monde) ===")
    for region_unit, label in (("fahrenheit", "US (°F)"), ("celsius", "International (°C)")):
        print(f"\n  -- {label} --")
        region_rows = [r for r in rows if r["unit"] == region_unit]
        for name in MODELS:
            vals = [(r["sources"][name]["hit"], abs(r["sources"][name]["value"] -
                    (max(r["winning_range"][0], -100) + min(r["winning_range"][1], 150)) / 2))
                    for r in region_rows if name in r["sources"]]
            if not vals:
                continue
            n = len(vals)
            hit_rate = sum(1 for h, _ in vals if h) / n * 100
            mae = sum(e for _, e in vals) / n
            print(f"    {name:18s} n={n:4d}  hit_rate={hit_rate:5.1f}%  MAE={mae:4.2f}")


if __name__ == "__main__":
    main()
