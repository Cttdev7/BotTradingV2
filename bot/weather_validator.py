"""
weather_validator.py — Vérifie la prévision météo avant tout trade YES.

Deux niveaux de vérification :
- Jour J (aujourd'hui en heure locale) : regarde le max des heures RESTANTES
  → si le pic de la journée est déjà passé et la temp ne peut plus monter, veto
- Jour J+1 (demain) : regarde le max journalier (marge 3°C)
"""
from __future__ import annotations
import re
import datetime
import requests

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_GEO      = "https://geocoding-api.open-meteo.com/v1/search"

CITY_COORDS = {
    'chengdu':       (30.67,  104.07),
    'seoul':         (37.57,  126.98),
    'hong-kong':     (22.32,  114.17),
    'nyc':           (40.71,  -74.01),
    'london':        (51.51,   -0.13),
    'tokyo':         (35.69,  139.69),
    'atlanta':       (33.75,  -84.39),
    'seattle':       (47.61, -122.33),
    'miami':         (25.77,  -80.19),
    'singapore':     ( 1.29,  103.85),
    'madrid':        (40.42,   -3.70),
    'shanghai':      (31.23,  121.47),
    'los-angeles':   (34.05, -118.24),
    'guangzhou':     (23.13,  113.26),
    'mexico-city':   (19.43,  -99.13),
    'amsterdam':     (52.37,    4.90),
    'paris':         (48.85,    2.35),
    'toronto':       (43.65,  -79.38),
    'chicago':       (41.85,  -87.65),
    'denver':        (39.74, -104.98),
    'houston':       (29.76,  -95.37),
    'taipei':        (25.05,  121.53),
    'beijing':       (39.91,  116.39),
    'san-francisco': (37.77, -122.42),
    'dallas':        (32.78,  -96.80),
    'wellington':    (-41.29,  174.78),
    'chongqing':     (29.56,  106.55),
    'wuhan':         (30.60,  114.31),
    'ankara':        (39.93,   32.85),
    'moscow':        (55.75,   37.62),
    'lucknow':       (26.85,   80.95),
    'istanbul':      (41.01,   28.95),
    'warsaw':        (52.23,   21.01),
    'milan':         (45.47,    9.19),
    'helsinki':      (60.17,   24.94),
    'karachi':       (24.86,   67.01),
    'cape-town':     (-33.93,  18.42),
    'jeddah':        (21.54,   39.17),
    'shenzhen':      (22.54,  114.06),
    'busan':         (35.10,  129.03),
    'qingdao':       (36.07,  120.38),
    'kuala-lumpur':  ( 3.14,  101.69),
    'tel-aviv':      (32.08,   34.78),
    'manila':        (14.60,  120.98),
    'munich':        (48.14,   11.58),
}

CITY_TZ = {
    'chengdu':       'Asia/Shanghai',
    'seoul':         'Asia/Seoul',
    'hong-kong':     'Asia/Hong_Kong',
    'nyc':           'America/New_York',
    'london':        'Europe/London',
    'tokyo':         'Asia/Tokyo',
    'atlanta':       'America/New_York',
    'seattle':       'America/Los_Angeles',
    'miami':         'America/New_York',
    'singapore':     'Asia/Singapore',
    'madrid':        'Europe/Madrid',
    'shanghai':      'Asia/Shanghai',
    'los-angeles':   'America/Los_Angeles',
    'guangzhou':     'Asia/Shanghai',
    'mexico-city':   'America/Mexico_City',
    'amsterdam':     'Europe/Amsterdam',
    'paris':         'Europe/Paris',
    'toronto':       'America/Toronto',
    'chicago':       'America/Chicago',
    'denver':        'America/Denver',
    'houston':       'America/Chicago',
    'taipei':        'Asia/Taipei',
    'beijing':       'Asia/Shanghai',
    'san-francisco': 'America/Los_Angeles',
    'dallas':        'America/Chicago',
    'wellington':    'Pacific/Auckland',
    'chongqing':     'Asia/Shanghai',
    'wuhan':         'Asia/Shanghai',
    'ankara':        'Europe/Istanbul',
    'moscow':        'Europe/Moscow',
    'lucknow':       'Asia/Kolkata',
    'istanbul':      'Europe/Istanbul',
    'warsaw':        'Europe/Warsaw',
    'milan':         'Europe/Rome',
    'helsinki':      'Europe/Helsinki',
    'karachi':       'Asia/Karachi',
    'cape-town':     'Africa/Johannesburg',
    'jeddah':        'Asia/Riyadh',
    'shenzhen':      'Asia/Shanghai',
    'busan':         'Asia/Seoul',
    'qingdao':       'Asia/Shanghai',
    'kuala-lumpur':  'Asia/Kuala_Lumpur',
    'tel-aviv':      'Asia/Jerusalem',
    'manila':        'Asia/Manila',
    'munich':        'Europe/Berlin',
}

_MONTHS = {
    'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
}

# Codes WMO (standard international météo)
_WMO_LABELS = {
    0: "☀️ ciel dégagé",
    1: "🌤️ quasi-dégagé", 2: "⛅ partiellement nuageux", 3: "☁️ couvert",
    45: "🌫️ brouillard", 48: "🌫️ brouillard givrant",
    51: "🌦️ bruine légère", 53: "🌦️ bruine", 55: "🌦️ bruine forte",
    61: "🌧️ pluie légère", 63: "🌧️ pluie", 65: "🌧️ pluie forte",
    71: "❄️ neige légère", 73: "❄️ neige", 75: "❄️ neige forte",
    77: "🌨️ grésil",
    80: "🌦️ averses", 81: "🌧️ averses modérées", 82: "⛈️ averses violentes",
    85: "🌨️ averses de neige", 86: "❄️ neige lourde",
    95: "⚡ orage", 96: "⛈️ orage + grêle", 99: "⛈️ orage violent + grêle",
}
_WMO_VETO  = {95, 96, 99}        # Orage/cyclone → température imprévisible → VETO
_WMO_SNOW  = {71, 73, 75, 77, 85, 86}  # Neige → température basse → VETO YES chaud


def _fetch_daily_risk(lat: float, lon: float, target_date, unit: str, tz_name: str) -> dict:
    """
    Tous les facteurs de risque météo en un seul appel API :
    pluie, vent, nuages, ensoleillement, neige, grêle, orage, rafales.
    """
    try:
        r = requests.get(OPEN_METEO_FORECAST, params={
            "latitude": lat, "longitude": lon,
            "daily": ",".join([
                "weathercode",
                "precipitation_sum",
                "precipitation_probability_max",
                "snowfall_sum",
                "sunshine_duration",
                "windspeed_10m_max",
                "windgusts_10m_max",
                "cloudcover_mean",
            ]),
            "temperature_unit": unit,
            "timezone": tz_name or "UTC",
            "start_date": str(target_date),
            "end_date":   str(target_date),
        }, timeout=8)
        if r.status_code != 200:
            return {}
        daily = r.json().get("daily", {})

        def _v(key):
            vals = daily.get(key, [])
            return vals[0] if vals and vals[0] is not None else None

        result = {}
        if (v := _v("weathercode"))                   is not None: result["wcode"]      = int(v)
        if (v := _v("precipitation_probability_max")) is not None: result["precip_prob"] = int(v)
        if (v := _v("precipitation_sum"))             is not None: result["precip_mm"]   = round(float(v), 1)
        if (v := _v("snowfall_sum"))                  is not None: result["snow_mm"]     = round(float(v), 1)
        if (v := _v("sunshine_duration"))             is not None: result["sun_h"]       = round(float(v) / 3600, 1)
        if (v := _v("windspeed_10m_max"))             is not None: result["wind_kmh"]    = round(float(v))
        if (v := _v("windgusts_10m_max"))             is not None: result["gusts_kmh"]   = round(float(v))
        if (v := _v("cloudcover_mean"))               is not None: result["cloud_pct"]   = int(v)
        if "wcode" in result:
            result["wlabel"] = _WMO_LABELS.get(result["wcode"], f"code {result['wcode']}")
        return result
    except Exception:
        return {}


def get_city_local_hour(city_slug: str) -> int | None:
    """Retourne l'heure locale actuelle dans la ville (0-23), ou None si inconnue."""
    tz_name = CITY_TZ.get(city_slug)
    if not tz_name or not ZoneInfo:
        return None
    try:
        return datetime.datetime.now(ZoneInfo(tz_name)).hour
    except Exception:
        return None


def _get_coords(city_slug: str):
    if city_slug in CITY_COORDS:
        return CITY_COORDS[city_slug]
    try:
        name = city_slug.replace('-', ' ').replace('_', ' ')
        r = requests.get(OPEN_METEO_GEO, params={'name': name, 'count': 1}, timeout=5)
        results = r.json().get('results', [])
        if results:
            return results[0]['latitude'], results[0]['longitude']
    except Exception:
        pass
    return None


def _parse_question(question: str) -> dict | None:
    # Cherche n'importe quel nombre suivi de °F ou °C dans la question
    # (les marchés Polymarket n'ont qu'un seul seuil de température)
    m = re.search(r'(\d+(?:\.\d+)?)\s*°([CF])\b', question, re.IGNORECASE)
    if not m:
        return None
    return {
        'threshold': float(m.group(1)),
        'unit': 'fahrenheit' if m.group(2).upper() == 'F' else 'celsius',
    }


def _parse_date_from_slug(slug: str) -> datetime.date | None:
    m = re.search(r'-on-([a-z]+)-(\d+)-(\d{4})', slug.lower())
    if not m:
        return None
    month = _MONTHS.get(m.group(1))
    if not month:
        return None
    try:
        return datetime.date(int(m.group(3)), month, int(m.group(2)))
    except ValueError:
        return None


def _apply_risk_veto(risk: dict, forecast: float, sym: str) -> str | None:
    """Retourne un message de veto si un risque majeur est détecté, sinon None."""
    wcode = risk.get("wcode")
    if wcode in _WMO_VETO:
        return f'⚡ {_WMO_LABELS.get(wcode, "orage")} — résultat imprévisible, VETO'
    if wcode in _WMO_SNOW:
        return f'❄️ {_WMO_LABELS.get(wcode, "neige")} — température basse garantie, VETO'
    if risk.get("snow_mm", 0) > 0.5:
        return f'❄️ Chutes de neige {risk["snow_mm"]}mm prévues — VETO'
    if risk.get("precip_prob", 0) >= 80:
        return f'🌧️ Pluie très probable ({risk["precip_prob"]}%) — refroidissement attendu, VETO'
    return None


def _risk_summary(risk: dict) -> str:
    """Résumé compact des facteurs de risque pour le log et Claude."""
    if not risk:
        return "météo inconnue"
    parts = []
    if "wlabel" in risk:
        parts.append(risk["wlabel"])
    if "precip_prob" in risk:
        parts.append(f"pluie {risk['precip_prob']}%")
    if "precip_mm" in risk and risk["precip_mm"] > 0:
        parts.append(f"{risk['precip_mm']}mm")
    if "cloud_pct" in risk:
        parts.append(f"nuages {risk['cloud_pct']}%")
    if "sun_h" in risk:
        parts.append(f"soleil {risk['sun_h']}h")
    if "wind_kmh" in risk:
        parts.append(f"vent {risk['wind_kmh']}km/h")
    if "gusts_kmh" in risk and risk["gusts_kmh"] > risk.get("wind_kmh", 0) + 10:
        parts.append(f"rafales {risk['gusts_kmh']}km/h")
    if "snow_mm" in risk and risk["snow_mm"] > 0:
        parts.append(f"neige {risk['snow_mm']}mm")
    return " | ".join(parts) if parts else "OK"


def validate_yes_trade(city_slug: str, question: str, slug: str) -> dict:
    """
    Vérifie si la prévision météo supporte un achat YES.

    Jour J  → regarde le max des heures restantes (heure locale) — marge 1°C
    Jour J+1 → regarde le max journalier — marge 3°C

    Retourne {'ok': bool, 'reason': str, 'forecast': float | None}
    """
    parsed = _parse_question(question)
    if not parsed:
        return {'ok': True, 'reason': 'Question non parseable — pas de veto', 'forecast': None}

    target_date = _parse_date_from_slug(slug)
    if not target_date:
        return {'ok': True, 'reason': 'Date non parseable — pas de veto', 'forecast': None}

    coords = _get_coords(city_slug)
    if not coords:
        return {'ok': True, 'reason': f'Ville inconnue ({city_slug}) — pas de veto', 'forecast': None}

    threshold = parsed['threshold']
    unit      = parsed['unit']
    sym       = '°F' if unit == 'fahrenheit' else '°C'
    lat, lon  = coords
    tz_name   = CITY_TZ.get(city_slug)

    # Détermine si le marché est pour aujourd'hui (heure locale de la ville)
    local_now  = None
    local_date = None
    local_hour = None
    if tz_name and ZoneInfo:
        try:
            local_now  = datetime.datetime.now(ZoneInfo(tz_name))
            local_date = local_now.date()
            local_hour = local_now.hour
        except Exception:
            pass

    is_today = (local_date is not None and target_date == local_date)

    try:
        if is_today:
            # Prévision heure par heure → max des heures restantes
            r = requests.get(OPEN_METEO_FORECAST, params={
                'latitude':         lat,
                'longitude':        lon,
                'hourly':           'temperature_2m',
                'temperature_unit': unit,
                'timezone':         tz_name,
                'start_date':       str(target_date),
                'end_date':         str(target_date),
            }, timeout=8)
            data  = r.json()
            times = data.get('hourly', {}).get('time', [])
            temps = data.get('hourly', {}).get('temperature_2m', [])
            if not temps:
                return {'ok': True, 'reason': 'Open-Meteo : aucune donnée horaire — pas de veto', 'forecast': None}

            # Filtre les heures restantes (≥ heure actuelle locale)
            remaining = [
                temps[i] for i, t in enumerate(times)
                if int(t.split('T')[1][:2]) >= local_hour
            ]
            if not remaining:
                return {'ok': True, 'reason': 'Plus d\'heures restantes aujourd\'hui — pas de veto', 'forecast': None}

            forecast = max(remaining)
            margin   = 1.8 if unit == 'fahrenheit' else 1.0

            if forecast < threshold - margin:
                return {
                    'ok':       False,
                    'forecast': forecast,
                    'reason':   (
                        f'{local_hour:02d}h00 heure locale — max restant {forecast:.1f}{sym} '
                        f'< seuil {threshold}{sym} (marge -{margin}{sym}) → NO probable'
                    ),
                }
            # Température OK — vérifier les risques météo (orage, pluie, neige…)
            risk = _fetch_daily_risk(lat, lon, target_date, unit, tz_name or "UTC")
            veto = _apply_risk_veto(risk, forecast, sym)
            if veto:
                return {'ok': False, 'forecast': forecast, 'reason': veto}
            return {
                'ok':       True,
                'forecast': forecast,
                'risk':     risk,
                'reason':   f'{local_hour:02d}h00 — max {forecast:.1f}{sym} ✓ | {_risk_summary(risk)}',
            }

        else:
            # Jour futur → max journalier
            r = requests.get(OPEN_METEO_FORECAST, params={
                'latitude':         lat,
                'longitude':        lon,
                'daily':            'temperature_2m_max',
                'temperature_unit': unit,
                'timezone':         'UTC',
                'start_date':       str(target_date),
                'end_date':         str(target_date),
            }, timeout=8)
            temps = r.json().get('daily', {}).get('temperature_2m_max', [])
            if not temps:
                return {'ok': True, 'reason': 'Open-Meteo : aucune donnée — pas de veto', 'forecast': None}

            forecast = float(temps[0])
            margin   = 5.4 if unit == 'fahrenheit' else 3.0

            if forecast < threshold - margin:
                return {
                    'ok':       False,
                    'forecast': forecast,
                    'reason':   (
                        f'Prévision J+1 {forecast:.1f}{sym} < seuil {threshold}{sym} '
                        f'(marge -{margin}{sym}) → NO probable'
                    ),
                }
            # Température OK — vérifier les risques météo (orage, pluie, neige…)
            risk = _fetch_daily_risk(lat, lon, target_date, unit, tz_name or "UTC")
            veto = _apply_risk_veto(risk, forecast, sym)
            if veto:
                return {'ok': False, 'forecast': forecast, 'reason': veto}
            return {
                'ok':       True,
                'forecast': forecast,
                'risk':     risk,
                'reason':   f'J+1 {forecast:.1f}{sym} ✓ | {_risk_summary(risk)}',
            }

    except Exception as e:
        return {'ok': True, 'reason': f'Open-Meteo erreur ({e}) — pas de veto', 'forecast': None}


# ── Météo enrichie : ensemble + multi-modèles + température actuelle ──────────

import time as _time

OPEN_METEO_ENSEMBLE = "https://ensemble-api.open-meteo.com/v1/ensemble"

_WX_CACHE: dict = {}
_WX_CACHE_TTL   = 1800  # 30 min — une seule requête par ville toutes les 30 min


def _wx_cache_get(key: tuple):
    entry = _WX_CACHE.get(key)
    if entry and _time.time() - entry[0] < _WX_CACHE_TTL:
        return entry[1]
    _WX_CACHE.pop(key, None)
    return None


def _wx_cache_set(key: tuple, data):
    _WX_CACHE[key] = (_time.time(), data)


def _fetch_single_model_max(lat, lon, model_id, target_date, unit, tz):
    """Prévision max journalière depuis un modèle météo donné."""
    try:
        r = requests.get(OPEN_METEO_FORECAST, params={
            "latitude": lat, "longitude": lon,
            "daily": "temperature_2m_max",
            "models": model_id,
            "temperature_unit": unit,
            "timezone": tz or "UTC",
            "start_date": str(target_date),
            "end_date":   str(target_date),
        }, timeout=6)
        if r.status_code == 200:
            vals = r.json().get("daily", {}).get("temperature_2m_max", [])
            if vals and vals[0] is not None:
                return float(vals[0])
    except Exception:
        pass
    return None


def _fetch_current_temp(lat, lon, unit):
    """Température observée en ce moment dans la ville."""
    try:
        r = requests.get(OPEN_METEO_FORECAST, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m",
            "temperature_unit": unit,
        }, timeout=5)
        if r.status_code == 200:
            val = r.json().get("current", {}).get("temperature_2m")
            return float(val) if val is not None else None
    except Exception:
        pass
    return None


def _fetch_ensemble_members(lat, lon, target_date, unit):
    """
    Retourne les températures max de chaque membre ECMWF IFS (≈51 membres).
    Utilisé pour calculer la probabilité que le seuil soit dépassé.
    """
    try:
        r = requests.get(OPEN_METEO_ENSEMBLE, params={
            "latitude": lat, "longitude": lon,
            "daily":    "temperature_2m_max",
            "models":   "ecmwf_ifs025",
            "temperature_unit": unit,
            "timezone": "UTC",
            "start_date": str(target_date),
            "end_date":   str(target_date),
        }, timeout=10)
        if r.status_code != 200:
            return []
        daily   = r.json().get("daily", {})
        times   = daily.get("time", [])
        day_idx = times.index(str(target_date)) if str(target_date) in times else 0
        members = []
        for key, vals in daily.items():
            if key == "time" or not vals:
                continue
            v = vals[day_idx] if day_idx < len(vals) else None
            if v is not None:
                try:
                    members.append(float(v))
                except (TypeError, ValueError):
                    pass
        return members if len(members) >= 5 else []
    except Exception:
        return []


def get_rich_weather_context(city_slug: str, question: str, slug: str) -> dict | None:
    """
    Contexte météo complet pour Claude :
      - current_temp      : température observée maintenant
      - ensemble_prob     : % de membres ECMWF qui prévoient de dépasser le seuil
      - ensemble_members_count : nombre de membres utilisés
      - models            : prévision max par modèle {ecmwf, gfs, icon, mf}
      - models_above      : nombre de modèles au-dessus du seuil
      - models_avg        : moyenne des modèles
      - models_spread     : écart max-min entre modèles (indicateur de confiance)

    Cache 30 min par (ville, date, unité) — la probabilité est recalculée
    par marché selon le seuil spécifique à chaque question.
    """
    parsed      = _parse_question(question)
    target_date = _parse_date_from_slug(slug)
    if not parsed or not target_date:
        return None

    coords = _get_coords(city_slug)
    if not coords:
        return None

    lat, lon  = coords
    threshold = parsed["threshold"]
    unit      = parsed["unit"]
    sym       = "°F" if unit == "fahrenheit" else "°C"
    tz_name   = CITY_TZ.get(city_slug, "UTC")

    cache_key = (city_slug, str(target_date), unit)
    raw       = _wx_cache_get(cache_key)

    if raw is None:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=7) as pool:
            f_current  = pool.submit(_fetch_current_temp,      lat, lon, unit)
            f_ensemble = pool.submit(_fetch_ensemble_members,  lat, lon, target_date, unit)
            f_ecmwf    = pool.submit(_fetch_single_model_max,  lat, lon, "ecmwf_ifs025",         target_date, unit, tz_name)
            f_gfs      = pool.submit(_fetch_single_model_max,  lat, lon, "gfs_global",           target_date, unit, tz_name)
            f_icon     = pool.submit(_fetch_single_model_max,  lat, lon, "icon_seamless",        target_date, unit, tz_name)
            f_mf       = pool.submit(_fetch_single_model_max,  lat, lon, "meteofrance_seamless", target_date, unit, tz_name)
            f_risk     = pool.submit(_fetch_daily_risk,        lat, lon, target_date, unit, tz_name)

        models = {}
        for name, fut in [("ecmwf", f_ecmwf), ("gfs", f_gfs), ("icon", f_icon), ("mf", f_mf)]:
            val = fut.result()
            if val is not None:
                models[name] = val

        raw = {
            "current_temp":     f_current.result(),
            "ensemble_members": f_ensemble.result(),
            "models":           models,
            "risk":             f_risk.result(),
        }
        _wx_cache_set(cache_key, raw)

    # Calculs spécifiques au seuil (hors cache — chaque marché a son propre seuil)
    result: dict = {"threshold": threshold, "sym": sym}

    if raw["current_temp"] is not None:
        result["current_temp"] = raw["current_temp"]

    members = raw["ensemble_members"]
    if members:
        above = sum(1 for t in members if t > threshold)
        result["ensemble_prob"]          = round(above / len(members) * 100)
        result["ensemble_members_count"] = len(members)

    models = raw["models"]
    if models:
        above_m                = sum(1 for v in models.values() if v > threshold)
        result["models"]       = models
        result["models_above"] = above_m
        result["models_total"] = len(models)
        result["models_avg"]   = round(sum(models.values()) / len(models), 1)
        if len(models) > 1:
            result["models_spread"] = round(max(models.values()) - min(models.values()), 1)

    # Inclure les facteurs de risque dans le contexte enrichi
    risk = raw.get("risk", {})
    if risk:
        result["risk"] = risk
        if "wlabel" in risk:
            result["weather_label"] = risk["wlabel"]

    return result if len(result) > 2 else None
