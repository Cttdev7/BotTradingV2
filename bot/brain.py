"""
brain.py — Cerveau IA du bot (Claude API)

Reçoit : stratégie + marchés disponibles + historique des trades
Retourne : liste de décisions (acheter/vendre/ignorer)

La clé ANTHROPIC_API_KEY doit être dans .env.
"""

from __future__ import annotations
import json
import os
import requests
import anthropic
import config
from concurrent.futures import ThreadPoolExecutor, as_completed

_client = None

def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY manquante dans .env")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


_WEATHER_VILLES = [
    "chengdu", "seoul", "hong_kong", "nyc", "london", "tokyo",
    "atlanta", "seattle", "miami", "singapore", "madrid", "shanghai",
    "los_angeles", "guangzhou", "mexico_city", "amsterdam",
    "paris", "toronto", "chicago", "denver", "houston",
    "taipei", "beijing", "san_francisco", "dallas",
    "wellington", "chongqing", "wuhan", "ankara", "moscow", "lucknow",
    "istanbul", "warsaw", "milan", "helsinki", "karachi", "cape_town",
    "jeddah", "shenzhen", "busan", "qingdao", "kuala_lumpur",
    "tel_aviv", "manila", "munich",
]

def _load_analysis_context() -> str:
    """
    Charge depuis Supabase les données des bots d'analyse météo :
    - Dernière analyse stratégique Mistral cross-ville
    - Performance (taux victoire) par ville
    - Signaux actifs non résolus = opportunités détectées
    """
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")
    if not supabase_url or not supabase_key:
        return "Données d'analyse non disponibles (SUPABASE_URL/KEY manquants)."

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }
    base = f"{supabase_url}/rest/v1"
    sections = []

    # 1. Dernière analyse stratégique Mistral cross-ville
    try:
        r = requests.get(
            f"{base}/strategie_analyses",
            params={"order": "created_at.desc", "limit": "1"},
            headers=headers, timeout=5,
        )
        if r.status_code == 200 and r.json():
            a = r.json()[0]
            sections.append(
                f"=== ANALYSE STRATÉGIQUE MISTRAL ({a.get('date', '?')}) ===\n"
                + (a.get("analyse_text") or "")[:600]
            )
    except Exception:
        pass

    # 2+3. Performance et signaux actifs par ville — requêtes parallèles
    def _fetch_ville(ville):
        stat_line   = None
        ville_sigs  = []
        try:
            r = requests.get(f"{base}/{ville}_stats", params={"limit": "1"}, headers=headers, timeout=3)
            if r.status_code == 200 and r.json():
                s      = r.json()[0]
                resolus = int(s.get("resolus") or 0)
                gagnes  = int(s.get("gagnes") or 0)
                taux    = s.get("taux_victoire")
                if resolus > 0:
                    stat_line = f"  {ville}: {taux}% victoire ({gagnes}/{resolus} résolus)"
        except Exception:
            pass
        try:
            r = requests.get(
                f"{base}/{ville}_tracking",
                params={"resultat": "is.null", "limit": "5", "order": "detecte_le.desc"},
                headers=headers, timeout=3,
            )
            if r.status_code == 200:
                for sig in r.json():
                    price     = float(sig.get("yes_price_actuel") or sig.get("yes_price_au_signal") or 0)
                    price_pct = price if price > 1 else price * 100
                    if price_pct < 75:  # seuil cohérent avec la stratégie
                        continue
                    ville_sigs.append(
                        f"  [{ville}] {(sig.get('question') or '')[:70]}"
                        f" → YES {price_pct:.0f}%"
                        f" | détecté {(sig.get('detecte_le') or '')[:10]}"
                    )
        except Exception:
            pass
        return ville, stat_line, ville_sigs

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(_fetch_ville, _WEATHER_VILLES))

    stats_lines  = [sl  for _, sl, _  in results if sl]
    signal_lines = [sig for _, _,  sv in results for sig in sv]

    if stats_lines:
        sections.append(
            "=== PERFORMANCE DES BOTS D'ANALYSE PAR VILLE ===\n"
            + "\n".join(stats_lines)
        )
    if signal_lines:
        sections.append(
            "=== SIGNAUX ACTIFS DES BOTS D'ANALYSE (opportunités non résolues) ===\n"
            + "\n".join(signal_lines[:20])
        )

    return "\n\n".join(sections) if sections else "Aucune donnée d'analyse disponible."


def _format_markets(markets: list) -> tuple:
    """
    Formate les marchés météo pour Claude.
    Retourne (texte, index_map) où index_map[N] = condition_id réel.
    Claude retourne un index numérique — jamais la chaîne hex brute.
    """
    if not markets:
        return "Aucun marché météo disponible.", {}

    def sort_key(m):
        tokens = m.get("tokens", [])
        yes = next((t.get("price", 0) for t in tokens if t.get("outcome") == "Yes"), 0)
        return -float(yes)

    sorted_markets = sorted(markets, key=sort_key)

    lines      = []
    index_map  = {}
    current_city = None
    idx        = 0

    for m in sorted_markets:
        if idx >= 60:
            break
        tokens    = m.get("tokens", [])
        yes_price = next((t.get("price", 0) for t in tokens if t.get("outcome") == "Yes"), 0)
        no_price  = next((t.get("price", 0) for t in tokens if t.get("outcome") == "No"),  0)
        volume    = float(m.get("volume") or 0)
        city      = m.get("city", "?")

        if city != current_city:
            local_hour = m.get("local_hour")
            hour_str   = f" — {local_hour:02d}h00 heure locale" if local_hour is not None else ""
            lines.append(f"\n[{city.upper()}{hour_str}]")
            current_city = city

        index_map[idx] = m.get("condition_id", "")
        market_line = (
            f"  [#{idx}] {m.get('question','?')[:75]}\n"
            f"    YES={yes_price:.2f} | NO={no_price:.2f} | Vol=${volume:,.0f}"
        )
        wx = m.get("weather_ctx")
        if wx:
            sym   = wx.get("sym", "°C")
            parts = []
            if "current_temp" in wx:
                trend = wx.get("trend", "")
                max_t = f" max_jour:{wx['max_today']:.1f}{sym}" if "max_today" in wx else ""
                parts.append(f"actuel:{wx['current_temp']:.1f}{sym}{max_t} {trend}".strip())
            if "ensemble_prob" in wx:
                n = wx.get("ensemble_members_count", "?")
                parts.append(f"prob:{wx['ensemble_prob']}%({n}mbr)")
            if "band_prob" in wx:
                bp = wx["band_prob"]
                flag = "⚠️" if bp < 40 else "✅"
                parts.append(f"{flag}fourchette:{bp}%")
            if wx.get("models"):
                avg    = wx.get("models_avg", "?")
                spread = wx.get("models_spread", "?")
                parts.append(
                    f"consensus:{wx['models_above']}/{wx['models_total']}ok"
                    f"·moy:{avg}{sym}·écart:{spread}{sym}"
                )
            if parts:
                market_line += "\n    🌤️ " + " | ".join(parts)
            # Facteurs de risque (pluie, vent, nuages, orage, neige, ensoleillement)
            risk = wx.get("risk", {})
            if risk:
                rparts = []
                if "wlabel" in risk:
                    rparts.append(risk["wlabel"])
                if "precip_prob" in risk:
                    emoji = "🌧️" if risk["precip_prob"] >= 60 else "🌦️" if risk["precip_prob"] >= 30 else "☀️"
                    rparts.append(f"{emoji}pluie {risk['precip_prob']}%")
                if risk.get("precip_mm", 0) > 0:
                    rparts.append(f"{risk['precip_mm']}mm")
                if "cloud_pct" in risk:
                    rparts.append(f"☁️{risk['cloud_pct']}%nuages")
                if "sun_h" in risk:
                    rparts.append(f"☀️{risk['sun_h']}h soleil")
                if "wind_kmh" in risk:
                    rparts.append(f"💨{risk['wind_kmh']}km/h")
                if risk.get("gusts_kmh", 0) > risk.get("wind_kmh", 0) + 10:
                    rparts.append(f"rafales {risk['gusts_kmh']}km/h")
                if risk.get("snow_mm", 0) > 0:
                    rparts.append(f"❄️neige {risk['snow_mm']}mm")
                if rparts:
                    market_line += "\n    🌡️ " + " | ".join(rparts)
        lines.append(market_line)
        idx += 1

    return "\n".join(lines), index_map


def _format_history(history: list) -> str:
    """Formate l'historique des trades pour que Claude apprenne."""
    if not history:
        return "Aucun trade passé."
    recent = history[-20:]  # 20 derniers trades
    lines = []
    for t in recent:
        outcome = "✅ gain" if (t.get("pnl") or 0) > 0 else ("❌ perte" if (t.get("pnl") or 0) < 0 else "⏳ ouvert")
        pnl_str = f" | P&L: ${t.get('pnl', 0):.2f}" if t.get("pnl") is not None else ""
        lines.append(
            f"- {t.get('side','?').upper()} {t.get('sym','?')} @ {t.get('price',0):.3f}"
            f" x{t.get('qty',0)} → {outcome}{pnl_str}"
        )
    return "\n".join(lines)


def decide(strategy: dict, markets: list, history: list, balance_usdc: float) -> list:
    """
    Appelle Claude pour décider quoi trader.

    Retourne une liste de décisions :
    [
      {
        "action": "buy" | "sell" | "skip",
        "condition_id": "0x...",
        "outcome": "Yes" | "No",
        "amount_usdc": 50.0,
        "reason": "explication courte"
      },
      ...
    ]
    """
    prompt_text = strategy.get("prompt", "").strip()
    if not prompt_text:
        return []

    system_prompt = """Tu es ProfitWeather, un bot de trading sur les marchés météo Polymarket.
Tu trades les marchés "highest temperature in {ville}" sur les 45 villes suivies par les bots d'analyse.

MISSION : préserver le capital d'abord, faire croître ensuite. 1 trade parfait vaut mieux que 5 trades passables.
En cas de doute → ne pas trader. Le prochain cycle arrive dans 15 min.

Processus de décision :
1. Identifie les signaux actifs des bots d'analyse (YES ≥ 80% minimum — plus de 75%)
2. Filtre strict : uniquement les marchés dans la zone idéale (YES 0.78-0.87) — plus de 0.88+ sauf exception rare
3. Calcule la taille de position selon la confiance :
   - Signal fort (YES 0.78-0.87, ville Tier 1, win rate >65%, Mistral positif) : 12% du solde, min 10 USDC
   - Signal exceptionnel (bots ≥85% + Mistral convergent + ville Tier 1 + après 16h) : 18% du solde
   - JAMAIS plus de 18% du solde sur un seul trade
4. Limite de risque : max 35% du solde total engagé simultanément (était 55%)
5. Si les conditions ne sont pas toutes réunies → retourner []

Heure locale de la ville (indiquée entre crochets) :
- Avant 16h00 : INTERDIT de trader sauf signal ≥ 85% + ville Tier 1 + win rate >70%
- Entre 16h00 et 20h00 : zone idéale — pic passé, température quasi-certaine → signal ≥ 80%
- Après 20h00 : marché quasi-résolu → signal ≥ 78% suffit mais position réduite (8% du solde)

Règles non-négociables :
- INTERDIT Jeddah : ville blacklistée définitivement
- INTERDIT si prix YES ≥ 0.92 : trop cher, marge trop faible
- INTERDIT si YES < 0.78 : signal insuffisant
- INTERDIT si win rate ville < 55% : historique pas assez solide
- MINIMUM ABSOLU 10 USDC par trade
- Volume minimum marché : 5 000 USDC
- Ne pas re-trader un condition_id déjà en position
- Si solde < 60 USDC : maximum 1 trade par cycle, 10% du solde

Classement des villes par fiabilité (basé sur l'analyse des marchés résolus Polymarket) :

✅ TIER 1 — Villes prioritaires (température stable, fourchette se dégage nettement) :
Seoul, Hong Kong, Tokyo, Shanghai, Chengdu, Singapore, Kuala Lumpur,
Taipei, Wuhan, Lucknow, Karachi, Busan, Shenzhen

✅ TIER 2 — Villes acceptables (bon historique, surveiller la fourchette) :
Miami, Houston, Dallas, San Francisco, Toronto, Madrid, Helsinki,
Cape Town, Tel Aviv, Munich, Beijing, Guangzhou

⚠️  TIER 3 — Villes à risque (météo variable, fourchettes concurrentes, signal moins fiable) :
London, Paris, Amsterdam, Milan, Warsaw, Moscow, Ankara, Istanbul,
Atlanta, Chicago, Denver, Seattle, NYC, Los Angeles, Mexico City

Règles par Tier :
- Tier 1 : signal ≥ 80%, toute heure après 14h local
- Tier 2 : signal ≥ 82%, uniquement après 16h local
- Tier 3 : signal ≥ 88% + band_prob ≥ 50% + après 18h local + win rate >65% — très rare

Interprétation des données météo 🌤️ (présentes sous chaque marché) :
- prob:X%(Nmbr)     = X% des N membres ECMWF prévoient de dépasser le seuil
- fourchette:X%     = X% des membres dans la fourchette EXACTE du marché ← le plus important
  → fourchette > 50% = signal fort | 35-50% = acceptable | < 35% = INTERDIT (trop incertain)
- consensus:N/4ok   = N des 4 modèles (ECMWF/GFS/ICON/MF) au-dessus du seuil
  → 4/4 = très fiable | 3/4 = bon | 2/4 ou moins = éviter
- écart:X°C         = dispersion entre modèles (< 1.5°C fiable, > 3°C incertain)
- actuel:X°C        = température observée maintenant
  → si actuel dans la fourchette ou juste en dessous → signal très fort

Tu réponds UNIQUEMENT en JSON valide, sans texte autour :
[
  {
    "action": "buy",
    "market_index": 3,
    "outcome": "Yes",
    "amount_usdc": 20.0,
    "yes_price": 0.82,
    "reason": "ville Tier1 win>65%, zone idéale 0.82, signal bot 79%, analyse Mistral positive"
  }
]
"market_index" est le numéro #N du marché dans la liste ci-dessous. Ne recopie jamais le condition_id hex.
Si aucun signal qualifié → retourner []"""

    analysis_ctx      = _load_analysis_context()
    markets_text, index_map = _format_markets(markets)

    user_message = f"""STRATÉGIE :
{prompt_text}

SOLDE DISPONIBLE : ${balance_usdc:.2f} USDC

DONNÉES DES BOTS D'ANALYSE MÉTÉO (signaux actifs, performance par ville, analyse Mistral) :
{analysis_ctx}

MARCHÉS MÉTÉO DISPONIBLES (utilise le numéro #N dans market_index) :
{markets_text}

HISTORIQUE DES TRADES (apprends de tes erreurs) :
{_format_history(history)}

Croise les signaux actifs des bots d'analyse avec les marchés disponibles et retourne tes décisions en JSON."""

    response = get_client().messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
    )

    if not response.content:
        return []
    raw = response.content[0].text.strip()

    # Extraire le JSON même si Claude ajoute du texte autour
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    if start == -1 or end == 0:
        return []

    try:
        decisions = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return []

    # Résout market_index → condition_id réel (évite que Claude recopie la chaîne hex)
    resolved = []
    for d in decisions:
        if d.get("action") != "buy":
            continue
        idx = d.get("market_index")
        if idx is None or idx not in index_map:
            continue
        d["condition_id"] = index_map[idx]
        resolved.append(d)
    return resolved


def reflect(strategy: dict, recent_trades: list) -> str:
    """Analyse les derniers trades et retourne un texte de suggestions."""
    if not recent_trades:
        return "Pas encore de trades à analyser."
    prompt_text = strategy.get("prompt", "").strip()
    message = f"""Voici la stratégie actuelle du bot :
{prompt_text}

Voici ses 20 derniers trades :
{_format_history(recent_trades)}

Analyse ces résultats en 3-5 phrases : ce qui a marché, ce qui a raté, comment améliorer."""

    response = get_client().messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": message}],
    )
    return response.content[0].text.strip() if response.content else ""


def improve_strategy(strategy: dict, history: list) -> dict:
    """
    Réécrit la stratégie en se basant sur l'historique des trades.
    Retourne {"new_prompt": str, "reason": str, "version": int}

    C'est la fonction d'auto-amélioration : le bot remet en question
    sa stratégie actuelle pour devenir meilleur à chaque cycle.
    """
    current_prompt = strategy.get("prompt", "").strip()
    version        = strategy.get("version", 1)

    if not current_prompt:
        return {"new_prompt": current_prompt, "reason": "Pas de stratégie initiale.", "version": version}

    wins   = [t for t in history if (t.get("pnl") or 0) > 0]
    losses = [t for t in history if (t.get("pnl") or 0) < 0]
    open_  = [t for t in history if t.get("pnl") is None]

    system = """Tu es un expert en marchés de prédiction Polymarket et en trading algorithmique.
Tu dois améliorer la stratégie d'un bot de trading en te basant sur ses résultats passés.

Ton objectif absolu : maximiser le taux de réussite et le P&L.
Sois impitoyable dans ton analyse — si quelque chose ne marche pas, coupe-le.
Si quelque chose marche, amplifie-le.

Réponds en JSON :
{
  "new_prompt": "nouvelle stratégie en 3-5 phrases, précise et actionnable",
  "reason": "explication courte de ce que tu as changé et pourquoi"
}"""

    analysis_ctx = _load_analysis_context()

    user = f"""STRATÉGIE ACTUELLE (version {version}) :
{current_prompt}

BILAN DES TRADES :
- Trades gagnants : {len(wins)}
- Trades perdants : {len(losses)}
- Trades ouverts  : {len(open_)}

HISTORIQUE DÉTAILLÉ (30 derniers) :
{_format_history(history[-30:])}

DONNÉES BOTS D'ANALYSE MÉTÉO (signaux, performance par ville, analyse Mistral) :
{analysis_ctx}

Réécris la stratégie en combinant :
1. Ce qui a marché/raté dans l'historique des trades
2. Les opportunités et patterns identifiés par Mistral
3. Les stratégies suggérées par Mistral

Sois précis sur : marchés à cibler, probabilités d'entrée, taille des positions, critères de sortie."""

    response = get_client().messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": user}],
        system=system,
    )

    if not response.content:
        return {"new_prompt": current_prompt, "reason": "Erreur API.", "version": version}

    raw = response.content[0].text.strip()
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    try:
        result = json.loads(raw[start:end]) if start != -1 else {}
    except json.JSONDecodeError:
        result = {}

    return {
        "new_prompt": result.get("new_prompt", current_prompt),
        "reason":     result.get("reason", "Amélioration automatique."),
        "version":    version + 1,
    }


def _format_markets_v2(markets: list) -> tuple:
    """
    Formate les marchés pour decide_v2 — trie par NO price DESC (meilleure opportunité NO d'abord).
    """
    if not markets:
        return "Aucun marché disponible.", {}

    import json as _json

    def sort_key(m):
        tokens = m.get("tokens", [])
        no = next((t.get("price", 0) for t in tokens if t.get("outcome") == "No"), 0)
        return -float(no)

    sorted_markets = sorted(markets, key=sort_key)
    lines = []
    index_map = {}
    current_city = None
    idx = 0

    for m in sorted_markets:
        if idx >= 60:
            break
        tokens    = m.get("tokens", [])
        yes_price = next((t.get("price", 0) for t in tokens if t.get("outcome") == "Yes"), 0)
        no_price  = next((t.get("price", 0) for t in tokens if t.get("outcome") == "No"),  0)
        if no_price < 0.60:
            idx += 1
            continue
        volume    = float(m.get("volume") or 0)
        city      = m.get("city", "?")

        if city != current_city:
            local_hour = m.get("local_hour")
            hour_str   = f" — {local_hour:02d}h00 locale" if local_hour is not None else ""
            lines.append(f"\n[{city.upper()}{hour_str}]")
            current_city = city

        index_map[idx] = m.get("condition_id", "")
        market_line = (
            f"  [#{idx}] {m.get('question','?')[:80]}\n"
            f"    NO={no_price:.2f} | YES={yes_price:.2f} | Vol=${volume:,.0f}"
        )
        wx = m.get("weather_ctx")
        if wx:
            sym   = wx.get("sym", "°C")
            parts = []
            # Trajectoire temps réel
            if "current_temp" in wx:
                cur   = wx["current_temp"]
                h_loc = wx.get("local_hour", "?")
                traj  = f" {wx['trend']}" if wx.get("trend") else ""
                max_o = f" max_observé:{wx['max_today']:.1f}{sym}" if "max_today" in wx else ""
                max_r = f" max_restant:{wx['remaining_max']:.1f}{sym}" if "remaining_max" in wx else ""
                parts.append(f"🌡️ {h_loc}h→{cur:.1f}{sym}{traj}{max_o}{max_r}")
            if "band_prob" in wx:
                bp   = wx["band_prob"]
                flag = "🎯" if bp < 15 else "✅" if bp < 30 else "⚠️"
                parts.append(f"{flag}fourchette:{bp}% (NO évident si <30%)")
            if wx.get("models"):
                avg    = wx.get("models_avg", "?")
                spread = wx.get("models_spread", "?")
                parts.append(f"moy:{avg}{sym}·écart:{spread}{sym}")
            if parts:
                market_line += "\n    🌤️ " + " | ".join(parts)
            # Historique : probabilité que cette fourchette soit atteinte sur les 7 dernières années
            if "hist_yes_freq" in wx:
                hy  = wx["hist_yes_freq"]
                hn  = wx["hist_no_freq"]
                avg = wx.get("hist_avg", "?")
                n   = wx.get("hist_samples", "?")
                flag = "✅" if hy <= 10 else "⚠️" if hy <= 20 else "🔴"
                market_line += (
                    f"\n    📊 HISTORIQUE 7 ans ({n} pts) : fourchette atteinte {hy}% du temps"
                    f" | NO {hn}% | moy historique {avg}{sym} {flag}"
                )
        if m.get("_no_confirmed"):
            market_line += "\n    ✅ NO CONFIRMÉ EN TEMPS RÉEL : max observé aujourd'hui dépasse déjà la fourchette haute"
        if m.get("_deko"):
            market_line += "\n    🔍 SIGNAL DEKO : sailor82 est NO sur ce marché (win rate 86%)"
        hours_left = m.get("_hours_left")
        if hours_left is not None:
            if hours_left <= 4:
                market_line += f"\n    ⏳ FERME DANS {hours_left:.1f}h — résolution imminente, risque très faible"
            else:
                market_line += f"\n    ⏳ {hours_left:.1f}h avant clôture"
        lines.append(market_line)
        idx += 1

    return "\n".join(lines), index_map


def decide_v2(strategy: dict, markets: list, history: list, balance_usdc: float) -> list:
    """
    ProfitWeather V2 : acheter NO sur marchés de fourchettes de température à 70–95 cents.
    Logique : si la météo prédit clairement hors de la fourchette → NO vaut presque 1.
    """
    prompt_text = strategy.get("prompt", "").strip()
    if not prompt_text:
        return []

    system_prompt = """Tu es ProfitWeather V2.0, un bot de trading sur Polymarket.

STRATÉGIE : acheter NO sur les marchés météo de fourchettes de température US quand :
  1. Le NO se trade à 70–95 cents (YES à 5–30 cents = température très improbable dans cette fourchette)
  2. La météo confirme que la température sera CLAIREMENT hors de la fourchette

LOGIQUE : les marchés Polymarket ont des fourchettes étroites (1-2°F). Si la prévision météo montre
une temp à 80°F et la fourchette est 66-67°F, le NO à 0.80 est une évidence — il faut y mettre de l'argent.

CRITÈRES D'ENTRÉE (tous obligatoires) :
- NO price : 0.70–0.95 (sinon trop cheap = trop risqué, ou trop cher = marge faible)
- fourchette: < 30% (peu de modèles ECMWF dans cette case → clairement hors range)
- Écart évident entre temp actuelle/max_jour et les bornes de la fourchette
- Volume minimum : 1 000 USDC

TAILLE DES POSITIONS (solde disponible : sera fourni) :
- Cas évident  (NO > 0.80, fourchette < 15%) : 25% du solde, min $20, max $1 400
- Cas clair    (NO > 0.70, fourchette < 30%) : 15% du solde, min $20, max $500
- JAMAIS plus de 40% du solde total engagé simultanément

VILLES PRÉFÉRÉES (US) : san-francisco, miami, nyc, houston, atlanta, los-angeles, seattle, chicago, dallas
Autres villes : acceptées si signal très évident (NO > 0.85, fourchette < 10%)

INTERPRÉTATION DES DONNÉES MÉTÉO :
- actuel:X°C/F   = température observée maintenant
- max_jour:Y°F   = max prévu pour aujourd'hui
- fourchette:Z%  = % des modèles ECMWF dans cette case exacte ← CLEF pour NO
  → < 15% = NO évident (🎯) | 15-30% = NO clair (✅) | > 30% = trop risqué, ignorer

NIVEAUX DE CERTITUDE (tu dois les évaluer pour chaque trade) :
- "high"   : band_prob < 10% ET écart prévision/fourchette > 10°F → cas évident
- "medium" : band_prob < 20% ET écart > 5°F → cas clair
- "low"    : band_prob < 30% ET écart > 3°F → cas acceptable

⚠️  Ne PAS inclure "amount_usdc" — la mise est calculée automatiquement selon le solde.
⚠️  Ne PAS jouer les ranges proches de la prévision (< 3°F d'écart) — c'est là que sailor82 a perdu $2 500.

Tu réponds UNIQUEMENT en JSON valide :
[
  {
    "action": "buy",
    "market_index": 3,
    "outcome": "No",
    "no_price": 0.82,
    "certainty": "high",
    "reason": "SF prévu 80°F, fourchette 66-67°F → 14°F d'écart, band_prob=5% → NO évident"
  }
]
Si aucun cas évident → retourner []"""

    markets_text, index_map = _format_markets_v2(markets)

    user_message = f"""STRATÉGIE :
{prompt_text}

SOLDE DISPONIBLE : ${balance_usdc:.2f} USDC

MARCHÉS MÉTÉO (triés par NO price décroissant) :
{markets_text}

HISTORIQUE DES 10 DERNIERS TRADES :
{_format_history(history[-10:])}

Identifie les cas où NO est évident (temp prévue clairement hors fourchette) et retourne tes décisions en JSON."""

    response = get_client().messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
    )

    if not response.content:
        return []
    raw = response.content[0].text.strip()

    start = raw.find("[")
    end   = raw.rfind("]") + 1
    if start == -1 or end == 0:
        return []

    try:
        decisions = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return []

    resolved = []
    for d in decisions:
        if d.get("action") != "buy":
            continue
        idx = d.get("market_index")
        if idx is None or idx not in index_map:
            continue
        d["condition_id"] = index_map[idx]
        d["outcome"] = "No"
        resolved.append(d)
    return resolved


def check_market_outcomes(trades: list) -> list:
    """
    Vérifie si les marchés ont résolu via le champ 'closed' de l'API Polymarket.
    Utilise /events pour le vrai prix final (évite le bug CLOB bloqué à 0.51).
    Fonctionne en simulation ET en mode réel.
    """
    import requests as _req

    GAMMA = "https://gamma-api.polymarket.com"

    def _get_final_price(cid: str, outcome: str):
        """Récupère le prix final depuis /events (plus fiable que le CLOB)."""
        try:
            r = _req.get(f"{GAMMA}/markets/{cid}", timeout=5)
            if r.status_code != 200:
                return None
            m = r.json()
            if not m.get("closed"):
                return None
            import json as _j
            prices   = m.get("outcomePrices", [])
            outcomes = m.get("outcomes", [])
            prices   = _j.loads(prices)   if isinstance(prices, str)   else prices
            outcomes = _j.loads(outcomes) if isinstance(outcomes, str) else outcomes
            for o, p in zip(outcomes, prices):
                if o.lower() == outcome.lower():
                    return float(p)
        except Exception:
            pass
        return None

    updated = []
    for t in trades:
        if t.get("pnl") is not None:
            updated.append(t)
            continue
        cid     = t.get("condition_id")
        outcome = t.get("sym", "Yes")
        if not cid:
            updated.append(t)
            continue
        try:
            final_price = _get_final_price(cid, outcome)
            if final_price is not None:
                amount = float(t.get("amount_usdc", 0))
                entry  = float(t.get("price", 0.5)) or 0.5
                shares = amount / entry
                t["pnl"] = round(shares * (final_price - entry), 2)
        except Exception:
            pass
        updated.append(t)
    return updated
