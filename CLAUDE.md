# TradingBot V2 — Instructions pour Claude

## Ce que fait ce projet
Bot de trading autonome sur **Polymarket** (marchés de prédiction) avec dashboard iOS-style.
- **ProfitWeather V2** : bot de trading météo — Claude Haiku décide quoi acheter (stratégie NO sur fourchettes température)
- **Agent Deko** : surveille les trades de sailor82 en temps réel pour générer des signaux bonus
- **Agent météo multi-villes** : 45 bots d'analyse qui trackent les options YES >75% sur les marchés température
- **Stratège Mistral** : analyse cross-ville toutes les 15 min, apprend des analyses passées

## Structure du projet
```
Bottrading V2/
├── dashboard/          ← Frontend web (HTML/CSS/JSX, React via CDN) → Vercel
│   ├── index.html
│   ├── styles.css
│   ├── app.jsx         ← Shell, navigation, sidebar avec drapeaux pays
│   ├── api.jsx         ← Fetch données réelles depuis localhost:5000
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
│   └── page_history.jsx
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
│   ├── weather_validator.py ← Enrichissement ECMWF (band_prob, models_spread, models_avg)
│   ├── server.py       ← Flask API port 5000
│   ├── agent_temperature_cloud.py ← 45 villes, Railway 24/7 ← ACTIF
│   ├── derive_api_key.py ← Régénère credentials Polymarket si expirés
│   ├── requirements.txt
│   └── .env            ← Toutes les clés (jamais committé)
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
python3 bot/server.py                          # → http://localhost:5000

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
MIN_NO_PRICE      = 0.70    # NO minimum 70¢
MAX_NO_PRICE      = 0.95    # NO maximum 95¢ (leçon Dallas : 97¢ = marge trop faible)
MAX_EXPOSURE_PCT  = 1.0     # 100% du solde peut être exposé simultanément
MAX_BET_PCT       = 0.06    # jamais plus de 6% du solde sur 1 trade
MIN_FORECAST_GAP  = 3.0     # écart minimum °F entre prévision et fourchette
MAX_ENSEMBLE_PROB = 40      # si ECMWF prédit >40% dans ce range → interdit
MAX_BAND_PROB     = 30      # band_prob max (None = données absentes = refus)
MAX_MODELS_SPREAD = 12.0    # si modèles ECMWF divergent >12°F → trop incertain
MIN_VOLUME        = 1_000   # volume minimum USDC
NO_STOP_LOSS_PCT  = -0.25   # -25% → vente automatique
NO_TAKE_PROFIT    = 0.9999  # NO ≥ 99.99¢ → lock profit
```

### Règles de trading V2
- **NO uniquement** — pas de YES (trop complexe, focus sur ce qui marche)
- **1 trade max par ville par cycle** — `traded_cities` set réinitialisé à chaque cycle
- **1 trade max par ville en position ouverte** — `open_cities` bloqué dans `_prefilter`
- **Signal Deko** : consultatif uniquement — Claude analyse avant de décider. Si sailor82 est NO sur le même marché → boost de certitude d'un niveau (low→medium, medium→high)
- **Double vérification prix** : T1 puis T2 (4s après) — annulé si prix chute >2¢ entre les deux

## Agent Deko (`agent_deko.py`)
- **But** : surveiller les trades de sailor82 (@sailor82, Polymarket, addr `0xbbb72a812c…`)
- **Cycle** : toutes les 15 min
- **API** : `data-api.polymarket.com/activity?user=...` (type `TRADE`, pas `BUY`)
- **Tables Supabase** :
  - `deko_trades` : chaque trade détecté (tx_hash UNIQUE, outcome, city, range, price, amount_usdc, certainty, hour_et…)
  - `deko_stats` : stats cumulatives (win rate, P&L, distribution par ville/heure)
  - `deko_rapports` : analyses Mistral périodiques
- **Bug corrigé** : l'API retourne `type=TRADE` pas `type=BUY` — le filtre était `not in ("BUY",)` → corrigé en `not in ("BUY", "TRADE")`
- **Stratégie de sailor82 observée** : NO à 84-96¢ sur NYC, Houston, SF, LA, Austin, Seattle + YES spéculatifs à 38-48¢ (Atlanta, Austin, SF) — mise $7-$130 par trade

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

## Préférences utilisateur
- L'utilisateur ne code pas — expliquer simplement
- Toujours tester en local avant de déclarer terminé
- Bot actif principal : `agent_temperature_cloud.py` sur Railway
- ProfitWeather V2 (`loop_v2.py`) tourne en local avec agent_deko.py en parallèle
- VPN requis pour les ordres Polymarket depuis la France (CLOB API géobloké)
