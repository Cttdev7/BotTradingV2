"""
weather_validator.py — Vérifie la prévision météo avant tout trade YES.

Avant d'acheter, on interroge Open-Meteo pour s'assurer que la prévision
de température est compatible avec le seuil du marché Polymarket.
"""
from __future__ import annotations
import re
import datetime
import requests

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

_MONTHS = {
    'january':1, 'february':2, 'march':3, 'april':4,
    'may':5, 'june':6, 'july':7, 'august':8,
    'september':9, 'october':10, 'november':11, 'december':12,
}


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
    Vérifie si la prévision Open-Meteo supporte un achat YES.

    Logique : si la prévision est inférieure au seuil du marché (moins 3°C de marge),
    la résolution YES est peu probable → trade bloqué.

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
    # Marge : 3°C ou 5.4°F — si prévision en dessous de (seuil - marge) → veto
    margin    = 5.4 if unit == 'fahrenheit' else 3.0

    try:
        r = requests.get(OPEN_METEO_FORECAST, params={
            'latitude':         coords[0],
            'longitude':        coords[1],
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
    except Exception as e:
        return {'ok': True, 'reason': f'Open-Meteo erreur ({e}) — pas de veto', 'forecast': None}

    if forecast < threshold - margin:
        return {
            'ok':       False,
            'forecast': forecast,
            'reason':   (
                f'Prévision {forecast:.1f}{sym} < seuil {threshold}{sym} '
                f'(marge -{margin}{sym}) → NO probable, trade bloqué'
            ),
        }

    return {
        'ok':       True,
        'forecast': forecast,
        'reason':   f'Prévision {forecast:.1f}{sym} ✓ seuil {threshold}{sym}',
    }
