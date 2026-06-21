"""
postmortem.py — Analyse automatique des trades perdus

Quand un trade est perdu (SL ou résolution YES), ce module :
1. Récupère la température réelle via Open-Meteo historique
2. Compare avec la prévision au moment du trade
3. Analyse pourquoi le trade a échoué (heure locale, météo, gap)
4. Génère un rapport stocké dans Supabase (table trade_postmortems)
"""

from __future__ import annotations
import os
import re
import json
import datetime
import requests

SB_URL = os.getenv("SUPABASE_URL", "https://obqkqhlqlowxrxbyvktl.supabase.co")
SB_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")

LOG_FILE = os.path.join(os.path.dirname(__file__), "postmortems.log")

# Coordonnées GPS des villes
CITY_COORDS = {
    "paris":         (48.8566,  2.3522,  "Europe/Paris"),
    "london":        (51.5074, -0.1278,  "Europe/London"),
    "amsterdam":     (52.3676,  4.9041,  "Europe/Amsterdam"),
    "madrid":        (40.4168, -3.7038,  "Europe/Madrid"),
    "istanbul":      (41.0082, 28.9784,  "Europe/Istanbul"),
    "ankara":        (39.9334, 32.8597,  "Europe/Istanbul"),
    "moscow":        (55.7558, 37.6173,  "Europe/Moscow"),
    "warsaw":        (52.2297, 21.0122,  "Europe/Warsaw"),
    "milan":         (45.4654,  9.1859,  "Europe/Rome"),
    "munich":        (48.1351, 11.5820,  "Europe/Berlin"),
    "helsinki":      (60.1699, 24.9384,  "Europe/Helsinki"),
    "tel-aviv":      (32.0853, 34.7818,  "Asia/Jerusalem"),
    "istanbul":      (41.0082, 28.9784,  "Europe/Istanbul"),
    "nyc":           (40.7128, -74.0060, "America/New_York"),
    "new-york":      (40.7128, -74.0060, "America/New_York"),
    "atlanta":       (33.7490, -84.3880, "America/New_York"),
    "chicago":       (41.8781, -87.6298, "America/Chicago"),
    "houston":       (29.7604, -95.3698, "America/Chicago"),
    "dallas":        (32.7767, -96.7970, "America/Chicago"),
    "denver":        (39.7392,-104.9903, "America/Denver"),
    "seattle":       (47.6062,-122.3321, "America/Los_Angeles"),
    "san-francisco": (37.7749,-122.4194, "America/Los_Angeles"),
    "los-angeles":   (34.0522,-118.2437, "America/Los_Angeles"),
    "miami":         (25.7617, -80.1918, "America/New_York"),
    "toronto":       (43.6532, -79.3832, "America/Toronto"),
    "mexico-city":   (19.4326, -99.1332, "America/Mexico_City"),
    "tokyo":         (35.6762, 139.6503, "Asia/Tokyo"),
    "seoul":         (37.5665, 126.9780, "Asia/Seoul"),
    "busan":         (35.1796, 129.0756, "Asia/Seoul"),
    "beijing":       (39.9042, 116.4074, "Asia/Shanghai"),
    "shanghai":      (31.2304, 121.4737, "Asia/Shanghai"),
    "chengdu":       (30.5728, 104.0668, "Asia/Shanghai"),
    "guangzhou":     (23.1291, 113.2644, "Asia/Shanghai"),
    "shenzhen":      (22.5431, 114.0579, "Asia/Shanghai"),
    "chongqing":     (29.5630, 106.5516, "Asia/Shanghai"),
    "wuhan":         (30.5928, 114.3055, "Asia/Shanghai"),
    "taipei":        (25.0330, 121.5654, "Asia/Taipei"),
    "hong-kong":     (22.3193, 114.1694, "Asia/Hong_Kong"),
    "singapore":     (1.3521,  103.8198, "Asia/Singapore"),
    "kuala-lumpur":  (3.1390,  101.6869, "Asia/Kuala_Lumpur"),
    "manila":        (14.5995, 120.9842, "Asia/Manila"),
    "jakarta":       (-6.2088, 106.8456, "Asia/Jakarta"),
    "wellington":    (-41.2866, 174.7756,"Pacific/Auckland"),
    "cape-town":     (-33.9249,  18.4241,"Africa/Johannesburg"),
    "jeddah":        (21.4858,  39.1925, "Asia/Riyadh"),
    "karachi":       (24.8607,  67.0011, "Asia/Karachi"),
    "lucknow":       (26.8467,  80.9462, "Asia/Kolkata"),
    "qingdao":       (36.0671, 120.3826, "Asia/Shanghai"),
}


def _parse_range(question: str):
    """Extrait les bornes de la fourchette depuis la question du marché."""
    # Format °F : "72-73°F" ou "72 to 73"
    m = re.search(r'(\d+)[°\-\s]+(?:to\s+)?(\d+)\s*[°]?[FC]?', question)
    if m:
        return float(m.group(1)), float(m.group(2))
    # Format °C : "22°C" ou "22C"
    m = re.search(r'be\s+(\d+)[°\s]*[Cc]', question)
    if m:
        v = float(m.group(1))
        return v, v
    return None, None


def _get_actual_max_temp(city: str, date: str, unit: str = "auto") -> dict | None:
    """Récupère la température max réelle via Open-Meteo historique."""
    coords = CITY_COORDS.get(city.lower().replace("_", "-"))
    if not coords:
        return None
    lat, lon, tz = coords

    # Détecter l'unité depuis la ville (villes US = Fahrenheit)
    us_cities = {"nyc","new-york","atlanta","chicago","houston","dallas","denver",
                 "seattle","san-francisco","los-angeles","miami","toronto"}
    temp_unit = "fahrenheit" if city.lower() in us_cities else "celsius"

    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
            "latitude": lat, "longitude": lon,
            "start_date": date, "end_date": date,
            "daily": "temperature_2m_max,temperature_2m_min",
            "hourly": "temperature_2m",
            "temperature_unit": temp_unit,
            "timezone": tz,
        }, timeout=10)
        data = r.json()
        daily = data.get("daily", {})
        hourly = data.get("hourly", {})

        tmax = daily.get("temperature_2m_max", [None])[0]
        tmin = daily.get("temperature_2m_min", [None])[0]

        # Température heure par heure
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        hourly_data = [{"hour": t[11:16], "temp": v} for t, v in zip(times, temps)]

        return {
            "tmax": tmax,
            "tmin": tmin,
            "unit": "°F" if temp_unit == "fahrenheit" else "°C",
            "hourly": hourly_data,
        }
    except Exception as e:
        return {"error": str(e)}


def _save_postmortem(record: dict):
    """Sauvegarde dans Supabase table trade_postmortems."""
    try:
        requests.post(
            f"{SB_URL}/rest/v1/trade_postmortems",
            json=record,
            headers={
                "apikey": SB_KEY,
                "Authorization": f"Bearer {SB_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            timeout=10,
        )
    except Exception:
        pass


def analyze_loss(trade: dict, current_price: float, reason: str = "stop_loss"):
    """
    Analyse complète d'un trade perdu.
    trade    : dict complet du trade depuis Supabase
    current_price : prix NO au moment de la perte
    reason   : 'stop_loss' | 'resolution_yes'
    """
    city     = trade.get("city", "?")
    question = trade.get("question", "") or ""
    entry    = float(trade.get("price") or 0)
    amount   = float(trade.get("amount_usdc") or 0)
    trade_time = trade.get("time", "")
    cid      = trade.get("condition_id", "")

    # Si la question est absente, la récupérer depuis l'API Polymarket
    if not question and cid:
        try:
            r = requests.get(f"https://clob.polymarket.com/markets/{cid}", timeout=6)
            question = r.json().get("question", "") or ""
        except Exception:
            pass

    # Date du marché (résolution prévue)
    end_date = (trade.get("end_date") or trade_time)[:10]
    trade_date = trade_time[:10]

    # Heure locale au moment du trade
    coords = CITY_COORDS.get(city.lower().replace("_", "-"))
    local_hour_at_trade = "?"
    if coords and trade_time:
        try:
            from zoneinfo import ZoneInfo
            dt_utc = datetime.datetime.fromisoformat(trade_time.replace("Z", "+00:00"))
            dt_local = dt_utc.astimezone(ZoneInfo(coords[2]))
            local_hour_at_trade = dt_local.strftime("%H:%M heure locale")
        except Exception:
            pass

    # Fourchette du marché
    low, high = _parse_range(question)
    range_str = f"{low}-{high}" if low and high else "?"

    # Température réelle (historique)
    wx_real = _get_actual_max_temp(city, end_date)

    # Construire le rapport
    pnl = round((current_price - entry) / entry * amount, 2)
    loss_pct = round((current_price - entry) / entry * 100, 1)

    lines = [
        f"=== POST-MORTEM : {city.upper()} ===",
        f"Question      : {question}",
        f"Fourchette    : {range_str}",
        f"",
        f"TRADE",
        f"  Acheté le   : {trade_date} à {local_hour_at_trade}",
        f"  Prix entrée : {entry:.3f} NO",
        f"  Mise        : ${amount:.2f}",
        f"  Raison perte: {reason}",
        f"  Prix sortie : {current_price:.3f} ({loss_pct:+.1f}%)",
        f"  P&L         : ${pnl:.2f}",
    ]

    if wx_real and not wx_real.get("error"):
        unit = wx_real.get("unit", "°")
        tmax = wx_real.get("tmax")
        tmin = wx_real.get("tmin")
        lines += [
            f"",
            f"MÉTÉO RÉELLE ({end_date})",
            f"  Temp max     : {tmax}{unit}",
            f"  Temp min     : {tmin}{unit}",
        ]
        if low and tmax:
            gap_real = tmax - low
            verdict = "✅ La temp n'a PAS atteint la fourchette" if tmax < low else f"❌ La temp A atteint {tmax}{unit} — dans la fourchette {range_str}"
            lines.append(f"  Gap réel     : {gap_real:+.1f}{unit} vs borne basse")
            lines.append(f"  Verdict      : {verdict}")

        # Pic de température dans la journée
        hourly = wx_real.get("hourly", [])
        if hourly:
            peak = max(hourly, key=lambda x: x["temp"] or -999)
            lines.append(f"  Pic journée  : {peak['temp']}{unit} à {peak['hour']}")

    elif wx_real and wx_real.get("error"):
        lines.append(f"  (données météo indisponibles: {wx_real['error']})")

    # Diagnostic
    lines += [
        f"",
        f"DIAGNOSTIC",
    ]
    if reason == "stop_loss":
        lines.append(f"  Le prix NO a chuté de {entry:.3f} → {current_price:.3f}")
        lines.append(f"  → Le marché a convergé vers YES pendant le trade")
        if local_hour_at_trade != "?":
            lines.append(f"  → Trade acheté à {local_hour_at_trade} — {'trop tôt (avant 15h)' if 'avant' in local_hour_at_trade else 'horaire OK'}")
    elif reason == "resolution_yes":
        lines.append(f"  Marché résolu YES — la température a atteint la fourchette {range_str}")

    report = "\n".join(lines)

    # Sauvegarder dans le fichier local
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n" + "━" * 60 + "\n")
            f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n")
            f.write(report + "\n")
    except Exception:
        pass

    # Sauvegarder dans Supabase
    _save_postmortem({
        "trade_id": trade.get("id", ""),
        "city": city,
        "question": question,
        "range_low": low,
        "range_high": high,
        "entry_price": entry,
        "exit_price": current_price,
        "amount_usdc": amount,
        "pnl": pnl,
        "loss_pct": loss_pct,
        "reason": reason,
        "local_hour_at_trade": local_hour_at_trade,
        "trade_date": trade_date,
        "market_date": end_date,
        "actual_tmax": wx_real.get("tmax") if wx_real else None,
        "actual_tmin": wx_real.get("tmin") if wx_real else None,
        "report": report,
        "created_at": datetime.datetime.utcnow().isoformat(),
    })

    return report
