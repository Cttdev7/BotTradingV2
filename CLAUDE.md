# TradingBot V2 — Instructions pour Claude

## Ce que fait ce projet
Bot de trading autonome sur **Polymarket** (marchés de prédiction) avec dashboard iOS-style.
- **ProfitWeather V2** : bot de trading météo — Claude Haiku décide quoi acheter (stratégie NO sur fourchettes température)
- **Agent Deko** : surveille les trades de sailor82 en temps réel pour générer des signaux bonus
- **Agent météo multi-villes** : 45 bots d'analyse qui trackent les options YES >75% sur les marchés température
- **Stratège Mistral** : analyse cross-ville toutes les 15 min, apprend des analyses passées
- **ZeroToHeroBTC** : bot 100% mécanique sur marchés Polymarket BTC Up/Down 5 min — surveille à partir de T-120s, achète le côté ≥90%, compte dédié séparé (variables `ZTH_*`), tourne 24/7 sur **Fly.io Toronto (`yyz`)**

## Structure du projet
```
Bottrading V2/
├── dashboard/          ← Frontend web (HTML/CSS/JSX, React via CDN) → Vercel
│   ├── index.html
│   ├── styles.css
│   ├── app.jsx         ← Shell, navigation, sidebar avec drapeaux pays
│   ├── api.jsx         ← Fetch données réelles depuis localhost:5050
│   ├── data.jsx        ← 45 bots température + ProfitWeather + Crypto
│   ├── charts.jsx
│   ├── icons.jsx
│   ├── ui.jsx
│   ├── tweaks-panel.jsx
│   ├── page_dashboard.jsx
│   ├── page_bot.jsx    ← Onglet unique "Analyse" pour les bots température
│   ├── page_stratege.jsx ← Page Mistral stratège (hero violet, stats par ville)
│   ├── page_portfolio.jsx
│   ├── page_settings.jsx
│   ├── page_history.jsx
│   └── page_calendar.jsx ← Calendrier P&L ProfitWeather V2 (depuis PERF_RESET_DATE)
├── bot/                ← Backend Python
│   ├── config.py       ← Charge .env
│   ├── auth.py         ← Signature HMAC-SHA256
│   ├── polymarket.py   ← API Polymarket + get_weather_markets() ← clé
│   ├── pm_api.py       ← Alias/wrapper polymarket.py utilisé par loop_v2.py
│   ├── brain.py        ← Claude Haiku : décide quoi trader, lit les signaux Supabase
│   ├── trader.py       ← Exécution ordres (DRY_RUN=true par défaut)
│   ├── loop.py         ← Ancienne boucle ProfitWeather (remplacée par loop_v2.py)
│   ├── loop_v2.py      ← ⭐ ProfitWeather V2 — stratégie NO, ACTIF en local
│   ├── agent_deko.py   ← ⭐ Surveille sailor82 (@sailor82) → table deko_trades
│   ├── weather_validator.py ← Enrichissement ECMWF (band_prob, models_spread, models_avg) + stations METAR/WU
│   ├── server.py       ← Flask API port 5050 (+ /api/v2/trades, /api/v2/calendar) — pas 5000 (AirPlay macOS le bloque)
│   ├── agent_temperature_cloud.py ← 45 villes, Railway 24/7 ← ACTIF
│   ├── derive_api_key.py ← Régénère credentials Polymarket si expirés
│   ├── close_all.py    ← Ferme manuellement toutes les positions ouvertes polyedge2 (script ponctuel)
│   ├── fetch_wu_stations.py ← Scrape les codes stations WU réels depuis les descriptions de marchés Polymarket
│   ├── wu_stations.json ← Résultat du scraping ci-dessus (cache local)
│   ├── test_order.py   ← Script de test ponctuel pour passer un ordre via SecureClient
│   ├── postmortems.log ← Log des analyses post-mortem générées par postmortem.py
│   ├── requirements.txt
│   └── .env            ← Toutes les clés (jamais committé)
├── STRATEGIE_BOT.md    ← Doc stratégie en langage simple pour l'utilisateur (non-dev)
├── notes               ← Idées d'amélioration brutes (brouillon, voir section "Améliorations futures")
├── Procfile            ← Railway : python3 bot/agent_temperature_cloud.py
├── requirements.txt    ← Dépendances Railway
└── scripts/
    ├── Lancer le dashboard.command
    ├── Lancer le bot.command
    └── Lancer la stratégie.command  ← Lance ProfitWeather (loop.py — legacy)
```

## Lancer le projet
```bash
# Dashboard local
cd dashboard && python3 -m http.server 8080   # → http://localhost:8080

# Serveur bot (données temps réel dashboard)
python3 bot/server.py                          # → http://localhost:5050

# ProfitWeather V2 — TRADING RÉEL
source bot/.env && ~/.pyenv/versions/3.11.9/bin/python3 bot/loop_v2.py

# Agent Deko (surveille sailor82, signal bonus)
source bot/.env && ~/.pyenv/versions/3.11.9/bin/python3 bot/agent_deko.py
```

## Conventions frontend
- React 18 via CDN, Babel transpile JSX dans le navigateur, **aucun build**
- Composants exposés sur `window` (ex. `window.BotPage`)
- Styles inline React partout (pas de classes CSS sauf layout global)
- Variables CSS : `var(--accent)`, `var(--green)`, `var(--text)`, `var(--fill)`…
- Dashboard déployé sur **Vercel** (auto-deploy depuis GitHub)

## État actuel
- ✅ Dashboard iOS complet — Vercel, auto-deploy GitHub
- ✅ **45 villes actives** :
  - Chengdu 🇨🇳, Séoul 🇰🇷, Hong Kong 🇭🇰, NYC 🇺🇸, Londres 🇬🇧, Tokyo 🇯🇵, Atlanta 🇺🇸, Seattle 🇺🇸, Miami 🇺🇸, Singapour 🇸🇬, Madrid 🇪🇸, Shanghai 🇨🇳, Los Angeles 🇺🇸, Guangzhou 🇨🇳, Mexico City 🇲🇽, Amsterdam 🇳🇱, Paris 🇫🇷, Toronto 🇨🇦, Chicago 🇺🇸, Denver 🇺🇸, Houston 🇺🇸, Taipei 🇹🇼, Beijing 🇨🇳, San Francisco 🇺🇸, Dallas 🇺🇸
  - Wellington 🇳🇿, Chongqing 🇨🇳, Wuhan 🇨🇳, Ankara 🇹🇷, Moscou 🇷🇺, Lucknow 🇮🇳, Istanbul 🇹🇷, Varsovie 🇵🇱, Milan 🇮🇹, Helsinki 🇫🇮, Karachi 🇵🇰, Cape Town 🇿🇦, Jeddah 🇸🇦, Shenzhen 🇨🇳, Busan 🇰🇷, Qingdao 🇨🇳, Kuala Lumpur 🇲🇾
  - Tel Aviv 🇮🇱, Manila 🇵🇭, Munich 🇩🇪
- ✅ **ProfitWeather V2** (`loop_v2.py`) — bot NO sur fourchettes température, **DRY_RUN=false (TRADING RÉEL)**
- ✅ **Agent Deko** (`agent_deko.py`) — surveille sailor82, cycle 15 min, alimente `deko_trades` Supabase
- ✅ **Mistral Stratège** — analyse cross-ville toutes les 15 min (Railway)
- ✅ Toutes les clés dans `bot/.env` : ANTHROPIC, POLYMARKET (PRIVATE_KEY, API_KEY, API_SECRET, API_PASSPHRASE), SUPABASE, MISTRAL
- ✅ `can_trade: True` — clés Polymarket valides (API_KEY régénéré avec nonce=1 en juin 2026)
- ✅ **DRY_RUN=false** — trading réel activé (premier ordre Toronto 31°C le 2026-06-11)
- ✅ Résolution marchés : lit `/events` pour vrai prix (fix CLOB bloqué à 51%), fallback Open-Meteo
- ✅ **Python 3.11.9** via pyenv installé (`~/.pyenv/versions/3.11.9/`) — requis pour trader.py et loop_v2.py
- ✅ **trader.py** utilise le nouveau SDK `polymarket-client` (SecureClient) — CTF Exchange V2

## ProfitWeather V2 — Bot de trading (local)
- **Script** : `bot/loop_v2.py` (remplace loop.py)
- **Python** : `~/.pyenv/versions/3.11.9/bin/python3` — OBLIGATOIRE (trader.py exige Python 3.11+)
- **Cerveau** : Claude Haiku (`brain.py`) — analyse les candidats + décide
- **Exécution ordres** : `trader.py` → `polymarket-client` SecureClient (CTF Exchange V2)
- **Stratégie** : acheter **NO uniquement** sur fourchettes température clairement hors prévision ECMWF
- **Cycle** : toutes les 5 min, auto-amélioration de stratégie toutes les 6h
- **Persistance** : stratégie dans Supabase (`bot_strategies` id=`polyedge2`), historique dans `trade_history`

### Paramètres hard-codés loop_v2.py (NE PAS laisser Claude Haiku les modifier)
```python
MIN_NO_PRICE          = 0.75    # NO minimum 75¢
MAX_NO_PRICE          = 0.96    # NO maximum 96¢ (au-dessus = marge trop faible)
MAX_EXPOSURE_PCT      = 1.0     # 100% du portefeuille (cash + positions ouvertes) peut être exposé
MAX_BET_PCT           = 0.05    # jamais plus de 5% du solde sur 1 trade
MIN_FORECAST_GAP_DOWN = 2.0     # range EN-DESSOUS prévision (déjà dépassée → safe) : 2°F suffisent
MIN_FORECAST_GAP_UP   = 8.0     # range AU-DESSUS prévision : gap mini si jamais autorisé (cascade/pic confirmé)
MAX_ENSEMBLE_PROB     = 30      # si ECMWF prédit >30% dans ce range → interdit
MAX_BAND_PROB         = 20      # band_prob max (None = données absentes = refus)
MAX_MODELS_SPREAD     = 10.0    # si modèles ECMWF divergent >10°F → trop incertain
MIN_VOLUME            = 1_500   # volume minimum USDC
NO_STOP_LOSS_PCT      = -0.50   # -50% → déclenche le hedge/post-mortem (pas de vente, voir ci-dessous)
NO_TAKE_PROFIT        = 0.99    # NO ≥ 99¢ → vend et lock profit
CASCADE_TRIGGER       = 0.35    # range YES dominant >35% → cascade NO sur les ranges adjacents
HEDGE_YES_TRIGGER      = 0.60   # YES ≥ 60% (et < 90%) sur notre NO perdant → auto-hedge YES
HEDGE_MULTIPLIER       = 1.10   # mise hedge calculée pour +10% si le YES gagne
PERF_RESET_DATE        = "2026-06-17T15:34:00"  # stats/calendrier dashboard repartent de 0 à cette date
```

### Vente via le SDK (corrigé le 21/06 — l'ancienne note disait l'inverse)
`polymarket-client` (SecureClient) supporte bien la vente (`side="sell"`). Take-profit ET stop-loss vendent désormais activement dès que possible :
- **Take-profit** (`NO_TAKE_PROFIT`) : vend dès que le prix NO atteint le seuil.
- **Stop-loss** (`NO_STOP_LOSS_PCT`) : vend dès que la perte atteint le seuil, au lieu d'attendre la résolution — limite la perte au lieu de la laisser courir jusqu'à -100%.
- Si la vente échoue (solde réel quasi nul, erreur API) → fallback sur l'ancien comportement : attente de la résolution naturelle, P&L enregistré dans `trade_history` quand le prix touche ~0 (perdu) ou ~1 (gagné), ou via `check_market_outcomes`.
- L'**auto-hedge** (acheter le YES en face, voir plus bas) reste disponible en complément, déclenché avant le test stop-loss.

### Règles de trading V2
- **NO uniquement** — pas de YES (trop complexe, focus sur ce qui marche)
- **1 trade max par ville par cycle** — `traded_cities` set réinitialisé à chaque cycle
- **1 trade max par ville en position ouverte** — `open_cities` bloqué dans `_prefilter`
- **Signal Deko** : consultatif uniquement — Claude analyse avant de décider. Si sailor82 est NO sur le même marché → boost de certitude d'un niveau (low→medium, medium→high)
- **Double vérification prix** : T1 puis T2 (4s après) — annulé si prix chute >2¢ entre les deux
- **Règle directionnelle (leçon Chicago/canicule)** :
  - Range EN-DESSOUS de la prévision → autorisé (2°F gap min) — la temp dépasse déjà ce range, c'est safe
  - Range AU-DESSUS de la prévision → **toujours BLOQUÉ** dans le filtre normal (`_prefilter`), même en cascade, sauf si le **signal "pic METAR confirmé"** dit que le max journalier est déjà tombé (température ne peut plus monter)
  - Exemple : prévision Paris 37°C → on achète NO sur 34°C (en-dessous) ✅, jamais NO sur 39°C (au-dessus) ❌ sauf pic confirmé
- **Signal "pic METAR confirmé"** : si la station METAR montre que la température a baissé depuis son max du jour → le max est considéré comme verrouillé → permet de trader immédiatement (même avant 15h, même sur un range au-dessus) car on connaît déjà le résultat
- **Cascade** (`CASCADE_TRIGGER = 0.60`) : si un range atteint **60%** YES → les ranges adjacents reçoivent un signal NO automatique (le marché dit déjà où sera la température)
- **Auto-hedge** (leçon Cape Town/London) : si un NO acheté perd et que le YES en face monte entre 60% et 90%, le bot achète automatiquement le YES avec une mise calculée pour ressortir +10% si le YES gagne — transforme une perte quasi-certaine en position neutre/légèrement gagnante. **Pas de hedge si YES ≥ 90%** (marché quasi-résolu, plus rien à gagner). Un hedge par position max (`_hedged_cids_session` + colonne en DB)
- **Stations WU exactes** (source de résolution Polymarket, confirmées via `fetch_wu_stations.py` sur les descriptions de marchés) : London=EGLC, Paris=LFPB, NYC=KLGA, Dallas=KDAL, Denver=KBKF, Seoul=RKSI, Taipei=RCSS, Milan=LIMC (pas les aéroports principaux !)
- **Marchés valeur unique °C** (ex: "be 34°C") ne sont plus bloqués par défaut — ils sont traités comme une fourchette d'1°C par `_parse_range_bounds` (ancienne règle de blocage retirée le 17/06)

## Agent Deko (`agent_deko.py`)
- **But** : surveiller les trades de sailor82 (@sailor82, Polymarket, addr `0xbbb72a812c…`)
- **Cycle** : toutes les 15 min
- **API** : `data-api.polymarket.com/activity?user=...` (type `TRADE`, pas `BUY`)
- **Table Supabase** : `positions_tracker` (réécrit le 21/06 — `deko_trades` est une table morte, ne plus l'utiliser)
- `loop_v2.py` lit le signal sailor82 via `load_deko_trades()` qui interroge `positions_tracker`, pas `deko_trades`
- **Bug corrigé** : l'API retourne `type=TRADE` pas `type=BUY` — le filtre était `not in ("BUY",)` → corrigé en `not in ("BUY", "TRADE")`
- **Stratégie de sailor82 observée** : NO à 84-96¢ sur NYC, Houston, SF, LA, Austin, Seattle + YES spéculatifs à 38-48¢ (Atlanta, Austin, SF) — mise $7-$130 par trade

## ZeroToHeroBTC (`bot/zerotoherobtc.py`)
- **Stratégie** : marché BTC up/down toutes les 5 min — surveille en continu de T-120s à T-2s (`TRIGGER_MAX_REMAINING=120`), achète si un côté est entre `PRICE_THRESHOLD` (0.90) et `PRICE_CEILING` (0.97 — au-delà, profit quasi nul, pas la peine)
- **Mise** : fixe, `BET_USDC = 10.0` par trade (pas un % du solde)
- **Double vérification anti-fausse-alerte** : après détection, attend `RECHECK_DELAY` (2.5s) puis relit le prix — annule si le prix a baissé de plus de `RECHECK_MAX_DROP` (2¢) ou dépasse le plafond
- **Coupe-circuit** : `MAX_CONSECUTIVE_LOSSES = 3` — pause le bot après 3 pertes d'affilée (vérifié via `get_consecutive_losses()` sur Supabase), uniquement en mode réel
- **Compte dédié** : variables `ZTH_WALLET_ADDRESS` (wallet Safe, détient les fonds), `ZTH_PRIVATE_KEY` (clé de l'EOA propriétaire du Safe — **adresse différente** du wallet, ne pas confondre), `ZTH_API_KEY/SECRET/PASSPHRASE`, `ZTH_DRY_RUN`
- **Trading réel actif depuis le 21/06** : `ZTH_DRY_RUN=false`, wallet financé (~$100 USDC sur Polygon). Tourne 24/7 sur **Fly.io (Londres, région `lhr`)**.
- **Persistance** : table Supabase `zerotoherobtc_trades` (`dry_run` distingue simulé/réel) — `bot/zth_stats.py` calcule le win rate
- **Dashboard** : `dashboard/page_zerotohero_results.jsx` — win rate + historique des trades depuis Supabase

### Déploiement Fly.io (29/06 — ACTIF, trading réel)
Railway (AWS US West) et Hetzner Allemagne sont géobloqués par Polymarket. Le bot tourne désormais sur **Fly.io région Londres (`lhr`)**, qui n'est pas géobloqué et ne nécessite pas de VPN.

- **App Fly.io** : `zth-bot` — dashboard : fly.io/apps/zth-bot
- **Région** : Toronto `yyz` (Canada) — London `lhr` et Singapore `sin` étaient géobloqués
- **Logs temps réel** : `/Users/clementctt/.fly/bin/fly logs --app zth-bot`
- **Redéployer** : `cd "Bottrading V2" && /Users/clementctt/.fly/bin/fly deploy --app zth-bot`
- **Changer de région** : modifier `primary_region` dans `fly.toml`, puis cloner la machine (`fly machine clone <id> --region <region>`), vérifier les logs, puis supprimer l'ancienne (`fly machine destroy <id> --force`)
- **Modifier un secret** : `/Users/clementctt/.fly/bin/fly secrets set CLE=valeur --app zth-bot`
- **Fichiers de config** : `fly.toml` (région, VM) + `Dockerfile` + `requirements-zth.txt` à la racine du projet
- **Pas de VPN nécessaire** — IPs Fly.io Toronto non géobloquées par Polymarket
- **Logs dashboard** : table Supabase `zerotoherobtc_logs` — le bot y envoie des logs temps réel via `sb_log()` (non-bloquant, threading), visibles dans la page Résultats ZeroToHero du dashboard

**Rappel Railway** : les 2 services restants sur Railway (`fabulous-perception`=deko, `BotTradingV2`=worker température) continuent de tourner normalement — ils utilisent l'API gamma/data (pas CLOB) donc pas géobloqués.

### Bug critique corrigé le 21/06 — slug = début de fenêtre, pas fin
Le numéro dans le slug Polymarket (`btc-updown-5m-{epoch}`) correspond au **début** de la fenêtre de 5 min, pas à sa fin (vérifié via `endDate` de l'API gamma = epoch+300). Le bot utilisait cet epoch comme fin de fenêtre → il suivait systématiquement le marché **suivant** (qui vient de démarrer, prix ~50/50) au lieu du marché en cours de résolution. Corrigé dans `slug_for_end_epoch()` (soustrait `WINDOW_SECONDS`). Avant ce fix, le bot ne voyait jamais les vrais pics de prix proches de la clôture.

### Bug critique corrigé le 23/06 — détection de résolution par seuil de prix peu fiable
`fetch_market_outcome()` marquait un trade comme résolu/gagné dès que le prix affiché par l'API gamma touchait ≥0.99 à un instant donné — un prix qui spike momentanément sans résolution finale (litige UMA, volatilité) aurait pu fausser le résultat. **Corrigé** : la fonction exige désormais `closed=True` ET `umaResolutionStatus=="resolved"` ET un prix exactement 0/1 (pas juste ≥0.99) avant de trancher. Revérification rétroactive des 20 premiers trades réels (21/06-23/06) via ces champs fiables : **tous correctement classés**, aucune erreur trouvée — le ~95% de win rate affiché est donc fiable, pas un artefact de mesure. `list_positions().redeemable` (utilisé dans `redeem_zth.py`) n'est pas adapté à une revérification rétroactive car les positions disparaissent de cette liste une fois réclamées (auto-redeem à chaque cycle).

### Réclamer les gains (`bot/redeem_zth.py`)
Une position gagnante doit être **réclamée (redeem)** pour que les fonds passent de "position résolue" à "espèces" utilisables — ce n'est pas automatique côté Polymarket (bouton "Échanger" sur le site = ça). `SecureClient.redeem_positions()` du SDK officiel ne fonctionne PAS pour un marché déjà clôturé pour deux raisons :
1. Il appelle `list_markets()` sans `closed=True` en interne → ne trouve jamais le marché (`Expected exactly one market... got 0`)
2. Même corrigé, le dispatch de transaction passe par un relayer gasless qui exige une **Builder/Relayer API Key** Polymarket qu'on n'a pas configurée

`redeem_zth.py` contourne ça en construisant et signant nous-mêmes une transaction **Safe `execTransaction`** (le wallet `ZTH_WALLET_ADDRESS` est un Gnosis Safe v1.3.0, signé par l'EOA de `ZTH_PRIVATE_KEY` qui paie le gas en POL — vérifier qu'il a au moins ~0.05 POL). Piège important : l'adresse de contrat à appeler pour `redeemPositions` n'est **pas** `conditional_tokens` mais `context.adapter_address` (= `collateral_adapter` pour un marché non neg-risk, calculé via `normalize_market_position_context`) — appeler le mauvais contrat ne génère aucune erreur mais ne crédite rien (vécu le 21/06, ~$0.001 de gas perdu sans effet). Toujours **simuler via `eth_call` avant de broadcaster** pour vérifier que ça retourne `true`.
**Appelé automatiquement** : `zerotoherobtc.py` importe `redeem_all_resolved()` de `redeem_zth.py` et l'exécute à chaque cycle (`run_cycle()`, uniquement si `ZTH_DRY_RUN=false`) — plus besoin de le lancer à la main, le redeem se fait seul après chaque résolution de marché. Lancement manuel toujours possible si besoin : `source bot/.env && ~/.pyenv/versions/3.11.9/bin/python3 bot/redeem_zth.py` (réclame toutes les positions `redeemable=True` trouvées).

## Sécurité Supabase (audit du 21/06)
- **RLS verrouillé sur 190 tables** — lecture publique autorisée uniquement sur `bot_strategies` et `*_tracking`, tout le reste est privé
- Le backend (`bot/*.py`, `server.py`) utilise désormais `SUPABASE_SERVICE_KEY` (pas la clé anon) — variable d'env à avoir dans `bot/.env`
- **Exception Hetzner** : le bot ZeroToHeroBTC sur Hetzner utilise la clé **anon** (`SUPABASE_KEY`) — des policies RLS d'écriture `anon INSERT/UPDATE` ont été ajoutées sur `zerotoherobtc_trades` et `zerotoherobtc_logs` pour l'autoriser
- **Table `zerotoherobtc_logs`** : logs temps réel envoyés par le bot via `sb_log()` (non-bloquant, threading). Politique : lecture publique + INSERT anon autorisé. Visible dans la page Résultats ZeroToHero du dashboard.
- Le dashboard centralise sa clé Supabase dans `dashboard/api.jsx` (1 source au lieu de 6 copies dispersées) — toujours modifier cette clé là, pas dans les fichiers page_*.jsx

## Architecture Polymarket SDK (important — a changé en 2026)
- **Ancien SDK** : `py-clob-client` (archivé mai 2026) — ne fonctionne plus (CTF Exchange V2 incompatible)
- **Nouveau SDK** : `polymarket-client` (SecureClient) — exige Python 3.10+
- **trader.py** utilise `SecureClient.create(private_key, wallet, credentials)` pour placer les ordres
- **wallet** = adresse proxy Safe Polymarket : `0xb53bbf2D1D5e0d2fEec24c31F2BF03C7B1E5168d` (WALLET_ADDRESS dans .env)
- **credentials** = ApiKeyCreds(apiKey, secret, passphrase) — API_KEY régénéré avec nonce=1
- **derive_api_key.py** : script pour régénérer les credentials via EIP-712 L1 auth si expirés

## Bot Température Multi-Villes (actif sur Railway 24/7)
- **Script** : `bot/agent_temperature_cloud.py` (lancé via `Procfile`)
- **Railway** : projet `lucid-encouragement`, service `BotTradingV2`
- **Seuil signal** : YES ≥ 75%
- **Scan** : toutes les 15 min, J+0 si encore ouvert sinon J+1
- **Slug Polymarket** : `highest-temperature-in-{city}-on-{month}-{day}-{year}`
- **Tables Supabase par ville** (45 villes) :
  - `{ville_id}_tracking` — signaux détectés (condition_id UNIQUE, yes_price_au_signal, resultat…)
  - `{ville_id}_stats` — stats cumulatives long terme (taux_victoire, gagnes, resolus… ne reculent jamais)
  - `{ville_id}_rapports` — rapport à chaque cycle (purge auto à 3 jours / 288 entrées)
  - `{ville_id}_resumes` — résumé Mistral quotidien (1 par jour, gardé indéfiniment)
- **Tables globales** : `strategie_analyses`, `strategie_config`, `bot_status`
- **Purge automatique** :
  - `_rapports` : 3 jours (288 entrées max)
  - `_tracking` : signaux résolus >30 jours supprimés
  - `_stats` : compteurs cumulatifs préservés (jamais recalculés à zéro)

## Ajouter une nouvelle ville
1. Vérifier le slug Polymarket : `highest-temperature-in-{city}-on-...`
2. Ajouter dans `VILLES` de `agent_temperature_cloud.py`
3. Ajouter dans `_WEATHER_VILLES` de `brain.py`
4. Ajouter bot dans `dashboard/data.jsx` avec `type:'temperature'`, `citySlug`, `flag`, `glyph`
5. Ajouter ville dans `VILLES` de `dashboard/page_stratege.jsx`
6. Créer 4 tables Supabase (via MCP Supabase ou SQL) avec le schéma standard

## Trading réel — ACTIF ✅
- `DRY_RUN=false` dans `bot/.env`
- Lancer : `source bot/.env && ~/.pyenv/versions/3.11.9/bin/python3 bot/loop_v2.py`
- Premier ordre réel : Toronto 31°C YES — 10 USDC → 10.64 tokens, tx `0xdfb26ab1...` (2026-06-11)
- Performance V2 (au 2026-06-16) : ~75% win rate, ~17+ trades, -$0.34 net (perte principale : Dallas 97¢ — corrigé)
- **Reset stats le 2026-06-17 15:34** (`PERF_RESET_DATE`) : le calendrier P&L et les stats affichées dans les logs/dashboard ne comptent que les trades à partir de cette date (positions précédentes ignorées dans les compteurs, mais toujours en DB)

## Dashboard — page Calendrier (`page_calendar.jsx`)
- Nouvelle page accessible depuis la sidebar (`nav.page === 'calendar'`, icône `calendar-days`)
- Affiche le P&L jour par jour de ProfitWeather V2 depuis `PERF_RESET_DATE`
- Données via `fetchCalendarData()` (`api.jsx`) → `GET /api/v2/calendar` (`server.py`) → groupe `trade_history` (bot_id=`polyedge2`) par jour : pnl, wins, losses, trades ouverts
- Il existe aussi `GET /api/v2/trades` pour la liste brute des trades récents (même filtre `PERF_RESET_DATE`)

## Si les credentials API Polymarket expirent
Lancer : `~/.pyenv/versions/3.11.9/bin/python3 bot/derive_api_key.py`
→ Affiche les nouvelles valeurs API_KEY / API_SECRET / API_PASSPHRASE à coller dans `.env`
(utilise EIP-712 L1 auth + nonces 0→4 pour trouver un slot libre)

## Dashboard — page ProfitWeather (`page_bot.jsx`, bot.id === 'polyedge')
- Onglet **Stratégie** : schéma visuel 7 étapes en haut (processus de décision), puis stratégie en lecture seule
- La stratégie s'affiche depuis Supabase (`bot_strategies`) — **pas de textarea éditable** pour polyedge
- Le toggle "Activer ProfitWeather" sauvegarde directement dans Supabase (pas de bouton Sauvegarder)
- Les autres bots (Crypto, etc.) gardent la textarea éditable avec les exemples génériques

## Améliorations futures identifiées (par ordre de priorité)
1. **Température en temps réel US** — stations NWS/ASOS, update horaire : temp actuelle + tendance → savoir si le marché J+0 est déjà "gagné"
2. **Temps restant avant clôture du marché** — NO à 90¢ avec 2h restantes ≠ 14h restantes
3. **Analyse ranges adjacents** — si 74-75°F ET 76-77°F ET 78-79°F sont tous NO>90% pour la même ville → signal très fort
4. **Historique résolutions Polymarket** — taux de résolution passé par ville + fourchette

## Scripts utilitaires ponctuels (bot/)
- **`close_all.py`** : ferme manuellement toutes les positions ouvertes polyedge2 (utile si on veut tout liquider à la main — mais voir note SDK ne supporte pas la vente, donc ce script peut échouer pour les positions encore actives)
- **`fetch_wu_stations.py`** : scrape les vraies stations Weather Underground depuis les descriptions de marchés Polymarket (`gamma-api.polymarket.com/events`) → écrit `wu_stations.json` → a servi à corriger les codes ICAO dans `weather_validator.py` (ex: Paris LFPG→LFPB, London EGLL→EGLC)
- **`test_order.py`** : script ponctuel de test d'ordre direct via `SecureClient` (hors boucle), garder comme référence si les credentials API doivent être re-testés manuellement
- **`STRATEGIE_BOT.md`** : explication complète de la stratégie en langage simple (sans jargon code) pour l'utilisateur — à tenir à jour en parallèle de cette section si les règles changent significativement

## Préférences utilisateur
- L'utilisateur ne code pas — expliquer simplement
- Toujours tester en local avant de déclarer terminé
- Bot actif principal : `agent_temperature_cloud.py` sur Railway
- ProfitWeather V2 (`loop_v2.py`) tourne en local avec agent_deko.py en parallèle
- **ZeroToHeroBTC tourne 24/7 sur Hetzner** (IP `178.105.136.96`, Allemagne) — pas de VPN nécessaire depuis Hetzner
- VPN requis uniquement pour les ordres Polymarket **depuis la France en local** (CLOB API géobloké pour les IPs françaises et AWS)
