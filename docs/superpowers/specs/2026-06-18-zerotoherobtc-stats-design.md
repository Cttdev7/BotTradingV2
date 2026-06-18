# ZeroToHeroBTC — Stockage des trades & taux de victoire — Design

## Contexte
Le bot ZeroToHeroBTC tourne actuellement en `ZTH_DRY_RUN=true` et ne garde aucune trace de ses décisions. L'utilisateur veut pouvoir mesurer le taux de victoire de la stratégie (acheter à ≥95% à 60s-0 de la clôture) pendant cette phase de simulation, avant de risquer de l'argent réel. Cette spec couvre uniquement la partie stockage + calcul (étape 1) ; l'affichage sur le dashboard est explicitement reporté à une étape 2 ultérieure.

## Problème du solde à 0 en simulation
`ZTH_WALLET_ADDRESS` a un solde on-chain de 0 USDC/pUSD (confirmé via `test_zth_connection.py`). Comme la mise = 5% du solde réel, le bot ne déclencherait jamais de trade simulé tant que le compte n'est pas approvisionné, rendant impossible toute mesure de taux de victoire.

**Solution** : quand `ZTH_DRY_RUN=true`, la mise utilise un **solde de référence fictif de 100 USDC** (donc 5 USDC par trade simulé) au lieu du vrai solde on-chain. Quand `ZTH_DRY_RUN=false`, le bot repasse sur le vrai solde on-chain (comportement actuel, inchangé).

## Table Supabase `zerotoherobtc_trades`
Même projet Supabase que le reste du projet (`SUPABASE_URL`/`SUPABASE_KEY` déjà dans `.env`), nouvelle table dédiée :

| Colonne | Type | Description |
|---|---|---|
| `id` | bigint (identity) | clé primaire |
| `slug` | text | ex. `btc-updown-5m-1781812200` |
| `end_epoch` | bigint | epoch Unix de fin de la fenêtre |
| `condition_id` | text | identifiant du marché Polymarket |
| `outcome` | text | `"Up"` ou `"Down"` — côté acheté |
| `price_at_buy` | numeric | prix best-ask au moment de l'achat |
| `amount_usdc` | numeric | mise (réelle ou simulée selon `dry_run`) |
| `dry_run` | boolean | `true` si c'était une simulation |
| `created_at` | timestamptz | défaut `now()` |
| `resolved` | boolean | défaut `false` |
| `actual_outcome` | text, nullable | `"Up"` ou `"Down"` une fois connu |
| `win` | boolean, nullable | `true` si `outcome == actual_outcome` |
| `resolved_at` | timestamptz, nullable | quand la résolution a été faite |

## Flux d'enregistrement et de résolution
1. **À chaque trade** (simulé ou réel) dans `run_cycle` : une ligne est insérée dans `zerotoherobtc_trades` avec `resolved=false`, juste après l'appel à `place_buy`.
2. **Résolution différée** : au début de chaque nouvel appel à `run_cycle` (donc environ toutes les 5 minutes, au rythme naturel du bot), une fonction `resolve_pending_trades()` :
   - cherche en base les lignes `resolved=false`
   - ne traite que celles dont `end_epoch + 60s` est déjà passé (le marché a eu le temps de se résoudre sur Polymarket)
   - relit l'événement via Gamma API (`outcomePrices`) pour connaître le côté gagnant réel
   - si le marché n'est pas encore résolu côté Polymarket (cas rare), la ligne reste `resolved=false` et sera retentée au cycle suivant — pas d'erreur, pas de blocage
   - met à jour `resolved=true`, `actual_outcome`, `win`, `resolved_at`

## Script de consultation `bot/zth_stats.py`
Nouveau script autonome, dans la convention existante du projet (comme `test_order.py`) :
- Lit toutes les lignes `resolved=true` de `zerotoherobtc_trades`
- Affiche : nombre total résolu, gagnés, perdus, en attente de résolution, et taux de victoire en %
- Lancé manuellement : `python3 bot/zth_stats.py`

## Hors scope (reporté à l'étape 2)
- Affichage sur le dashboard web (page ou section dédiée) — sera fait une fois qu'il y aura des données réelles à montrer.
- Pas de changement à la logique de décision (seuil 95%, fenêtre 60s-0) — uniquement de l'enregistrement/lecture en plus.
