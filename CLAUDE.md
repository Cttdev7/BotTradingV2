# TradingBot V2 — Instructions pour Claude

## Ce que fait ce projet
Bot de trading autonome sur **Polymarket** (marchés de prédiction) avec dashboard iOS-style.
- **ProfitWeather V2** : bot de trading météo — Claude Haiku décide quoi acheter (stratégie NO sur fourchettes température), tourne en local
- **ProfitWeather V3** : achat YES précoce (≤15¢) à l'ouverture des marchés + revente si divergence météo/stop-loss — même compte que le V2 (partage le solde, plafond 50/50), tourne 24/7 sur **Fly.io Toronto (`yyz`)** — DRY_RUN depuis le 01/07/2026
- **Copy-trade sailor82** : copie les positions température de sailor82, analyse avec Claude Haiku + météo Open-Meteo, tourne 24/7 sur **Fly.io Toronto (`yyz`)** — DRY_RUN depuis le 30/06/2026

## Structure du projet
```
Bottrading V2/
├── dashboard/          ← Frontend web (HTML/CSS/JSX, React via CDN) → Vercel
│   ├── index.html
│   ├── styles.css
│   ├── app.jsx         ← Shell, navigation, sidebar
│   ├── api.jsx         ← Fetch données réelles depuis localhost:5050
│   ├── data.jsx        ← bots : polyedge, polyedge2
│   ├── charts.jsx
│   ├── icons.jsx
│   ├── ui.jsx
│   ├── tweaks-panel.jsx
│   ├── page_dashboard.jsx
│   ├── page_bot.jsx    ← ProfitWeather V1 et V2 (onglets Aperçu + Stratégie)
│   ├── page_portfolio.jsx
│   ├── page_settings.jsx
│   ├── page_history.jsx
│   └── page_calendar.jsx       ← Calendrier P&L ProfitWeather V2 (depuis PERF_RESET_DATE)
├── bot/                ← Backend Python
│   ├── config.py       ← Charge .env
│   ├── auth.py         ← Signature HMAC-SHA256
│   ├── polymarket.py   ← API Polymarket + get_weather_markets()
│   ├── pm_api.py       ← Alias/wrapper polymarket.py utilisé par loop_v2.py
│   ├── brain.py        ← Claude Haiku : décide quoi trader (ProfitWeather V2)
│   ├── trader.py       ← Exécution ordres (DRY_RUN=true par défaut)
│   ├── loop_v2.py      ← ⭐ ProfitWeather V2 — stratégie NO, ACTIF en local
│   ├── loop_v3.py      ← ⭐ ProfitWeather V3 — achat YES précoce, Fly.io app profitweather-v3
│   ├── backtest_weather_sources.py ← Backtest précision Open-Meteo/ECMWF/GFS/ICON/MeteoFrance
│   ├── copy_sailor82.py ← ⭐ Copy-trade sailor82 — Fly.io app sailor82-copy
│   ├── weather_validator.py ← Enrichissement ECMWF (band_prob, models_spread, models_avg) + stations METAR/WU
│   ├── server.py       ← Flask API port 5050 (/api/v2/trades, /api/v2/calendar) — pas 5000 (AirPlay bloque)
│   ├── postmortem.py   ← Analyse post-mortem des trades perdants
│   ├── derive_api_key.py ← Régénère credentials Polymarket si expirés
│   ├── close_all.py    ← Ferme manuellement toutes les positions ouvertes polyedge2
│   ├── fetch_wu_stations.py ← Scrape les codes stations WU depuis les descriptions de marchés
│   ├── wu_stations.json ← Cache des stations WU scrapées
│   ├── test_order.py   ← Test ponctuel d'ordre via SecureClient
│   └── .env            ← Toutes les clés (jamais committé)
├── fly-sailor82.toml   ← Config Fly.io app sailor82-copy (Toronto yyz, 256mb)
├── fly-profitweather-v3.toml ← Config Fly.io app profitweather-v3 (Toronto yyz, 256mb)
├── Dockerfile.sailor82 ← Image Docker pour sailor82-copy
├── Dockerfile.profitweather-v3 ← Image Docker pour profitweather-v3
├── requirements-zth.txt ← Dépendances Fly.io partagées (sans polymarket-client, installé séparément)
├── STRATEGIE_BOT.md    ← Doc stratégie V2 en langage simple
├── STRATEGIE_PROFITWEATHER_V3.md ← Doc stratégie V3 en langage simple
└── scripts/
    ├── Lancer le dashboard.command
    └── Lancer le bot.command
```

## Lancer le projet
```bash
# Dashboard local
cd dashboard && python3 -m http.server 8080   # → http://localhost:8080

# Serveur bot (données temps réel dashboard)
python3 bot/server.py                          # → http://localhost:5050

# ProfitWeather V2 — TRADING RÉEL
source bot/.env && ~/.pyenv/versions/3.11.9/bin/python3 bot/loop_v2.py
```

## Conventions frontend
- React 18 via CDN, Babel transpile JSX dans le navigateur, **aucun build**
- Composants exposés sur `window` (ex. `window.BotPage`)
- Styles inline React partout (pas de classes CSS sauf layout global)
- Variables CSS : `var(--accent)`, `var(--green)`, `var(--text)`, `var(--fill)`…
- Dashboard déployé sur **Vercel** (auto-deploy depuis GitHub)

## État actuel (au 01/07/2026)
- ✅ Dashboard iOS — Vercel, auto-deploy GitHub (nettoyé : plus de pages météo/deko/stratège)
- ✅ **ProfitWeather V2** (`loop_v2.py`) — bot NO sur fourchettes température, **DRY_RUN=false**, `MAX_EXPOSURE_PCT=0.5` (partage le compte avec le V3)
- ✅ **ProfitWeather V3** (`loop_v3.py`) — achat YES précoce, Fly.io `profitweather-v3`, **DRY_RUN=true depuis 01/07/2026**
- ✅ **Copy-trade sailor82** (`copy_sailor82.py`) — Fly.io `sailor82-copy`, **DRY_RUN=true depuis 30/06 22:10 CEST**
- ❌ **ZeroToHeroBTC** décommissionné le 01/07/2026 — pertes récurrentes (~-25$ sur 2h, win rate 73% insuffisant vs ~92% requis) + bug stop-loss qui ne s'exécutait pas. App Fly.io `zth-bot` supprimée, code retiré
- ✅ Toutes les clés dans `bot/.env` : ANTHROPIC, POLYMARKET (PRIVATE_KEY, API_KEY, API_SECRET, API_PASSPHRASE), SUPABASE
- ✅ `can_trade: True` — clés Polymarket valides (API_KEY régénéré avec nonce=1 en juin 2026)
- ✅ **Python 3.11.9** via pyenv (`~/.pyenv/versions/3.11.9/`) — requis pour trader.py et loop_v2.py
- ✅ **trader.py** utilise le nouveau SDK `polymarket-client` (SecureClient) — CTF Exchange V2

## ProfitWeather V2 — Bot de trading (local)
- **Script** : `bot/loop_v2.py`
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
MAX_EXPOSURE_PCT      = 0.5     # 50% du portefeuille peut être exposé (V3 partage le compte, plafond 50/50)
MAX_BET_PCT           = 0.05    # jamais plus de 5% du solde sur 1 trade
MIN_FORECAST_GAP_DOWN = 2.0     # range EN-DESSOUS prévision → 2°F suffisent
MIN_FORECAST_GAP_UP   = 8.0     # range AU-DESSUS prévision → 8°F minimum
MAX_ENSEMBLE_PROB     = 30      # ECMWF >30% dans ce range → interdit
MAX_BAND_PROB         = 20      # band_prob max
MAX_MODELS_SPREAD     = 10.0    # modèles ECMWF divergent >10°F → trop incertain
MIN_VOLUME            = 1_500   # volume minimum USDC
NO_STOP_LOSS_PCT      = -0.50   # -50% → déclenche hedge/post-mortem
NO_TAKE_PROFIT        = 0.99    # NO ≥ 99¢ → vend et lock profit
CASCADE_TRIGGER       = 0.35    # range YES dominant >35% → cascade NO adjacents
HEDGE_YES_TRIGGER     = 0.60    # YES ≥ 60% sur notre NO perdant → auto-hedge YES
HEDGE_MULTIPLIER      = 1.10    # mise hedge pour +10% si YES gagne
PERF_RESET_DATE       = "2026-06-17T15:34:00"  # stats repartent à 0 ici
```

### Règles de trading V2
- **NO uniquement** — pas de YES
- **1 trade max par ville par cycle** — `traded_cities` set réinitialisé à chaque cycle
- **1 trade max par ville en position ouverte** — `open_cities` bloqué dans `_prefilter`
- **Double vérification prix** : T1 puis T2 (4s après) — annulé si prix chute >2¢
- **Règle directionnelle** :
  - Range EN-DESSOUS de la prévision → autorisé (2°F gap min)
  - Range AU-DESSUS de la prévision → **toujours BLOQUÉ**, sauf si "pic METAR confirmé"
- **Signal "pic METAR confirmé"** : température a baissé depuis son max du jour → max verrouillé → trade immédiat autorisé même sur range au-dessus
- **Cascade** : si range YES > 35% → ranges adjacents reçoivent signal NO automatique
- **Auto-hedge** : si NO perdant avec YES en face entre 60-90% → achète YES pour ressortir neutre/+10%
- **Stations WU exactes** : London=EGLC, Paris=LFPB, NYC=KLGA, Dallas=KDAL, Denver=KBKF, Seoul=RKSI, Taipei=RCSS, Milan=LIMC

## ProfitWeather V3 (`bot/loop_v3.py`)
Doc complète en langage simple : `STRATEGIE_PROFITWEATHER_V3.md`

- **But** : acheter YES très tôt (dès la création du marché, prix ≤15¢) sur la fourchette la plus proche de la prévision, revendre en cours de journée si la fourchette est compromise. Opposé au V2 (qui achète NO tard et cher) — objectif ~60% de réussite mais gains asymétriques (petites pertes, gros gains)
- **Source de prévision** : Open-Meteo blend (sans modèle spécifique) — retenue après backtest (`backtest_weather_sources.py`) contre ECMWF/GFS/ICON/MeteoFrance sur ~180 marchés résolus, toutes villes. Best hit-rate + MAE le plus bas, net sur les villes US (25% hit rate, MAE 1.66°F)
- **Source de résolution (surveillance)** : station officielle extraite du champ `resolutionSource` de chaque event Gamma API (ex: `.../history/daily/us/ny/new-york-city/KLGA` → station `KLGA`) — auto-détection générique, pas de liste figée
- **Détection** : scan toutes les 90s, 45 villes × **J+2 uniquement** (`NEW_MARKET_DAY_OFFSET=2`) — vérifié empiriquement le 01/07/2026 : Polymarket crée les marchés température ~2 jours avant l'échéance (~4h-5h UTC), donc J+0/J+1 ont déjà 1-2 jours de trading, trop tard pour la fenêtre de prix bas
- **Max 2 nouveaux achats par cycle** (`MAX_TRADES_PER_CYCLE=2`) — évite qu'une rafale d'opportunités simultanées engage tout le plafond de 50% d'un coup
- **Deux boucles séparées** : détection toutes les 90s (thread principal) + surveillance des positions ouvertes **toutes les 1s** (thread dédié, `MONITOR_INTERVAL=1`) — une position achetée est trackée en continu jusqu'à sa clôture, indépendamment du cycle de scan
- **Sortie anticipée** :
  - Stop-loss prix : -30% depuis l'achat (vérifié chaque seconde)
  - Divergence météo : le relevé METAR officiel dépasse la borne haute de la fourchette, ou le pic du jour est passé (temp en baisse depuis le max, après 18h locale) sans avoir atteint la borne basse (cache 60s sur l'appel METAR — une station ne se met à jour que toutes les 20-60 min, inutile de la rappeler chaque seconde)
- **Compte Polymarket** : même que ProfitWeather V2 — partage le solde, plafond **50% chacun** (`MAX_EXPOSURE_PCT=0.5` dans les deux bots)
- **Mise par trade** : max 10% du capital alloué au V3 (= 5% du solde total)
- **Suivi de précision météo** : table `profitweather_v3_forecast_log` — chaque prévision faite à la détection (achetée ou non) est loggée puis réconciliée avec le résultat réel une fois le marché résolu (`check_forecast_accuracy()`, appelé chaque cycle de scan). Corrige la limite du premier backtest (`backtest_weather_sources.py`) qui ne pouvait pas vraiment mesurer la fiabilité à horizon J+2 (Open-Meteo ne conserve pas ses prévisions passées, donc impossible de tester rétroactivement — il faut le mesurer en avançant dans le temps)
- **Persistance** : table Supabase `profitweather_v3_trades` (upsert sur `condition_id` — un marché "prix trop haut" reste rechecké aux cycles suivants, contrairement aux statuts terminaux comme `open`/`skipped_confidence`)
- **Statut** : DRY_RUN depuis le 01/07/2026, actuellement **à l'arrêt** (machine Fly.io stoppée) en attendant le feu vert pour relancer. 32 prévisions déjà loggées dans `profitweather_v3_forecast_log` (target_date 2026-07-03) — à vérifier automatiquement une fois ces marchés résolus

### Déploiement Fly.io — profitweather-v3
- **App** : `profitweather-v3` → fly.io/apps/profitweather-v3 | région `yyz` (Toronto)
- **Logs** : `/Users/clementctt/.fly/bin/fly logs --app profitweather-v3`
- **Redéployer** : `cd "Bottrading V2" && /Users/clementctt/.fly/bin/fly deploy --app profitweather-v3 --config fly-profitweather-v3.toml`
- **Passer en réel** : `/Users/clementctt/.fly/bin/fly secrets set V3_DRY_RUN=false --app profitweather-v3`
- **Config** : `fly-profitweather-v3.toml` + `Dockerfile.profitweather-v3` + `requirements-zth.txt`

## Copy-trade sailor82 (`bot/copy_sailor82.py`)
- **But** : copier les positions température de sailor82 (addr `0xbbb72a812cfbc5217d77c0a0018c71f174d3a11a`)
- **Cycle** : toutes les 2.5 min — poll `/positions` de sailor82
- **Filtre** : marchés température uniquement (titre contient "temperature")
- **Météo** : Open-Meteo pour la ville/date → température prévue en °F
- **Analyse** : Claude Haiku analyse le trade (reasoning + confidence 1-5) avant de décider
- **Mise** : 10% de la mise de sailor82, min $5, max $20
- **Dérive prix** : skip si prix actuel a bougé de plus de 5¢ depuis l'entrée de sailor82
- **Confiance min** : 2/5 — en dessous, trade ignoré
- **Compte Polymarket** : même que ProfitWeather V2 (PRIVATE_KEY, WALLET_ADDRESS, API_KEY…)
- **Persistance** : table Supabase `copy_sailor82_trades` (condition_id, title, outcome, sailor_price, our_price, forecast_temp, analysis, confidence, status)
- **Status** : DRY_RUN=true depuis le 30/06/2026 22:10 CEST — bilan J+1 à faire le 01/07/2026

### Déploiement Fly.io — sailor82-copy
- **App** : `sailor82-copy` → fly.io/apps/sailor82-copy | région `yyz` (Toronto)
- **Logs** : `/Users/clementctt/.fly/bin/fly logs --app sailor82-copy`
- **Redéployer** : `cd "Bottrading V2" && /Users/clementctt/.fly/bin/fly deploy --app sailor82-copy --config fly-sailor82.toml`
- **Passer en réel** : `/Users/clementctt/.fly/bin/fly secrets set COPY_DRY_RUN=false --app sailor82-copy`
- **Config** : `fly-sailor82.toml` + `Dockerfile.sailor82` + `requirements-zth.txt`

## Sécurité Supabase (audit du 21/06)
- **RLS verrouillé** — lecture publique uniquement sur `bot_strategies` et `*_tracking`
- Le backend utilise `SUPABASE_SERVICE_KEY` (pas la clé anon) — variable dans `bot/.env`
- **Table `copy_sailor82_trades`** : trades copiés de sailor82, accès service uniquement
- Le dashboard centralise sa clé Supabase dans `dashboard/api.jsx` — toujours modifier là

## Architecture Polymarket SDK (important — a changé en 2026)
- **Ancien SDK** : `py-clob-client` (archivé mai 2026) — ne fonctionne plus (CTF Exchange V2 incompatible)
- **Nouveau SDK** : `polymarket-client` (SecureClient) — exige Python 3.10+
- **trader.py** utilise `SecureClient.create(private_key, wallet, credentials)` pour placer les ordres
- **wallet** = adresse proxy Safe Polymarket : `0xb53bbf2D1D5e0d2fEec24c31F2BF03C7B1E5168d` (WALLET_ADDRESS dans .env)
- **credentials** = ApiKeyCreds(apiKey, secret, passphrase) — API_KEY régénéré avec nonce=1
- **derive_api_key.py** : régénère les credentials via EIP-712 L1 auth si expirés

## Trading réel — ACTIF ✅
- `DRY_RUN=false` dans `bot/.env`
- Lancer : `source bot/.env && ~/.pyenv/versions/3.11.9/bin/python3 bot/loop_v2.py`
- Premier ordre réel : Toronto 31°C YES — 10 USDC → 10.64 tokens, tx `0xdfb26ab1...` (2026-06-11)
- **Reset stats le 2026-06-17 15:34** (`PERF_RESET_DATE`) : les stats/calendrier ne comptent que les trades depuis cette date

## Dashboard — page Calendrier (`page_calendar.jsx`)
- Affiche le P&L jour par jour de ProfitWeather V2 depuis `PERF_RESET_DATE`
- Données via `fetchCalendarData()` → `GET /api/v2/calendar` → groupe `trade_history` (bot_id=`polyedge2`) par jour

## Si les credentials API Polymarket expirent
Lancer : `~/.pyenv/versions/3.11.9/bin/python3 bot/derive_api_key.py`
→ Affiche les nouvelles valeurs API_KEY / API_SECRET / API_PASSPHRASE à coller dans `.env`

## Dashboard — page ProfitWeather (`page_bot.jsx`)
- Onglet **Stratégie** : schéma visuel 7 étapes + stratégie en lecture seule depuis Supabase (`bot_strategies`)
- Le toggle "Activer ProfitWeather" sauvegarde directement dans Supabase (pas de bouton Sauvegarder)

## Bots supprimés
- **Agent Deko** (`agent_deko.py`) — remplacé par copy_sailor82.py plus direct (30/06/2026)
- **Agent température multi-villes** (`agent_temperature_cloud.py`) — 45 bots d'analyse Railway (30/06/2026)
- **Mistral Stratège** — analyse cross-ville (plus utilisé) (30/06/2026)
- **Pages dashboard** supprimées : `page_stratege.jsx`, `page_deko.jsx`, `page_luck.jsx` (30/06/2026)
- **Services Railway** arrêtés : `fabulous-perception` (deko), `BotTradingV2` (température) (30/06/2026)
- **ZeroToHeroBTC** (`zerotoherobtc.py`, `redeem_zth.py`, `zth_stats.py`) — décommissionné le 01/07/2026 : pertes récurrentes (~-25$ sur 2h, win rate 73% insuffisant vs ~92% requis) + bug stop-loss qui ne s'exécutait pas (`shares is required for SELL market orders`). App Fly.io `zth-bot` détruite, `fly.toml`/`Dockerfile`/`Procfile`/`page_zerotohero_results.jsx` retirés. Focus reporté sur ProfitWeather V3

## Améliorations futures identifiées
1. ~~YES à l'ouverture de marché~~ — implémenté dans ProfitWeather V3 (`loop_v3.py`, 01/07/2026)
2. **Température en temps réel US** — stations NWS/ASOS pour savoir si le marché J+0 est déjà "gagné"
3. **Temps restant avant clôture** — NO à 90¢ avec 2h restantes ≠ 14h restantes
4. **Page dashboard copy-trade** — afficher les trades copiés de sailor82 + analyse Haiku

## Préférences utilisateur
- L'utilisateur ne code pas — expliquer simplement
- Toujours tester en local avant de déclarer terminé
- ProfitWeather V2 (`loop_v2.py`) tourne en local
- ProfitWeather V3 et copy-trade sailor82 tournent 24/7 sur Fly.io Toronto
- VPN requis uniquement pour les ordres Polymarket **depuis la France en local** (CLOB API géobloké pour les IPs françaises)
