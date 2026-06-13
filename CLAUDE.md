# TradingBot V2 — Instructions pour Claude

## Ce que fait ce projet
Bot de trading autonome sur **Polymarket** (marchés de prédiction) avec dashboard iOS-style.
- **ProfitWeather** : bot de trading météo — Claude Haiku décide quoi acheter selon les signaux des bots d'analyse
- **Agent météo multi-villes** : 42 bots d'analyse qui trackent les options YES >75% sur les marchés température
- **Stratège Mistral** : analyse cross-ville toutes les 15 min, apprend des analyses passées

## Structure du projet
```
Bottrading V2/
├── dashboard/          ← Frontend web (HTML/CSS/JSX, React via CDN) → Vercel
│   ├── index.html
│   ├── styles.css
│   ├── app.jsx         ← Shell, navigation, sidebar avec drapeaux pays
│   ├── api.jsx         ← Fetch données réelles depuis localhost:5000
│   ├── data.jsx        ← 42 bots température + ProfitWeather + Crypto
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
│   ├── brain.py        ← Claude Haiku : décide quoi trader, lit les signaux Supabase
│   ├── trader.py       ← Exécution ordres (DRY_RUN=true par défaut)
│   ├── loop.py         ← Boucle ProfitWeather toutes les 15 min (local)
│   ├── server.py       ← Flask API port 5000
│   ├── agent_temperature_cloud.py ← 42 villes, Railway 24/7 ← ACTIF
│   ├── strategy.json   ← Stratégie ProfitWeather (ignoré par git, local)
│   ├── history.json    ← Historique trades (ignoré par git, local)
│   ├── requirements.txt
│   └── .env            ← Toutes les clés (jamais committé)
├── Procfile            ← Railway : python3 bot/agent_temperature_cloud.py
├── requirements.txt    ← Dépendances Railway
└── scripts/
    ├── Lancer le dashboard.command
    ├── Lancer le bot.command
    └── Lancer la stratégie.command  ← Lance ProfitWeather (loop.py)
```

## Lancer le projet
```bash
# Dashboard local
cd dashboard && python3 -m http.server 8080   # → http://localhost:8080

# Serveur bot (données temps réel dashboard)
python3 bot/server.py                          # → http://localhost:5000

# ProfitWeather — simulation
python3 bot/loop.py
```
Ou double-cliquer sur les fichiers dans `scripts/`.

## Conventions frontend
- React 18 via CDN, Babel transpile JSX dans le navigateur, **aucun build**
- Composants exposés sur `window` (ex. `window.BotPage`)
- Styles inline React partout (pas de classes CSS sauf layout global)
- Variables CSS : `var(--accent)`, `var(--green)`, `var(--text)`, `var(--fill)`…
- Dashboard déployé sur **Vercel** (auto-deploy depuis GitHub)

## État actuel
- ✅ Dashboard iOS complet — Vercel, auto-deploy GitHub
- ✅ **42 villes actives** :
  - Chengdu 🇨🇳, Séoul 🇰🇷, Hong Kong 🇭🇰, NYC 🇺🇸, Londres 🇬🇧, Tokyo 🇯🇵, Atlanta 🇺🇸, Seattle 🇺🇸, Miami 🇺🇸, Singapour 🇸🇬, Madrid 🇪🇸, Shanghai 🇨🇳, Los Angeles 🇺🇸, Guangzhou 🇨🇳, Mexico City 🇲🇽, Amsterdam 🇳🇱, Paris 🇫🇷, Toronto 🇨🇦, Chicago 🇺🇸, Denver 🇺🇸, Houston 🇺🇸, Taipei 🇹🇼, Beijing 🇨🇳, San Francisco 🇺🇸, Dallas 🇺🇸
  - Wellington 🇳🇿, Chongqing 🇨🇳, Wuhan 🇨🇳, Ankara 🇹🇷, Moscou 🇷🇺, Lucknow 🇮🇳, Istanbul 🇹🇷, Varsovie 🇵🇱, Milan 🇮🇹, Helsinki 🇫🇮, Karachi 🇵🇰, Cape Town 🇿🇦, Jeddah 🇸🇦, Shenzhen 🇨🇳, Busan 🇰🇷, Qingdao 🇨🇳, Kuala Lumpur 🇲🇾
- ✅ **ProfitWeather** (id: `polyedge`) — bot de trading local, **DRY_RUN=false (TRADING RÉEL)**
- ✅ **Mistral Stratège** — analyse cross-ville toutes les 15 min (Railway)
- ✅ Toutes les clés dans `bot/.env` : ANTHROPIC, POLYMARKET (PRIVATE_KEY, API_KEY, API_SECRET, API_PASSPHRASE), SUPABASE, MISTRAL
- ✅ `can_trade: True` — clés Polymarket valides (API_KEY régénéré avec nonce=1 en juin 2026)
- ✅ **DRY_RUN=false** — trading réel activé (premier ordre Toronto 31°C le 2026-06-11)
- ✅ Résolution marchés : lit `/events` pour vrai prix (fix CLOB bloqué à 51%), fallback Open-Meteo
- ✅ **Python 3.11.9** via pyenv installé (`~/.pyenv/versions/3.11.9/`) — requis pour trader.py
- ✅ **trader.py** utilise le nouveau SDK `polymarket-client` (SecureClient) — CTF Exchange V2

## ProfitWeather — Bot de trading (local)
- **Script** : `bot/loop.py` (lancé via `scripts/Lancer la stratégie.command`)
- **Python** : `~/.pyenv/versions/3.11.9/bin/python3` — OBLIGATOIRE (trader.py exige Python 3.11+)
- **Cerveau** : Claude Haiku (`brain.py`) — lit les signaux Supabase + décide
- **Exécution ordres** : `trader.py` → `polymarket-client` SecureClient (CTF Exchange V2)
- **Stratégie** : acheter YES sur marchés météo où les bots d'analyse ont détecté signal ≥75%
- **Marchés** : `polymarket.get_weather_markets()` — construit les slugs J+0/J+1 par ville, interroge l'API events Polymarket
- **Contexte Claude** : `_load_analysis_context()` lit depuis Supabase :
  - `strategie_analyses` — dernière analyse Mistral cross-ville
  - `{ville}_stats` — taux de réussite par ville
  - `{ville}_tracking` WHERE resultat IS NULL — signaux actifs
- **Cycle** : toutes les 5 min, auto-amélioration de stratégie toutes les 6h
- **Persistance** : `strategy.json` + `history.json` (fichiers locaux, ignorés par git)
- **DRY_RUN=false** — trading réel actif depuis le 2026-06-11

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
- **Tables Supabase par ville** (42 villes) :
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
- Double-cliquer sur `scripts/Lancer la stratégie.command` (utilise Python 3.11.9)
- Premier ordre réel : Toronto 31°C YES — 10 USDC → 10.64 tokens, tx `0xdfb26ab1...` (2026-06-11)

## Si les credentials API Polymarket expirent
Lancer : `~/.pyenv/versions/3.11.9/bin/python3 bot/derive_api_key.py`
→ Affiche les nouvelles valeurs API_KEY / API_SECRET / API_PASSPHRASE à coller dans `.env`
(utilise EIP-712 L1 auth + nonces 0→4 pour trouver un slot libre)

## Préférences utilisateur
- L'utilisateur ne code pas — expliquer simplement
- Toujours tester en local avant de déclarer terminé
- Bot actif principal : `agent_temperature_cloud.py` sur Railway
- ProfitWeather tourne en local (pas encore sur Railway)
