"""
Récupère les stations Weather Underground (WU) pour chaque ville
depuis les descriptions des marchés Polymarket.
"""
import re
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

GAMMA = "https://gamma-api.polymarket.com/events"
DATE  = "june-17-2026"

CITIES = [
    "ankara", "istanbul", "london", "paris", "madrid", "amsterdam",
    "warsaw", "milan", "munich", "helsinki", "moscow", "tel-aviv",
    "nyc", "atlanta", "chicago", "houston", "dallas", "denver",
    "miami", "seattle", "san-francisco", "los-angeles", "toronto",
    "mexico-city", "tokyo", "seoul", "busan", "beijing", "shanghai",
    "chengdu", "guangzhou", "shenzhen", "chongqing", "wuhan", "qingdao",
    "hong-kong", "taipei", "singapore", "kuala-lumpur", "manila",
    "wellington", "cape-town", "jeddah", "karachi", "lucknow",
]

def fetch_wu_url(city: str):
    slug = f"highest-temperature-in-{city}-on-{DATE}"
    try:
        r = requests.get(GAMMA, params={"slug": slug}, timeout=10)
        data = r.json()
        if not data:
            return city, None
        desc = data[0].get("description", "")
        m = re.search(r'https://www\.wunderground\.com/history/daily/[^\s\n"\'\.]+', desc)
        if m:
            return city, m.group(0)
    except Exception as e:
        print(f"  ERR {city}: {e}")
    return city, None

results = {}
print(f"Fetching WU stations for {len(CITIES)} cities...\n")

with ThreadPoolExecutor(max_workers=10) as pool:
    futures = {pool.submit(fetch_wu_url, c): c for c in CITIES}
    for f in as_completed(futures):
        city, url = f.result()
        if url:
            # Extract station code from URL (last path segment)
            station = url.rstrip("/").split("/")[-1]
            results[city] = {"url": url, "station": station}
            print(f"  ✅ {city:20s} → {station:6s}  ({url})")
        else:
            results[city] = {"url": None, "station": None}
            print(f"  ❌ {city:20s} → NOT FOUND")

# Save results
out_path = __file__.replace("fetch_wu_stations.py", "wu_stations.json")
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"\n✅ Saved to {out_path}")

# Print Python dict for weather_validator.py
print("\n# Copier dans weather_validator.py :")
print("CITY_WU_STATIONS = {")
for city, d in sorted(results.items()):
    s = d["station"] or "???"
    print(f"    '{city}': '{s}',")
print("}")
