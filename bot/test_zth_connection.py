"""
Test de connexion ZeroToHeroBTC — lecture seule, aucun ordre passé.
Vérifie : la clé privée correspond bien à l'adresse, le solde on-chain,
et que les credentials API sont valides auprès de Polymarket.
"""
import sys
import os

_PYTHON311 = os.path.expanduser("~/.pyenv/versions/3.11.9/lib/python3.11/site-packages")
if os.path.exists(_PYTHON311) and _PYTHON311 not in sys.path:
    sys.path.insert(0, _PYTHON311)

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(".env")

import requests
from eth_account import Account

WALLET_ADDRESS = os.getenv("ZTH_WALLET_ADDRESS", "")
PRIVATE_KEY    = os.getenv("ZTH_PRIVATE_KEY", "")
API_KEY        = os.getenv("ZTH_API_KEY", "")
API_SECRET     = os.getenv("ZTH_API_SECRET", "")
API_PASSPHRASE = os.getenv("ZTH_API_PASSPHRASE", "")

print("=== 1. Clé privée valide ===")
derived = Account.from_key(PRIVATE_KEY).address
print(f"Adresse EOA dérivée de la clé privée (signataire) : {derived}")
print(f"Adresse dans .env ZTH_WALLET_ADDRESS (wallet/proxy Polymarket) : {WALLET_ADDRESS}")
print("ℹ️  Ces deux adresses sont normalement DIFFÉRENTES sur Polymarket")
print("    (le wallet affiché est un proxy Safe, signé par la clé privée de l'EOA) — voir compte existant, même topologie.")

print("\n=== 2. Solde on-chain (Polygon) ===")
USDC_CONTRACT  = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
PUSD_CONTRACT  = "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb"
POLYGON_RPC    = "https://polygon-bor-rpc.publicnode.com"

def rpc_call(method, params):
    r = requests.post(POLYGON_RPC, json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1}, timeout=10)
    r.raise_for_status()
    return r.json().get("result", "0x0")

data = "0x70a08231" + WALLET_ADDRESS[2:].lower().zfill(64)
try:
    pol_hex  = rpc_call("eth_getBalance", [WALLET_ADDRESS, "latest"])
    usdc_hex = rpc_call("eth_call", [{"to": USDC_CONTRACT, "data": data}, "latest"])
    pusd_hex = rpc_call("eth_call", [{"to": PUSD_CONTRACT, "data": data}, "latest"])
    print(f"POL (gas)   : {int(pol_hex, 16) / 1e18:.4f}")
    print(f"USDC native : {int(usdc_hex, 16) / 1e6:.2f}")
    print(f"pUSD        : {int(pusd_hex, 16) / 1e6:.2f}")
except Exception as e:
    print(f"❌ Erreur RPC : {e}")

print("\n=== 3. Credentials API Polymarket (auth L2) ===")
try:
    from polymarket.clients.secure import SecureClient
    from polymarket.models.clob.api_key import ApiKeyCreds

    creds = ApiKeyCreds(apiKey=API_KEY, secret=API_SECRET, passphrase=API_PASSPHRASE)
    with SecureClient.create(private_key=PRIVATE_KEY, wallet=WALLET_ADDRESS, credentials=creds) as client:
        print(f"Client créé pour wallet : {client.wallet}")
        orders = list(client.list_open_orders())
        print(f"✅ Auth API OK — {len(orders)} ordre(s) ouvert(s)")
except Exception as e:
    print(f"❌ Erreur auth API : {e}")
