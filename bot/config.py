import os
from dotenv import load_dotenv

# Charge toujours bot/.env quel que soit le répertoire de lancement
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_env_path)

WALLET_ADDRESS  = os.getenv("WALLET_ADDRESS", "")
API_KEY         = os.getenv("API_KEY", "")

# Nécessaires uniquement pour passer des ordres (Phase 2)
API_SECRET      = os.getenv("API_SECRET", "")
API_PASSPHRASE  = os.getenv("API_PASSPHRASE", "")
PRIVATE_KEY     = os.getenv("PRIVATE_KEY", "")

HOST     = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon

# IA externe
MISTRAL_API_KEY   = os.getenv("MISTRAL_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Modèle Claude utilisé par le bot (haiku=pas cher, sonnet=équilibré, opus=premium)
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

def validate():
    """Vérifie que les clés minimales sont présentes."""
    missing = [k for k, v in {
        "API_KEY": API_KEY,
        "WALLET_ADDRESS": WALLET_ADDRESS,
    }.items() if not v]
    if missing:
        raise ValueError(f"Clés manquantes dans .env : {', '.join(missing)}")

def can_trade():
    """Retourne True si on a les clés complètes pour passer des ordres."""
    return bool(PRIVATE_KEY and API_SECRET and API_PASSPHRASE)
