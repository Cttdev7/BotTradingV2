"""
Dérive les credentials API Polymarket depuis la PRIVATE_KEY du wallet.
Utilise EIP-712 (format L1 Polymarket officiel).
"""
import time
import requests
import json
import config
from eth_account import Account

MSG_TO_SIGN = "This message attests that I control the given wallet"
DOMAIN_NAME    = "ClobAuthDomain"
DOMAIN_VERSION = "1"
CHAIN_ID       = 137

def l1_headers(account, nonce=0):
    address = account.address
    timestamp = str(int(time.time()))
    signed = Account.sign_typed_data(
        private_key=config.PRIVATE_KEY,
        domain_data={"name": DOMAIN_NAME, "version": DOMAIN_VERSION, "chainId": CHAIN_ID},
        message_types={"ClobAuth": [
            {"name": "address",   "type": "address"},
            {"name": "timestamp", "type": "string"},
            {"name": "nonce",     "type": "uint256"},
            {"name": "message",   "type": "string"},
        ]},
        message_data={"address": address, "timestamp": timestamp, "nonce": nonce, "message": MSG_TO_SIGN},
    )
    sig = signed.signature.hex()
    return {
        "POLY_ADDRESS":   address,
        "POLY_SIGNATURE": "0x" + sig if not sig.startswith("0x") else sig,
        "POLY_TIMESTAMP": timestamp,
        "POLY_NONCE":     str(nonce),
        "Content-Type":   "application/json",
    }

def derive_credentials():
    pk = config.PRIVATE_KEY
    if not pk:
        print("❌ PRIVATE_KEY manquante dans .env")
        return

    account = Account.from_key(pk)
    print(f"Wallet : {account.address}")

    # Essaie nonce 0 à 4 jusqu'à trouver un slot disponible
    r = None
    for nonce in range(5):
        print(f"\n→ Tentative nonce={nonce}…")
        r = requests.post(
            "https://clob.polymarket.com/auth/api-key",
            headers=l1_headers(account, nonce=nonce),
            timeout=10,
        )
        print(f"  POST /auth/api-key → {r.status_code} : {r.text[:100]}")
        if r.status_code == 200:
            break

    if not r or r.status_code != 200:
        print("❌ Impossible de créer une clé API — toutes les slots sont prises.")
        return

    creds = r.json()
    print(json.dumps(creds, indent=2))

    api_key        = creds.get("apiKey") or creds.get("api_key", "?")
    api_secret     = creds.get("secret") or creds.get("api_secret", "?")
    api_passphrase = creds.get("passphrase") or creds.get("api_passphrase", "?")

    print("\n✅ Copie ces 3 valeurs dans bot/.env :")
    print(f"  API_KEY        = {api_key}")
    print(f"  API_SECRET     = {api_secret}")
    print(f"  API_PASSPHRASE = {api_passphrase}")

if __name__ == "__main__":
    derive_credentials()
