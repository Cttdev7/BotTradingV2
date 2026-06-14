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
    m = re.search(r'be (\d+(?:\.\d+)?)\s*°([CF])\b', question, re.IGNORECASE)
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
            return {
                'ok':       True,
                'forecast': forecast,
                'reason':   f'{local_hour:02d}h00 heure locale — max restant {forecast:.1f}{sym} ✓ seuil {threshold}{sym}',
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
            return {
                'ok':       True,
                'forecast': forecast,
                'reason':   f'Prévision J+1 {forecast:.1f}{sym} ✓ seuil {threshold}{sym}',
            }

    except Exception as e:
        return {'ok': True, 'reason': f'Open-Meteo erreur ({e}) — pas de veto', 'forecast': None}
