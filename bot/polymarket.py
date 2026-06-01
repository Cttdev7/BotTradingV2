from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
import config

# ── Connexion ────────────────────────────────────────────────────────────────

def get_client() -> ClobClient:
    creds = ApiCreds(
        api_key=config.API_KEY,
        api_secret=config.API_SECRET,
        api_passphrase=config.API_PASSPHRASE,
    )
    return ClobClient(
        host=config.HOST,
        key=config.PRIVATE_KEY,
        chain_id=config.CHAIN_ID,
        creds=creds,
        signature_type=0,   # 0 = EOA (clé privée standard)
        funder=config.WALLET_ADDRESS,
    )

# ── Lectures ─────────────────────────────────────────────────────────────────

def get_markets(client: ClobClient, limit: int = 50) -> list:
    """Marchés actifs (première page)."""
    resp = client.get_markets(next_cursor="MA==")
    return resp.get("data", [])

def get_market(client: ClobClient, condition_id: str) -> dict:
    """Détail d'un marché."""
    return client.get_market(condition_id)

def get_positions(client: ClobClient) -> list:
    """Positions ouvertes du wallet."""
    resp = client.get_positions()
    return resp if isinstance(resp, list) else resp.get("data", [])

def get_balance(client: ClobClient) -> dict:
    """Solde USDC disponible."""
    try:
        balance = client.get_balance()
        return {"usdc": float(balance)}
    except Exception:
        # Certaines versions du SDK exposent get_usdc_balance()
        balance = client.get_usdc_balance()
        return {"usdc": float(balance)}

def get_order_book(client: ClobClient, token_id: str) -> dict:
    """Carnet d'ordres pour un token."""
    return client.get_order_book(token_id)

def get_open_orders(client: ClobClient) -> list:
    """Ordres ouverts du wallet."""
    resp = client.get_orders()
    return resp if isinstance(resp, list) else resp.get("data", [])
