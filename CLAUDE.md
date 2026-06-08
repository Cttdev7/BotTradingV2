# TradingBot V2 — Instructions pour Claude

## Ce que fait ce projet
Bot de trading autonome sur **Polymarket** (marchés de prédiction) avec dashboard iOS-style.
- **ProfitWeather** : bot de trading météo — Claude Haiku décide quoi acheter selon les signaux des bots d'analyse
- **Agent météo multi-villes** : 12 bots d'analyse qui trackent les options YES >75% sur les marchés température
- **Stratège Mistral** : analyse cross-ville quotidienne, apprend des analyses passées

## Structure du projet
```
Bottrading V2/
├── dashboard/          ← Frontend web (HTML/CSS/JSX, React via CDN) → Vercel
│   ├── index.html
│   ├── styles.css
│   ├── app.jsx         ← Shell, navigation, sidebar avec drapeaux pays
│   ├── api.jsx         ← Fetch données réelles depuis localhost:5000
│   ├── data.jsx        ← 12 bots température + ProfitWeather + Crypto
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
│   ├── agent_temperature_cloud.py ← 12 villes, Railway 24/7 ← ACTIF
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
- ✅ **12 villes actives** : Chengdu 🇨🇳, Séoul 🇰🇷, Hong Kong 🇭🇰, NYC 🇺🇸, Londres 🇬🇧, Tokyo 🇯🇵, Atlanta 🇺🇸, Seattle 🇺🇸, Miami 🇺🇸, Singapour 🇸🇬, Madrid 🇪🇸, Shanghai 🇨🇳
- ✅ **ProfitWeather** (id: `polyedge`) — bot de trading météo, prêt pour simulation
- ✅ Toutes les clés dans `bot/.env` : ANTHROPIC, POLYMARKET (PRIVATE_KEY, API_SECRET, API_PASSPHRASE), SUPABASE
- ✅ `can_trade: True` — clés Polymarket valides
- ✅ `DRY_RUN=true` — simulation, aucun ordre réel
- ✅ Stratège Mistral — analyses croisées, mémoire des 7 dernières analyses
- ⏳ Attendre signaux bots d'analyse sur marchés J+1 avant première simulation
- ⏳ Wallet PUSD à $0 via data-api (à vérifier / déposer pour trading réel)

## ProfitWeather — Bot de trading (local)
- **Script** : `bot/loop.py` (lancé via `scripts/Lancer la stratégie.command`)
- **Cerveau** : Claude Haiku (`brain.py`) — lit les signaux Supabase + décide
- **Stratégie** : acheter YES sur marchés météo où les bots d'analyse ont détecté signal ≥75%
- **Marchés** : `polymarket.get_weather_markets()` — construit les slugs J+0/J+1 par ville, interroge l'API events Polymarket (132 marchés pour 12 villes)
- **Contexte Claude** : `_load_analysis_context()` lit depuis Supabase :
  - `strategie_analyses` — dernière analyse Mistral cross-ville
  - `{ville}_stats` — taux de réussite par ville
  - `{ville}_tracking` WHERE resultat IS NULL — signaux actifs
- **Cycle** : toutes les 15 min, auto-amélioration de stratégie toutes les 6h
- **Persistance** : `strategy.json` + `history.json` (fichiers locaux, ignorés par git)
- **Pour passer en réel** : `DRY_RUN=false` dans `bot/.env` (clés déjà en place)

## Bot Température Multi-Villes (actif sur Railway 24/7)
- **Script** : `bot/agent_temperature_cloud.py` (lancé via `Procfile`)
- **Railway** : projet `lucid-encouragement`, service `BotTradingV2`
- **Seuil signal** : YES ≥ 75%
- **Scan** : toutes les 15 min, J+0 si encore ouvert sinon J+1
- **Slug Polymarket** : `highest-temperature-in-{city}-on-{month}-{day}-{year}`
- **Tables Supabase par ville** (`{ville_id}` = chengdu / seoul / hong-kong / nyc / london / tokyo / atlanta / seattle / miami / singapore / madrid / shanghai) :
  - `{ville_id}_tracking` — signaux détectés (condition_id UNIQUE, yes_price_au_signal, resultat…)
  - `{ville_id}_stats` — stats globales (taux_victoire, gagnes, resolus…)
  - `{ville_id}_rapports` — rapport à chaque cycle
  - `{ville_id}_resumes` — résumé Mistral quotidien
- **Tables globales** : `strategie_analyses`, `strategie_config`, `bot_status`

## Ajouter une nouvelle ville
1. Vérifier le slug Polymarket : `highest-temperature-in-{city}-on-...`
2. Ajouter dans `VILLES` de `agent_temperature_cloud.py`
3. Ajouter bot dans `dashboard/data.jsx` avec `type:'temperature'`, `citySlug`, `flag`, `glyph`
4. Ajouter ville dans `VILLES` de `dashboard/page_stratege.jsx`
5. Créer 4 tables Supabase avec le bon schéma (voir tables ci-dessus)

## Pour activer le trading réel
1. Vérifier que le wallet a du PUSD sur Polymarket
2. `DRY_RUN=false` dans `bot/.env` (toutes les autres clés sont déjà en place)
3. Double-cliquer sur `scripts/Lancer la stratégie.command`

## Préférences utilisateur
- L'utilisateur ne code pas — expliquer simplement
- Toujours tester en local avant de déclarer terminé
- Bot actif principal : `agent_temperature_cloud.py` sur Railway
- ProfitWeather tourne en local (pas encore sur Railway)
