import sys
sys.path.insert(0, '/Users/clementctt/.pyenv/versions/3.11.9/lib/python3.11/site-packages')

import os
os.chdir('/Users/clementctt/Documents/Claude code/Bottrading V2/bot')
from dotenv import load_dotenv
load_dotenv('/Users/clementctt/Documents/Claude code/Bottrading V2/bot/.env')

PRIVATE_KEY    = os.getenv("PRIVATE_KEY")
API_KEY        = os.getenv("API_KEY")
API_SECRET     = os.getenv("API_SECRET")
API_PASSPHRASE = os.getenv("API_PASSPHRASE")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")  # proxy existant : 0xb53b...

from polymarket.clients.secure import SecureClient
from polymarket.models.clob.api_key import ApiKeyCreds

creds = ApiKeyCreds(apiKey=API_KEY, secret=API_SECRET, passphrase=API_PASSPHRASE)

TOKEN_ID = "7043284209357266777622641405849840522617156242498797126650004329624680273078"

with SecureClient.create(private_key=PRIVATE_KEY, wallet=WALLET_ADDRESS, credentials=creds) as client:
    print(f"Wallet: {client.wallet}")
    print("Placement ordre 10 USDC BUY YES Toronto 31°C…")
    result = client.place_market_order(
        token_id=TOKEN_ID,
        side="BUY",
        amount=10.0,
    )
    print("Résultat:", result)
