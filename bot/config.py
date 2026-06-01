import os
from dotenv import load_dotenv

load_dotenv()

WALLET_ADDRESS  = os.getenv("WALLET_ADDRESS", "")
API_KEY         = os.getenv("API_KEY", "")

# Nécessaires uniquement pour passer des ordres (Phase 2)
API_SECRET      = os.getenv("API_SECRET", "")
API_PASSPHRASE  = os.getenv("API_PASSPHRASE", "")
PRIVATE_KEY     = os.getenv("PRIVATE_KEY", "")

HOST     = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon

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
