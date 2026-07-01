# ProfitWeather V3 — Design

## Contexte

ProfitWeather V2 (`loop_v2.py`) achète NO tard (75-96¢), stratégie sûre à marge fine. L'analyse de sailor82 (voir mémoire `copy_sailor82_bot.md`) a montré que le vrai edge sur les marchés température se trouve sur les prix bas (<50¢), avec un rendement proportionnel bien supérieur malgré un win rate plus faible.

ProfitWeather V3 exploite ça dans l'autre sens : acheter **YES très tôt** à l'ouverture du marché (prix bas, 5-15¢) sur la fourchette la plus proche de la meilleure prévision disponible, puis revendre en cours de journée si le relevé météo officiel s'écarte de la fourchette achetée. Objectif : ~60% de réussite, mais gains asymétriques (petites pertes, gros gains).

## Cohabitation avec le V2

- Même compte Polymarket (mêmes credentials `.env`)
- Tournent en parallèle, partagent le solde
- Plafond d'exposition simultanée : **50% du solde pour chacun** (V2 et V3)
- ⚠️ Nécessite d'abaisser `MAX_EXPOSURE_PCT` du V2 de `1.0` à `0.5` dans `loop_v2.py` — sinon le plafond V3 n'a pas de garantie réelle

## Phase 1 — Backtest des sources météo

Script one-shot (pas un bot) : `bot/backtest_weather_sources.py`

1. Récupère les marchés température Polymarket résolus récemment, **toutes villes**
2. Pour chaque marché, compare la prévision qu'auraient donnée Open-Meteo, ECMWF (`weather_validator.py`), et les stations réelles METAR/WU — prise quelques jours avant clôture — à la température réellement observée à la résolution
3. Calcule l'écart moyen (°F) par source, si possible par région
4. Sort une recommandation de source par défaut (éventuellement différenciée par région)

Résultat : détermine la source de prévision utilisée en Phase 2.

## Phase 2 — Architecture du bot (`bot/loop_v3.py`)

### Cycle principal (poll 1-2 min)

1. **Détection** : scan tous les marchés température via `get_weather_markets()`, compare à une liste de marchés déjà vus (persistée) → identifie les nouveaux
2. **Source officielle de résolution** : auto-détection depuis la description du marché (extension de `fetch_wu_stations.py`)
3. **Prévision** : récupère la prévision via la source retenue en Phase 1, identifie la fourchette du marché la plus proche
4. **Filtre prix** : ask ≤ 15¢ sur cette fourchette → candidat
5. **Analyse Haiku** : confirme/pondère la décision (score de confiance, comme `copy_sailor82.py`)
6. **Achat** : si confiance suffisante et budget disponible → achète YES

### Surveillance des positions ouvertes

- Relevé du jour de la source officielle comparé à la fourchette achetée
- **Sortie météo** : si le max du jour dépasse déjà la borne haute, ou si le pic du jour est manifestement passé sans avoir atteint la borne basse → vente immédiate (logique similaire au signal "pic METAR confirmé" du V2, appliquée à une position YES)
- **Sortie stop-loss prix** : prix de revente en baisse de 30% depuis l'achat → vente immédiate
- Sinon : tenir jusqu'à résolution naturelle

## Gestion du risque

- Plafond V3 : 50% du solde total en position ouverte simultanée max
- Mise par trade : max 10% du capital alloué à V3 (= 5% du solde total)
- Stop-loss prix : -30%
- Prix d'achat initial : ≤ 15¢

## Persistance

Table Supabase `profitweather_v3_trades` :
`condition_id, title, outcome, city, station_source, forecast_temp, entry_price, bet_usdc, confidence, analysis, status (open/won/lost/sold_early), exit_reason (resolution/weather_divergence/stop_loss), exit_price, pnl, created_at, closed_at`

## Déploiement

- Nouvelle app Fly.io `profitweather-v3`, région Toronto (`yyz`), comme ZTH/sailor82 (pas de VPN requis)
- Config : `fly-profitweather-v3.toml` + `Dockerfile.profitweather-v3`
- Démarrage : `V3_DRY_RUN=true` par défaut, bilan après quelques jours avant passage en réel
