# ZeroToHeroBTC — Design

## Contexte
Nouveau bot de trading autonome sur Polymarket, indépendant de ProfitWeather V2 / Agent Deko / Agent météo multi-villes. Il trade le marché récurrent **BTC Up/Down 5 minutes** (`btc-updown-5m-{timestamp}`), qui se renouvelle toutes les 5 minutes avec deux issues : "Up" et "Down".

## Compte Polymarket
- Compte Polymarket dédié, **distinct** de celui utilisé par ProfitWeather V2.
- Credentials stockées dans `bot/.env`, préfixées `ZTH_` pour ne pas entrer en collision avec les variables existantes (`WALLET_ADDRESS`, `PRIVATE_KEY`, `API_KEY`, etc.) :
  - `ZTH_WALLET_ADDRESS` — adresse du wallet/proxy Polymarket (le solde et les positions y sont rattachés)
  - `ZTH_PRIVATE_KEY` — clé privée de l'EOA signataire (différente de `ZTH_WALLET_ADDRESS`, c'est normal sur Polymarket — topologie identique au compte existant : wallet = proxy Safe, signé par l'EOA)
  - `ZTH_API_KEY` / `ZTH_API_SECRET` / `ZTH_API_PASSPHRASE` — credentials API L2 CLOB
  - `ZTH_DRY_RUN` — `true` par défaut (simulation, pas d'argent réel)
- Connexion testée et validée le 2026-06-18 via `bot/test_zth_connection.py` : auth API OK (1 ordre ouvert détecté), solde on-chain à 0 USDC/pUSD/POL au moment du test (à approvisionner avant tout passage en réel).
- Claude (Anthropic) **n'est pas utilisé** dans ce bot — décision 100% mécanique (revirement par rapport à l'idée initiale d'une validation IA, abandonnée pour rester simple et déterministe).

## Stratégie de trading
- **Détection du marché courant** : la fin de la fenêtre en cours correspond toujours au prochain multiple de 300 secondes en epoch Unix. Le slug se construit ainsi : `btc-updown-5m-{end_epoch}`.
- **Récupération des données marché** : `GET https://gamma-api.polymarket.com/events/slug/{slug}` pour obtenir les `clobTokenIds` des issues "Up" et "Down".
- **Timing de déclenchement** : le bot surveille en continu de 60 secondes restantes jusqu'à la clôture (toutes les 2s), et achète dès qu'un côté franchit le seuil à n'importe quel moment dans cette fenêtre — avec garde anti-double-trade par marché (un seul achat par `condition_id`/fenêtre). *(Mis à jour le 2026-06-18 : initialement 30s avec une fenêtre étroite, élargi à 60s→0 pour un suivi continu.)*
- **Règle de décision (codée en dur, non modifiable)** :
  - Lire le carnet d'ordres (`GET /book?token_id=...` sur `clob.polymarket.com`) des deux tokens Up et Down, prendre le meilleur prix d'achat (best ask) de chacun.
  - Si le prix d'achat d'un côté est **≥ 95%** → ce côté est acheté.
  - Sinon → on skip ce cycle, pas de trade.
- **Pas de validation IA** — la règle ci-dessus est suffisante et appliquée directement en Python (cohérent avec la leçon déjà notée sur ce projet : les hard limits doivent être dans le code, pas confiés à un LLM).
- **Fréquence** : pas de limite — trade à chaque cycle de 5 minutes qui remplit la condition (jusqu'à 288 cycles/jour).

## Exécution des ordres
- Mise = **5% du solde USDC disponible** du compte ZeroToHeroBTC, lu directement on-chain (solde pUSD du wallet `ZTH_WALLET_ADDRESS`, même méthode que `get_polygon_balance()` dans `pm_api.py` mais paramétrée sur ce wallet).
- Achat via le SDK `polymarket-client` (`SecureClient`), instance séparée construite avec les credentials `ZTH_*` — **aucune modification de `trader.py`/`pm_api.py`/`config.py` existants**, qui restent dédiés au compte ProfitWeather.
- Respect du mode `ZTH_DRY_RUN` : en `true`, les ordres sont simulés et loggés sans appel réel à l'API d'ordres (même logique que `trader.py`).

## Logging & gestion d'erreurs
- Pas de table Supabase pour ce bot (décision explicite : pas de stockage pour l'instant).
- Logs dans la console + fichier local `bot/zerotoherobtc_runtime.log` (convention des autres scripts du projet).
- Marché pas encore créé à T-30s → skip silencieux, on retente au cycle suivant.
- Prix n'atteint jamais 95% avant la clôture → skip silencieux.
- Échec de l'ordre (API, réseau) → log de l'erreur, pas de retry (fenêtre de 5 min trop courte pour qu'un retry ait du sens).

## Fichiers
- Nouveau script unique et autonome : `bot/zerotoherobtc.py`.
- Script de test de connexion déjà créé et conservé : `bot/test_zth_connection.py`.
- Nouvelles variables `ZTH_*` ajoutées à `bot/.env` (déjà fait et testées).

## Hors scope (pour l'instant)
- Pas de stockage Supabase / historique / dashboard pour ce bot.
- Pas de déploiement Railway — exécution locale uniquement, comme `loop_v2.py`.
- Pas de limite de fréquence ni de stop-loss/take-profit — le marché se résout naturellement à chaque fenêtre de 5 min (gain ou perte immédiate, pas de position à gérer dans le temps comme pour ProfitWeather).
