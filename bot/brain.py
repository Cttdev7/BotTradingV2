"""
brain.py — Cerveau IA du bot (Claude API)

Reçoit : stratégie + marchés disponibles + historique des trades
Retourne : liste de décisions (acheter/vendre/ignorer)

La clé ANTHROPIC_API_KEY doit être dans .env.
"""

import json
import os
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

    system_prompt = """Tu es un assistant de trading sur Polymarket (marchés de prédiction).
Tu analyses des marchés et prends des décisions d'achat/vente basées sur la stratégie fournie.

Règles absolues :
- Ne jamais miser plus de 20% du solde disponible sur un seul marché
- Ne jamais miser sur un marché avec un volume < 1000 USDC (trop peu liquide)
- Toujours justifier chaque décision en une phrase
- Si aucun marché ne correspond à la stratégie, retourner une liste vide

Tu réponds UNIQUEMENT en JSON valide, sans texte avant ou après :
[
  {
    "action": "buy",
    "condition_id": "identifiant_du_marche",
    "outcome": "Yes",
    "amount_usdc": 25.0,
    "reason": "raison courte"
  }
]
Ou [] si aucune opportunité."""

    user_message = f"""STRATÉGIE :
{prompt_text}

SOLDE DISPONIBLE : ${balance_usdc:.2f} USDC

MARCHÉS DISPONIBLES :
{_format_markets(markets)}

HISTORIQUE DES TRADES (apprends de tes erreurs) :
{_format_history(history)}

Analyse ces marchés selon la stratégie et retourne tes décisions en JSON."""

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

    user = f"""STRATÉGIE ACTUELLE (version {version}) :
{current_prompt}

BILAN DES TRADES :
- Trades gagnants : {len(wins)}
- Trades perdants : {len(losses)}
- Trades ouverts  : {len(open_)}

HISTORIQUE DÉTAILLÉ (30 derniers) :
{_format_history(history[-30:])}

Réécris la stratégie pour qu'elle soit plus performante. Sois précis sur :
- Quels types de marchés cibler (ou éviter)
- À quels prix/probabilités acheter
- Taille des positions
- Critères de sortie

Si le bot a fait des erreurs, corrige-les explicitement dans la nouvelle stratégie."""

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
                    if price in (0.0, 1.0):  # marché résolu
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
