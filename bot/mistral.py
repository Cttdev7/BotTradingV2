"""
mistral.py — Agent d'analyse Polymarket via Mistral AI

Analyse les marchés en temps réel et propose des opportunités de trading
et des suggestions de stratégie.

La clé MISTRAL_API_KEY doit être dans .env.
"""
from __future__ import annotations
import json
import os
import requests
import config

MISTRAL_API = "https://api.mistral.ai/v1/chat/completions"
MODEL       = "mistral-small-latest"
TIMEOUT     = 30

CATEGORIES = {
    "tout":      None,
    "politique": ["election", "president", "vote", "gouvernement", "parti", "candidat", "sénat", "congress"],
    "crypto":    ["bitcoin", "btc", "ethereum", "eth", "crypto", "token", "blockchain", "solana", "binance"],
    "finance":   ["fed", "taux", "inflation", "recession", "marché", "bourse", "dow", "nasdaq", "s&p"],
    "sport":     ["nba", "nfl", "football", "tennis", "champion", "coupe", "ligue", "match", "tournoi"],
    "météo":     ["weather", "temperature", "rain", "snow", "hurricane", "storm", "celsius", "fahrenheit",
                  "precipitation", "wind", "forecast", "climate", "heat", "cold", "flood", "drought",
                  "météo", "pluie", "neige", "tempête", "chaleur", "froid", "cyclone"],
}


def _api_key() -> str:
    key = os.getenv("MISTRAL_API_KEY", "")
    if not key:
        raise ValueError("MISTRAL_API_KEY manquante dans .env")
    return key


def _filter_markets(markets: list, category: str, min_volume: float) -> list:
    """Filtre et trie les marchés selon la catégorie et le volume."""
    filtered = []
    keywords = CATEGORIES.get(category)

    for m in markets:
        question = m.get("question", "").lower()
        volume   = float(m.get("volume", 0) or 0)

        if volume < min_volume:
            continue
        if keywords and not any(kw in question for kw in keywords):
            continue

        tokens   = m.get("tokens", [])
        yes_price = next((float(t.get("price", 0)) for t in tokens if t.get("outcome", "").lower() == "yes"), None)
        no_price  = next((float(t.get("price", 0)) for t in tokens if t.get("outcome", "").lower() == "no"),  None)

        if yes_price is None:
            continue

        filtered.append({
            "condition_id": m.get("condition_id", ""),
            "question":     m.get("question", ""),
            "yes_price":    yes_price,
            "no_price":     no_price or round(1 - yes_price, 3),
            "volume":       volume,
        })

    # Trie par volume décroissant, garde les 25 plus liquides
    filtered.sort(key=lambda x: x["volume"], reverse=True)
    return filtered[:25]


def _format_for_prompt(markets: list) -> str:
    lines = []
    for m in markets:
        lines.append(
            f"- {m['question'][:90]}\n"
            f"  YES={m['yes_price']:.2f} | NO={m['no_price']:.2f} | "
            f"Volume=${m['volume']:,.0f} | ID={m['condition_id'][:12]}"
        )
    return "\n".join(lines)


def analyse(markets: list, category: str = "tout", min_volume: float = 5000, instructions: str = "") -> dict:
    """
    Analyse les marchés avec Mistral et retourne opportunités + stratégie.

    Retourne :
    {
        "summary": str,
        "opportunities": [{ title, condition_id, recommendation, yes_price, confidence, reasoning }],
        "strategy_suggestion": str,
        "markets_analysed": int,
        "category": str
    }
    """
    filtered = _filter_markets(markets, category, min_volume)

    if not filtered:
        return {
            "summary": "Aucun marché ne correspond aux filtres sélectionnés.",
            "opportunities": [],
            "strategy_suggestion": "",
            "markets_analysed": 0,
            "category": category,
        }

    system = """Tu es un expert en marchés de prédiction Polymarket.
Analyse les marchés fournis et identifie les meilleures opportunités de trading.

Réponds UNIQUEMENT en JSON valide avec cette structure exacte :
{
  "summary": "Résumé en 2-3 phrases de la situation actuelle des marchés",
  "opportunities": [
    {
      "title": "Nom court du marché",
      "condition_id": "identifiant",
      "recommendation": "YES ou NO",
      "yes_price": 0.45,
      "confidence": "Élevée / Moyenne / Faible",
      "reasoning": "Explication courte du raisonnement (2-3 phrases max)"
    }
  ],
  "strategy_suggestion": "Texte de stratégie prêt à copier dans le bot (2-4 phrases)"
}

Identifie 3 à 5 opportunités maximum. Priorise les marchés où le prix semble mal calibré.
Ne retourne QUE du JSON, sans texte avant ou après."""

    extra = f"\n\nInstructions spécifiques de l'utilisateur : {instructions}" if instructions else ""
    user = f"""Marchés Polymarket disponibles (catégorie: {category}, volume min: ${min_volume:,.0f}) :

{_format_for_prompt(filtered)}

Analyse ces marchés et identifie les meilleures opportunités.

Pour chaque opportunité identifiée, indique également :
- Le pourcentage estimé de victoire si on mise quand le prix YES est supérieur à 85¢ (85%)
- Si miser à ce niveau est rentable ou non (en tenant compte de la faible marge restante){extra}"""

    resp = requests.post(
        MISTRAL_API,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        json={
            "model":      MODEL,
            "messages":   [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "max_tokens":  1500,
            "temperature": 0.3,
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()

    raw = resp.json()["choices"][0]["message"]["content"].strip()

    # Extraction JSON robuste
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("Mistral n'a pas retourné de JSON valide")

    try:
        result = json.loads(raw[start:end])
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON invalide : {e}")

    result["markets_analysed"] = len(filtered)
    result["category"] = category
    return result
