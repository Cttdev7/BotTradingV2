"""Affiche le taux de victoire de ZeroToHeroBTC à partir de Supabase."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(".env")

import requests

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")

headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}

r = requests.get(
    f"{SB_URL}/rest/v1/zerotoherobtc_trades",
    params={"select": "resolved,win"},
    headers=headers,
    timeout=10,
)
r.raise_for_status()
trades = r.json()

resolved = [t for t in trades if t["resolved"]]
pending  = [t for t in trades if not t["resolved"]]
wins     = [t for t in resolved if t["win"] is True]
losses   = [t for t in resolved if t["win"] is False]

print(f"Total trades       : {len(trades)}")
print(f"Résolus            : {len(resolved)}")
print(f"  Gagnés           : {len(wins)}")
print(f"  Perdus           : {len(losses)}")
print(f"En attente         : {len(pending)}")
if resolved:
    print(f"Taux de victoire   : {len(wins) / len(resolved) * 100:.1f}%")
else:
    print("Taux de victoire   : pas encore de trade résolu")
