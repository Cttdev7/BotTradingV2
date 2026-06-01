import os
from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY     = os.getenv("PRIVATE_KEY")
API_KEY         = os.getenv("API_KEY")
API_SECRET      = os.getenv("API_SECRET")
API_PASSPHRASE  = os.getenv("API_PASSPHRASE")
WALLET_ADDRESS  = os.getenv("WALLET_ADDRESS")

HOST     = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon

def validate():
    missing = [k for k, v in {
        "PRIVATE_KEY": PRIVATE_KEY,
        "API_KEY": API_KEY,
        "API_SECRET": API_SECRET,
        "API_PASSPHRASE": API_PASSPHRASE,
        "WALLET_ADDRESS": WALLET_ADDRESS,
    }.items() if not v]
    if missing:
        raise ValueError(f"Clés manquantes dans .env : {', '.join(missing)}")
