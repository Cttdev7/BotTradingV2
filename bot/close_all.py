"""
close_all.py — Affiche/calcule le P&L estimé de toutes les positions ouvertes (polyedge2).

⚠️  Le SDK polymarket-client (CTF Exchange V2) ne permet PAS de vendre une position
avant résolution — il n'y a donc aucun moyen de "fermer" une position en cours.
Ce script ne peut enregistrer un P&L final que pour les marchés déjà résolus
(prix ≈ 1.00 ou ≈ 0.00). Pour les positions encore ouvertes, il affiche juste le
P&L latent estimé — elles doivent attendre la résolution naturelle, comme dans
loop_v2.py (check_stop_loss).

Usage :
    source bot/.env && ~/.pyenv/versions/3.11.9/bin/python3 bot/close_all.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import requests
import datetime
import config

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_KEY", "")
BOT_ID = "polyedge2"

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[CLOSE][{ts}] {msg}", flush=True)

def sb_headers():
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }

def load_open_trades():
    r = requests.get(
        f"{SB_URL}/rest/v1/trade_history",
        params={"bot_id": f"eq.{BOT_ID}", "pnl": "is.null", "limit": "100"},
        headers=sb_headers(), timeout=10,
    )
    r.raise_for_status()
    return r.json()

def get_current_no_price(condition_id):
    try:
        r = requests.get(f"https://clob.polymarket.com/markets/{condition_id}", timeout=8)
        if r.status_code != 200:
            return None
        for token in r.json().get("tokens", []):
            if token.get("outcome", "").lower() == "no":
                return float(token.get("price", 0))
    except Exception as e:
        log(f"  ⚠️  Prix introuvable : {e}")
    return None

def update_pnl(trade_id, pnl):
    requests.patch(
        f"{SB_URL}/rest/v1/trade_history",
        params={"id": f"eq.{trade_id}"},
        json={"pnl": pnl},
        headers={**sb_headers(), "Prefer": "return=minimal"},
        timeout=5,
    )

def main():
    log("═" * 50)
    log("🔴  FERMETURE DE TOUTES LES POSITIONS — polyedge2")
    log("═" * 50)

    if not SB_URL or not SB_KEY:
        log("❌ Variables SUPABASE_URL / SUPABASE_KEY manquantes — source bot/.env d'abord")
        sys.exit(1)

    dry = os.getenv("DRY_RUN", "true").lower() == "true"
    if dry:
        log("⚠️  MODE DRY_RUN=true — aucun ordre réel ne sera passé")
    else:
        log("✅ DRY_RUN=false — les ordres seront réels")

    trades = load_open_trades()
    if not trades:
        log("✅ Aucune position ouverte — rien à fermer.")
        return

    log(f"📋 {len(trades)} position(s) ouverte(s) à fermer :")
    for t in trades:
        log(f"   • {t.get('city','?'):15s} | {t.get('question','')[:40]}…")
        log(f"     condition_id={t.get('condition_id','')[:16]}… | entrée={t.get('price'):.3f} | {t.get('amount_usdc'):.2f} USDC")

    print()
    if not dry:
        confirm = input("Confirmer la fermeture ? (oui/non) : ").strip().lower()
        if confirm not in ("oui", "o", "yes", "y"):
            log("❌ Annulé.")
            return

    log("─" * 50)
    total_pnl = 0.0
    ok_count = 0
    err_count = 0

    for t in trades:
        cid         = t.get("condition_id", "")
        city        = t.get("city", "?")
        entry_price = float(t.get("price") or 0)
        amount_usdc = float(t.get("amount_usdc") or 0)
        trade_id    = t.get("id", "")

        if entry_price <= 0 or amount_usdc <= 0:
            log(f"  ⚠️  {city} — données manquantes (price={entry_price}, usdc={amount_usdc}) — ignoré")
            err_count += 1
            continue

        tokens_held = amount_usdc / entry_price
        current_price = get_current_no_price(cid)
        est_pnl = round(tokens_held * ((current_price or entry_price) - entry_price), 2) if current_price else None

        cur_str = f"{current_price:.3f}" if current_price else "??"
        pnl_str = f"{est_pnl:+.2f}$" if est_pnl is not None else "??$"
        log(f"  🔄 {city} | entrée {entry_price:.3f} → actuel {cur_str} | ~{pnl_str} | {tokens_held:.4f} tokens")

        # Marché peut-être déjà résolu (price == 1.0 ou 0.0)
        if current_price is not None and current_price >= 0.999:
            real_pnl = round(tokens_held * (1.0 - entry_price), 2)
            log(f"    ✅ Résolu à 1.00 — P&L +${real_pnl:.2f} (pas de vente nécessaire)")
            update_pnl(trade_id, real_pnl)
            total_pnl += real_pnl
            ok_count += 1
            continue

        if current_price is not None and current_price <= 0.005:
            real_pnl = round(-amount_usdc, 2)
            log(f"    ❌ Résolu à 0.00 — perte totale ${real_pnl:.2f}")
            update_pnl(trade_id, real_pnl)
            total_pnl += real_pnl
            ok_count += 1
            continue

        # Le SDK ne permet pas de vendre une position non résolue (voir docstring) —
        # on ne peut qu'attendre la résolution naturelle, comme loop_v2.py.
        log(f"    ⏳ Position encore ouverte — vente impossible avec le SDK actuel, "
            f"attente résolution naturelle (P&L latent estimé {pnl_str})")

    log("─" * 50)
    log(f"📊 Résultat : {ok_count} fermé(s) | {err_count} erreur(s) | P&L total {total_pnl:+.2f}$")
    log("═" * 50)

if __name__ == "__main__":
    main()
