"""
redeem_zth.py — Réclame (redeem) les positions ZeroToHeroBTC résolues et gagnantes,
créditant les gains dans le solde "espèces" du wallet Polymarket (0xf5EF...).

Pourquoi ce script existe (au lieu d'utiliser SecureClient.redeem_positions directement) :
1. SecureClient.redeem_positions() appelle list_markets() sans closed=True en interne,
   donc il ne trouve jamais un marché déjà clôturé ("Expected exactly one market... got 0").
2. Même corrigé, le dispatch passe par un relayer gasless qui exige une Builder/Relayer
   API Key qu'on n'a pas — on construit donc et signe nous-mêmes une transaction Safe
   execTransaction (wallet_type GNOSIS_SAFE v1.3.0), payée en gas par l'EOA (ZTH_PRIVATE_KEY).
3. L'adresse de contrat à appeler n'est PAS conditional_tokens directement mais
   context.adapter_address (collateral_adapter pour un marché non neg-risk) — sinon
   la transaction réussit sans rien faire (aucune erreur, aucun crédit).

Utilisation : python3 redeem_zth.py
"""

from __future__ import annotations
import os
import sys
import time
import requests
from typing import cast

_PYTHON311 = os.path.expanduser("~/.pyenv/versions/3.11.9/lib/python3.11/site-packages")
if os.path.exists(_PYTHON311) and _PYTHON311 not in sys.path:
    sys.path.insert(0, _PYTHON311)

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(".env")

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_abi import encode as abi_encode
from eth_utils import keccak, to_checksum_address

from polymarket.clients.secure import SecureClient
from polymarket.models.clob.api_key import ApiKeyCreds
from polymarket._internal.actions.relayer.positions import normalize_market_position_context
from polymarket.types import EvmAddress

RPC = "https://polygon-bor-rpc.publicnode.com"
ZERO_ADDR = "0x0000000000000000000000000000000000000000"

ZTH_WALLET_ADDRESS = os.environ["ZTH_WALLET_ADDRESS"]
ZTH_PRIVATE_KEY = os.environ["ZTH_PRIVATE_KEY"]
SAFE = to_checksum_address(ZTH_WALLET_ADDRESS)
EOA = Account.from_key(ZTH_PRIVATE_KEY).address


def rpc_call(method: str, params: list) -> str:
    r = requests.post(RPC, json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1}, timeout=15)
    res = r.json()
    if "error" in res:
        raise RuntimeError(res["error"])
    return res["result"]


def get_safe_nonce() -> int:
    selector = "0x" + keccak(text="nonce()")[:4].hex()
    return int(rpc_call("eth_call", [{"to": SAFE, "data": selector}, "latest"]), 16)


def build_redeem_call_data(collateral: str, condition_id: str) -> bytes:
    selector = keccak(text="redeemPositions(address,bytes32,bytes32,uint256[])")[:4]
    return selector + abi_encode(
        ["address", "bytes32", "bytes32", "uint256[]"],
        [collateral, b"\x00" * 32, bytes.fromhex(condition_id[2:]), [1, 2]],
    )


def sign_safe_tx(to: str, data: bytes, nonce: int) -> bytes:
    domain = {"chainId": 137, "verifyingContract": SAFE}
    types = {"SafeTx": [
        {"name": "to", "type": "address"}, {"name": "value", "type": "uint256"}, {"name": "data", "type": "bytes"},
        {"name": "operation", "type": "uint8"}, {"name": "safeTxGas", "type": "uint256"}, {"name": "baseGas", "type": "uint256"},
        {"name": "gasPrice", "type": "uint256"}, {"name": "gasToken", "type": "address"}, {"name": "refundReceiver", "type": "address"},
        {"name": "nonce", "type": "uint256"},
    ]}
    message = {
        "to": to, "value": 0, "data": data, "operation": 0, "safeTxGas": 0, "baseGas": 0,
        "gasPrice": 0, "gasToken": ZERO_ADDR, "refundReceiver": ZERO_ADDR, "nonce": nonce,
    }
    typed = encode_typed_data(domain_data=domain, message_types={"SafeTx": types["SafeTx"]}, message_data=message)
    return Account.sign_message(typed, private_key=ZTH_PRIVATE_KEY).signature


def build_exec_transaction_data(to: str, data: bytes, signature: bytes) -> str:
    selector = keccak(text="execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)")[:4]
    encoded = selector + abi_encode(
        ["address", "uint256", "bytes", "uint8", "uint256", "uint256", "uint256", "address", "address", "bytes"],
        [to, 0, data, 0, 0, 0, 0, ZERO_ADDR, ZERO_ADDR, bytes(signature)],
    )
    return "0x" + encoded.hex()


def redeem_condition(client: SecureClient, condition_id: str) -> bool:
    """Construit, simule puis envoie la transaction Safe de redeem. Retourne True si créditée."""
    env = client._ctx.environment
    page = client.list_markets(condition_ids=[condition_id], page_size=1, closed=True).first_page()
    if len(page.items) != 1:
        print(f"  [SKIP] marché introuvable (closed=True) pour {condition_id}")
        return False
    market = page.items[0]
    context = normalize_market_position_context(
        market, context=f"condition {condition_id}",
        collateral_adapter=cast(EvmAddress, env.collateral_adapter),
        neg_risk_collateral_adapter=cast(EvmAddress, env.neg_risk_collateral_adapter),
        conditional_tokens=cast(EvmAddress, env.conditional_tokens),
        neg_risk_adapter=cast(EvmAddress, env.neg_risk_adapter),
    )
    adapter = to_checksum_address(str(context.adapter_address))
    collateral = to_checksum_address(str(env.collateral_token))

    redeem_data = build_redeem_call_data(collateral, condition_id)
    nonce = get_safe_nonce()
    sig = sign_safe_tx(adapter, redeem_data, nonce)
    exec_data_hex = build_exec_transaction_data(adapter, redeem_data, sig)

    sim = rpc_call("eth_call", [{"from": EOA, "to": SAFE, "data": exec_data_hex}, "latest"])
    if sim != "0x" + "0" * 63 + "1":
        print(f"  [ABANDON] simulation négative pour {condition_id} : {sim}")
        return False

    eoa_nonce = int(rpc_call("eth_getTransactionCount", [EOA, "latest"]), 16)
    gas_est = int(rpc_call("eth_estimateGas", [{"from": EOA, "to": SAFE, "data": exec_data_hex}]), 16)
    max_priority = int(rpc_call("eth_maxPriorityFeePerGas", []), 16)
    base_fee = int(rpc_call("eth_getBlockByNumber", ["latest", False])["baseFeePerGas"], 16)
    tx = {
        "to": SAFE, "data": exec_data_hex, "value": 0, "nonce": eoa_nonce,
        "gas": int(gas_est * 1.3), "maxFeePerGas": base_fee * 2 + max_priority,
        "maxPriorityFeePerGas": max_priority, "chainId": 137, "type": 2,
    }
    raw = Account.sign_transaction(tx, ZTH_PRIVATE_KEY).raw_transaction.hex()
    if not raw.startswith("0x"):
        raw = "0x" + raw
    txhash = rpc_call("eth_sendRawTransaction", [raw])
    print(f"  TX envoyée : {txhash}")

    for _ in range(20):
        time.sleep(3)
        rcpt = rpc_call("eth_getTransactionReceipt", [txhash])
        if rcpt:
            ok = rcpt.get("status") == "0x1"
            print(f"  Reçu : status={rcpt.get('status')} ({'succès' if ok else 'échec'})")
            return ok
    print("  Pas encore confirmée après 60s — vérifier plus tard :", txhash)
    return False


_redeem_client: SecureClient | None = None


def _get_redeem_client() -> SecureClient:
    global _redeem_client
    if _redeem_client is None:
        creds = ApiKeyCreds(
            apiKey=os.environ["ZTH_API_KEY"],
            secret=os.environ["ZTH_API_SECRET"],
            passphrase=os.environ["ZTH_API_PASSPHRASE"],
        )
        _redeem_client = SecureClient.create(private_key=ZTH_PRIVATE_KEY, wallet=ZTH_WALLET_ADDRESS, credentials=creds)
    return _redeem_client


def redeem_all_resolved(log=None) -> int:
    """Réclame toutes les positions redeemable=True. Retourne le nombre réclamé avec succès."""
    out = log.info if log else print
    client = _get_redeem_client()
    redeemed = 0
    for page in client.list_positions():
        for p in page.items:
            if not p.redeemable:
                continue
            out(f"[redeem_zth] REDEEMABLE {p.slug} {p.outcome} value={p.current_value}")
            if redeem_condition(client, p.condition_id):
                out(f"[redeem_zth] {p.slug} réclamé avec succès, fonds crédités en espèces.")
                redeemed += 1
    return redeemed


if __name__ == "__main__":
    n = redeem_all_resolved()
    if n == 0:
        print("Aucune position réclamable pour l'instant.")
