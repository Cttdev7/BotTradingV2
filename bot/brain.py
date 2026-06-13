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
            lines.append(f"\n[{city.upper()}]")
            current_city = city

        index_map[idx] = m.get("condition_id", "")
        lines.append(
            f"  [#{idx}] {m.get('question','?')[:75]}\n"
            f"    YES={yes_price:.2f} | NO={no_price:.2f} | Vol=${volume:,.0f}"
        )
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

MISSION : faire croître le portefeuille sur le long terme. Qualité > quantité.
2 bons trades valent mieux que 5 trades médiocres. Ne jamais trader si les conditions ne sont pas réunies.

Processus de décision :
1. Identifie les signaux actifs des bots d'analyse (YES ≥ 75%)
2. Filtre : uniquement les marchés dans la zone idéale (YES 0.76-0.87) ou acceptable (0.88-0.92 Tier 1 + win rate >65%)
3. Calcule la taille de position selon la confiance du signal :
   - Signal standard (YES 0.76-0.87, win rate ville >50%) : 15% du solde, minimum absolu 10 USDC
   - Signal fort (YES 0.76-0.84, ville Tier 1, win rate >65%, analyse Mistral positive) : 20% du solde, min 15 USDC
   - Signal exceptionnel (bots + Mistral convergent sur même ville, win rate >70%) : 25% du solde
4. Vérifie les limites de risque : max 3 positions ouvertes simultanément, max 55% du solde total engagé
5. Si les conditions ne sont pas réunies → retourner [] et attendre le prochain cycle

Règles non-négociables :
- INTERDIT si prix YES ≥ 0.94 : frais Polymarket > marge restante, perte garantie même si signal fort
- INTERDIT si YES < 0.76 : signal insuffisant
- MINIMUM ABSOLU 10 USDC par trade — pas de petites positions
- Volume minimum : 1 000 USDC sur le marché (liquidité suffisante)
- Ne pas re-trader un condition_id déjà en position ouverte
- Mieux vaut 0 trade ce cycle que 1 trade douteux
- Villes Tier 1 (win rate historique > 65%) : toronto, miami, houston, singapore, dubai, sydney, tokyo, seoul
- Si solde > 100 USDC : préférer 1-2 gros trades plutôt que 3 petits

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
