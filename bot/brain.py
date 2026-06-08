"""
brain.py — Cerveau IA du bot (Claude API)

Reçoit : stratégie + marchés disponibles + historique des trades
Retourne : liste de décisions (acheter/vendre/ignorer)

La clé ANTHROPIC_API_KEY doit être dans .env.
"""

import json
import os
import requests
import anthropic
import config

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

    # 2. Performance par ville (taux de réussite des signaux passés)
    stats_lines = []
    for ville in _WEATHER_VILLES:
        try:
            r = requests.get(
                f"{base}/{ville}_stats",
                params={"limit": "1"},
                headers=headers, timeout=3,
            )
            if r.status_code == 200 and r.json():
                s = r.json()[0]
                resolus = int(s.get("resolus") or 0)
                gagnes  = int(s.get("gagnes") or 0)
                taux    = s.get("taux_victoire")
                if resolus > 0:
                    stats_lines.append(
                        f"  {ville}: {taux}% victoire ({gagnes}/{resolus} résolus)"
                    )
        except Exception:
            pass
    if stats_lines:
        sections.append(
            "=== PERFORMANCE DES BOTS D'ANALYSE PAR VILLE ===\n"
            + "\n".join(stats_lines)
        )

    # 3. Signaux actifs non résolus = opportunités identifiées maintenant
    signal_lines = []
    for ville in _WEATHER_VILLES:
        try:
            r = requests.get(
                f"{base}/{ville}_tracking",
                params={"resultat": "is.null", "limit": "5", "order": "detecte_le.desc"},
                headers=headers, timeout=3,
            )
            if r.status_code == 200:
                for sig in r.json():
                    price = float(sig.get("yes_price_au_signal") or sig.get("yes_price_actuel") or 0)
                    price_pct = price if price > 1 else price * 100
                    signal_lines.append(
                        f"  [{ville}] {(sig.get('question') or '')[:70]}"
                        f" → YES {price_pct:.0f}%"
                        f" | détecté {(sig.get('detecte_le') or '')[:10]}"
                    )
        except Exception:
            pass
    if signal_lines:
        sections.append(
            "=== SIGNAUX ACTIFS DES BOTS D'ANALYSE (opportunités non résolues) ===\n"
            + "\n".join(signal_lines[:20])
        )

    return "\n\n".join(sections) if sections else "Aucune donnée d'analyse disponible."


def _format_markets(markets: list) -> str:
    """Formate les marchés pour le prompt Claude."""
    if not markets:
        return "Aucun marché disponible."
    lines = []
    for m in markets[:30]:  # max 30 marchés pour ne pas saturer le contexte
        tokens = m.get("tokens", [])
        yes_price = next((t.get("price", "?") for t in tokens if t.get("outcome") == "Yes"), "?")
        no_price  = next((t.get("price", "?") for t in tokens if t.get("outcome") == "No"),  "?")
        volume = m.get("volume", 0)
        lines.append(
            f"- [{m.get('condition_id','?')[:12]}] {m.get('question','?')[:80]}\n"
            f"  YES={yes_price} | NO={no_price} | Volume=${float(volume or 0):,.0f}"
        )
    return "\n".join(lines)


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

    system_prompt = """Tu es ProfitWeather, un bot de trading spécialisé sur les marchés météo Polymarket.
Tu trades UNIQUEMENT les marchés "highest temperature in {ville}" sur les 12 villes suivies par les bots d'analyse.

Tu as accès :
1. Aux données des bots d'analyse météo (signaux actifs + taux de réussite par ville)
2. À la dernière analyse stratégique Mistral cross-ville
3. À l'historique de tes trades passés

Logique de décision :
- Un signal actif d'un bot d'analyse (YES >75%) EST une opportunité à étudier
- Croise le signal avec le marché disponible : est-ce que le prix actuel est cohérent avec le signal ?
- Favorise les villes avec un bon taux de réussite historique (>60%)
- Suis la stratégie fournie pour calibrer taille et critères d'entrée

Règles absolues :
- Ne jamais miser plus de 20% du solde sur un seul marché
- Ne jamais miser sur un marché avec volume < 500 USDC
- Si aucun signal ne correspond à un marché disponible, retourner []
- Toujours justifier en une phrase pourquoi le signal + marché sont alignés

Tu réponds UNIQUEMENT en JSON valide :
[
  {
    "action": "buy",
    "condition_id": "identifiant_du_marche",
    "outcome": "Yes",
    "amount_usdc": 25.0,
    "reason": "raison courte (ville, signal bot, alignement prix)"
  }
]"""

    analysis_ctx = _load_analysis_context()

    user_message = f"""STRATÉGIE :
{prompt_text}

SOLDE DISPONIBLE : ${balance_usdc:.2f} USDC

DONNÉES DES BOTS D'ANALYSE MÉTÉO (signaux actifs, performance par ville, analyse Mistral) :
{analysis_ctx}

MARCHÉS MÉTÉO DISPONIBLES :
{_format_markets(markets)}

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
    return [d for d in decisions if d.get("action") in ("buy", "sell")]


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
    Vérifie si les marchés sur lesquels on a parié ont résolu,
    et met à jour le P&L de chaque trade.
    Retourne la liste avec P&L mis à jour.
    """
    import polymarket as _pm
    updated = []
    for t in trades:
        if t.get("pnl") is not None:
            updated.append(t)
            continue
        cid = t.get("condition_id")
        if not cid:
            updated.append(t)
            continue
        try:
            market = _pm.get_market(cid)
            tokens = market.get("tokens", [])
            outcome = t.get("sym", "")
            for tok in tokens:
                if tok.get("outcome", "").lower() == outcome.lower():
                    price = float(tok.get("price", -1))
                    if price <= 0.01 or price >= 0.99:  # marché résolu
                        qty   = float(t.get("qty", t.get("amount_usdc", 0)))
                        entry = float(t.get("price", 0.5))
                        if t.get("side") == "buy":
                            t["pnl"] = round((price - entry) * qty, 2)
                        else:
                            t["pnl"] = round((entry - price) * qty, 2)
        except Exception:
            pass
        updated.append(t)
    return updated
