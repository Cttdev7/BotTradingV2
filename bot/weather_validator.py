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

# Stations METAR (codes ICAO) utilisées par Polymarket/Weather Underground pour résoudre les marchés
# Source : URL WU type wunderground.com/history/daily/{pays}/{ville}/{CODE}
CITY_METAR_STATIONS = {
    # Europe
    'ankara':        'LTAC',   # Esenboğa Airport (confirmé par user)
    'istanbul':      'LTFM',   # Istanbul Airport
    'london':        'EGLL',   # Heathrow
    'paris':         'LFPG',   # CDG
    'madrid':        'LEMD',   # Barajas
    'amsterdam':     'EHAM',   # Schiphol
    'warsaw':        'EPWA',   # Chopin Airport
    'milan':         'LIML',   # Linate
    'munich':        'EDDM',   # Franz Josef Strauss
    'helsinki':      'EFHK',   # Helsinki-Vantaa
    'moscow':        'UUWW',   # Vnukovo
    'tel-aviv':      'LLBG',   # Ben Gurion
    # USA
    'nyc':           'KJFK',   # JFK
    'atlanta':       'KATL',   # Hartsfield-Jackson
    'chicago':       'KORD',   # O'Hare
    'houston':       'KHOU',   # Hobby
    'dallas':        'KDFW',   # DFW
    'denver':        'KDEN',   # Denver International
    'miami':         'KMIA',   # Miami International
    'seattle':       'KSEA',   # Seattle-Tacoma
    'san-francisco': 'KSFO',   # SFO
    'los-angeles':   'KLAX',   # LAX
    # Asie/Pacifique
    'tokyo':         'RJTT',   # Haneda
    'seoul':         'RKSS',   # Gimpo
    'busan':         'RKPK',   # Gimhae
    'beijing':       'ZBAA',   # Capital Airport
    'shanghai':      'ZSPD',   # Pudong
    'hong-kong':     'VHHH',   # HK International
    'singapore':     'WSSS',   # Changi
    'taipei':        'RCTP',   # Taoyuan
    'kuala-lumpur':  'WMKK',   # KLIA
    'manila':        'RPLL',   # Ninoy Aquino
    # Autres
    'cape-town':     'FACT',   # Cape Town International
    'jeddah':        'OEJN',   # King Abdulaziz
    'karachi':       'OPKC',   # Jinnah International
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
            # Prévision heure par heure → trajectoire complète de la journée
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

            # Heures passées vs restantes
            past      = [temps[i] for i, t in enumerate(times) if int(t.split('T')[1][:2]) < local_hour]
            remaining = [temps[i] for i, t in enumerate(times) if int(t.split('T')[1][:2]) >= local_hour]

            if not remaining:
                return {'ok': True, 'reason': 'Plus d\'heures restantes aujourd\'hui — pas de veto', 'forecast': None}

            # Max observé aujourd'hui (heures passées) + max prévu (heures restantes)
            max_observed = max(past)  if past      else None
            forecast     = max(remaining)

            # Veto si le max déjà observé dépasse la borne haute de la fourchette (+0.5°C marge)
            band_width = 2.0 if unit == 'fahrenheit' else 1.0
            if max_observed is not None and max_observed >= threshold + band_width + 0.5:
                return {
                    'ok':     False,
                    'forecast': max_observed,
                    'reason': (
                        f'Max déjà observé {max_observed:.1f}{sym} dépasse la borne haute '
                        f'{threshold + band_width:.0f}{sym} — fourchette {threshold:.0f}{sym} impossible'
                    ),
                }

            # Tendance : les 3 dernières heures observées
            trend_str = ""
            if len(past) >= 3:
                last3 = past[-3:]
                if last3[-1] > last3[0] + 0.5:
                    trend_str = f"↗️ monte ({last3[0]:.1f}→{last3[-1]:.1f}{sym})"
                elif last3[-1] < last3[0] - 0.5:
                    trend_str = f"↘️ descend ({last3[0]:.1f}→{last3[-1]:.1f}{sym})"
                else:
                    trend_str = f"→ stable ({last3[-1]:.1f}{sym})"

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
            obs_str = f" | max observé {max_observed:.1f}{sym}" if max_observed else ""
            return {
                'ok':       True,
                'forecast': forecast,
                'risk':     risk,
                'max_observed': max_observed,
                'trend':    trend_str,
                'reason':   f'{local_hour:02d}h00 — {trend_str}{obs_str} | max restant {forecast:.1f}{sym} ✓ | {_risk_summary(risk)}',
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
OPEN_METEO_ARCHIVE  = "https://archive-api.open-meteo.com/v1/archive"

_WX_CACHE: dict = {}
_WX_CACHE_TTL   = 1800   # 30 min — données météo actuelles
_HIST_CACHE: dict = {}
_HIST_CACHE_TTL = 86400  # 24h — données historiques (ne changent pas dans la journée)


def _wx_cache_get(key: tuple):
    entry = _WX_CACHE.get(key)
    if entry and _time.time() - entry[0] < _WX_CACHE_TTL:
        return entry[1]
    _WX_CACHE.pop(key, None)
    return None


def _wx_cache_set(key: tuple, data):
    _WX_CACHE[key] = (_time.time(), data)


def _hist_cache_get(key: tuple):
    entry = _HIST_CACHE.get(key)
    if entry and _time.time() - entry[0] < _HIST_CACHE_TTL:
        return entry[1]
    _HIST_CACHE.pop(key, None)
    return None


def _hist_cache_set(key: tuple, data):
    _HIST_CACHE[key] = (_time.time(), data)


def _fetch_historical_maxes(lat, lon, unit, month, day, year_offset, window=3):
    """
    Récupère les maxima journaliers historiques pour ±window jours
    autour du même mois/jour il y a year_offset ans.
    """
    try:
        import datetime as _dt
        current_year = _dt.date.today().year
        year  = current_year - year_offset
        try:
            center = _dt.date(year, month, day)
        except ValueError:
            return []  # 29 fév en année non bissextile
        start = center - _dt.timedelta(days=window)
        end   = center + _dt.timedelta(days=window)
        r = requests.get(OPEN_METEO_ARCHIVE, params={
            "latitude": lat, "longitude": lon,
            "daily": "temperature_2m_max",
            "temperature_unit": unit,
            "timezone": "UTC",
            "start_date": str(start),
            "end_date":   str(end),
        }, timeout=8)
        if r.status_code == 200:
            vals = r.json().get("daily", {}).get("temperature_2m_max", [])
            return [float(v) for v in vals if v is not None]
    except Exception:
        pass
    return []


def get_historical_range_prob(lat, lon, unit, target_date, range_low, range_high, years=7):
    """
    Probabilité historique que le max journalier tombe dans [range_low, range_high].
    Utilise ±3 jours × 7 années → ~49 points historiques.
    Cache 24h par (lat, lon, unit, mois, jour).

    Retourne dict avec :
      hist_yes_freq   : % des années où le max était dans la fourchette
      hist_no_freq    : 100 - hist_yes_freq
      hist_avg        : moyenne historique du max journalier
      hist_samples    : nombre de points utilisés
    """
    from concurrent.futures import ThreadPoolExecutor

    cache_key = (round(lat, 2), round(lon, 2), unit, target_date.month, target_date.day)
    cached = _hist_cache_get(cache_key)
    if cached is not None:
        all_maxes = cached
    else:
        with ThreadPoolExecutor(max_workers=years) as pool:
            results = list(pool.map(
                lambda offset: _fetch_historical_maxes(lat, lon, unit, target_date.month, target_date.day, offset),
                range(1, years + 1)
            ))
        all_maxes = [v for year_data in results for v in year_data]
        if all_maxes:
            _hist_cache_set(cache_key, all_maxes)

    if len(all_maxes) < 10:
        return None

    in_range = sum(1 for v in all_maxes if range_low <= v <= range_high)
    hist_yes  = round(in_range / len(all_maxes) * 100)

    return {
        "hist_yes_freq": hist_yes,
        "hist_no_freq":  100 - hist_yes,
        "hist_avg":      round(sum(all_maxes) / len(all_maxes), 1),
        "hist_samples":  len(all_maxes),
    }


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


def _fetch_current_temp(lat, lon, unit, tz_name: str = "UTC"):
    """Température actuelle + max observé + max restant + tendance 3h (heure locale ville)."""
    try:
        import datetime as _dt
        tz   = ZoneInfo(tz_name) if ZoneInfo and tz_name else None
        now  = _dt.datetime.now(tz) if tz else _dt.datetime.utcnow()
        today = now.date().isoformat()
        now_hour = now.hour

        r = requests.get(OPEN_METEO_FORECAST, params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m",
            "hourly": "temperature_2m",
            "temperature_unit": unit,
            "timezone": tz_name or "UTC",
            "start_date": today,
            "end_date":   today,
        }, timeout=6)
        if r.status_code != 200:
            return None
        data        = r.json()
        current_val = data.get("current", {}).get("temperature_2m")
        current     = float(current_val) if current_val is not None else None

        times = data.get("hourly", {}).get("time", [])
        temps = data.get("hourly", {}).get("temperature_2m", [])

        # Heures passées (heure locale ville) vs restantes
        past      = [temps[i] for i, t in enumerate(times)
                     if temps[i] is not None and int(t.split('T')[1][:2]) <= now_hour]
        remaining = [temps[i] for i, t in enumerate(times)
                     if temps[i] is not None and int(t.split('T')[1][:2]) > now_hour]

        result = {"current": current}
        if past:
            result["max_today"] = round(max(past), 1)
            if len(past) >= 3:
                last3 = past[-3:]
                delta = last3[-1] - last3[0]
                if delta > 0.5:
                    result["trend"] = f"↗️ +{delta:.1f}°"
                elif delta < -0.5:
                    result["trend"] = f"↘️ {delta:.1f}°"
                else:
                    result["trend"] = "→ stable"
        if remaining:
            result["remaining_max"] = round(max(remaining), 1)
        result["local_hour"] = now_hour
        return result
    except Exception:
        return None


def _fetch_metar_temp(city_slug: str) -> dict | None:
    """
    Température actuelle depuis la station METAR (ICAO) que Polymarket utilise pour résoudre.
    API NOAA aviationweather.gov — gratuite, sans limite de taux.
    Retourne {temp_c, temp_f, station, raw_metar} ou None.
    """
    station = CITY_METAR_STATIONS.get(city_slug)
    if not station:
        return None
    try:
        r = requests.get(
            "https://aviationweather.gov/api/data/metar",
            params={"ids": station, "format": "json"},
            timeout=6,
        )
        if r.status_code != 200 or not r.json():
            return None
        d = r.json()[0]
        temp_c = d.get("temp")
        if temp_c is None:
            return None
        temp_f = round(temp_c * 9 / 5 + 32, 1)
        return {
            "temp_c":    round(float(temp_c), 1),
            "temp_f":    temp_f,
            "station":   station,
            "raw_metar": d.get("rawOb", "")[:80],
        }
    except Exception:
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
        with ThreadPoolExecutor(max_workers=8) as pool:
            f_current  = pool.submit(_fetch_current_temp,      lat, lon, unit, tz_name)
            f_metar    = pool.submit(_fetch_metar_temp,        city_slug)
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

        curr_data  = f_current.result() or {}
        metar_data = f_metar.result()

        # Température actuelle : préférer METAR (station exacte Polymarket) sur Open-Meteo
        if metar_data:
            current_temp = metar_data["temp_f"] if unit == "fahrenheit" else metar_data["temp_c"]
        else:
            current_temp = curr_data.get("current") if isinstance(curr_data, dict) else curr_data

        raw = {
            "current_temp":     current_temp,
            "max_today":        curr_data.get("max_today") if isinstance(curr_data, dict) else None,
            "remaining_max":    curr_data.get("remaining_max") if isinstance(curr_data, dict) else None,
            "trend":            curr_data.get("trend") if isinstance(curr_data, dict) else None,
            "local_hour":       curr_data.get("local_hour") if isinstance(curr_data, dict) else None,
            "metar":            metar_data,   # station ICAO exacte + temp brute
            "ensemble_members": f_ensemble.result(),
            "models":           models,
            "risk":             f_risk.result(),
        }
        _wx_cache_set(cache_key, raw)

    # Calculs spécifiques au seuil (hors cache — chaque marché a son propre seuil)
    result: dict = {"threshold": threshold, "sym": sym}

    if raw["current_temp"] is not None:
        result["current_temp"] = raw["current_temp"]
    if raw.get("max_today") is not None:
        result["max_today"] = raw["max_today"]
    if raw.get("remaining_max") is not None:
        result["remaining_max"] = raw["remaining_max"]
    if raw.get("trend"):
        result["trend"] = raw["trend"]
    if raw.get("local_hour") is not None:
        result["local_hour"] = raw["local_hour"]

    members = raw["ensemble_members"]
    if members:
        # Largeur de la fourchette Polymarket : 1°C ou 2°F
        band_width = 2.0 if unit == "fahrenheit" else 1.0
        upper      = threshold + band_width

        above_lower = sum(1 for t in members if t >= threshold)
        above_upper = sum(1 for t in members if t >= upper)
        in_band     = above_lower - above_upper  # membres dans [threshold, upper)

        result["ensemble_prob"]          = round(above_lower / len(members) * 100)
        result["band_prob"]              = round(in_band / len(members) * 100)
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

    # Probabilité historique pour la fourchette exacte de ce marché
    # Fourchette Polymarket : [threshold, threshold + band_width]
    band_width = 2.0 if unit == "fahrenheit" else 1.0
    hist = get_historical_range_prob(
        lat, lon, unit, target_date,
        range_low=threshold,
        range_high=threshold + band_width,
    )
    if hist:
        result["hist_yes_freq"]  = hist["hist_yes_freq"]
        result["hist_no_freq"]   = hist["hist_no_freq"]
        result["hist_avg"]       = hist["hist_avg"]
        result["hist_samples"]   = hist["hist_samples"]

    return result if len(result) > 2 else None
