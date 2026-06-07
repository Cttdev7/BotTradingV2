# TradingBot V2 — Instructions pour Claude

## Ce que fait ce projet
Bot de trading autonome sur **Polymarket** (marchés de prédiction) avec dashboard iOS-style.
Le bot utilise Claude Haiku pour analyser les marchés et décider quoi trader selon une stratégie écrite en langage naturel.
Un agent Mistral indépendant analyse les marchés et propose des stratégies.

## Structure du projet
```
Bottrading V2/
├── dashboard/          ← Frontend web (HTML/CSS/JSX, React via CDN)
│   ├── index.html      ← Point d'entrée
│   ├── styles.css      ← Design tokens iOS
│   ├── app.jsx         ← Shell, navigation, sync API
│   ├── api.jsx         ← Fetch données réelles depuis localhost:5000
│   ├── data.jsx        ← Bot polyedge, TXNS/POSITIONS vides (remplis par api.jsx)
│   ├── charts.jsx      ← Sparkline, AreaChart, Donut, Meter
│   ├── icons.jsx       ← Icônes SVG SF-style
│   ├── ui.jsx          ← Composants partagés (Card, Toggle, Button…)
│   ├── tweaks-panel.jsx← Panneau thème/densité
│   ├── page_dashboard.jsx
│   ├── page_bot.jsx    ← Onglets Aperçu / Stratégie / Analyse Mistral par bot
│   ├── page_portfolio.jsx
│   ├── page_settings.jsx
│   └── page_history.jsx← Prop transactions depuis app.jsx
├── bot/                ← Backend Python
│   ├── config.py       ← Charge .env (MISTRAL_API_KEY, ANTHROPIC_API_KEY…)
│   ├── auth.py         ← Signature HMAC-SHA256 partagée
│   ├── polymarket.py   ← API Polymarket (marchés, balance, positions)
│   ├── mistral.py      ← Agent d'analyse Mistral
│   ├── brain.py        ← Cerveau IA Claude Haiku (décisions de trading)
│   ├── trader.py       ← Exécution ordres (DRY_RUN=true par défaut)
│   ├── loop.py         ← Boucle toutes les 15 min
│   ├── server.py       ← Flask API port 5000
│   ├── agent_meteo.py          ← Agent météo local (JSON)
│   ├── agent_meteo_cloud.py    ← Agent météo cloud (GitHub Actions + Supabase)
│   ├── agent_chengdu.py        ← Agent Chengdu local (JSON)
│   ├── agent_chengdu_cloud.py  ← Agent Chengdu cloud (Railway + Supabase) ← ACTIF
│   ├── requirements.txt
│   ├── .env            ← Clés API (jamais committé)
│   └── .env.example    ← Template
├── Procfile            ← Commande Railway : python3 bot/agent_chengdu_cloud.py
├── requirements.txt    ← Dépendances racine pour Railway
└── scripts/            ← Scripts de lancement double-clic
    ├── Lancer le dashboard.command
    ├── Lancer le bot.command
    └── Lancer la stratégie.command
```

## Lancer le projet
```bash
# Dashboard
cd dashboard && python3 -m http.server 8080   # → http://localhost:8080

# Serveur bot
python3 bot/server.py                          # → http://localhost:5000

# Boucle de trading
python3 bot/loop.py
```
Ou double-cliquer sur les fichiers dans `scripts/`.

## Conventions frontend
- React 18 via CDN, Babel transpile JSX dans le navigateur, **aucun build**
- Composants exposés sur `window` (ex. `window.BotPage`)
- Styles inline React partout (pas de classes CSS sauf layout global)
- Variables CSS : `var(--accent)`, `var(--green)`, `var(--text)`, `var(--fill)`…

## État actuel
- ✅ Dashboard iOS complet (6 pages dont Analyse Mistral)
- ✅ Connexion Polymarket réelle — `can_trade: True`
- ✅ Bot polyedge connecté, données en temps réel
- ✅ Mode simulation `DRY_RUN=true` — aucun ordre réel sans activation
- ✅ Agent Mistral pour l'analyse indépendante des marchés
- ✅ **Bot température multi-villes** — `agent_temperature_cloud.py` sur Railway 24/7
- ✅ **3 villes actives** : Chengdu 🌡️, Séoul 🏙️, Hong Kong 🌆
- ✅ **Open-Meteo** intégré — température réelle par ville (sans clé API)
- ✅ **Dashboard Analyse** générique — fonctionne pour toutes les villes `type: 'temperature'`
- ⏳ `MISTRAL_API_KEY` — à ajouter dans variables Railway pour résumé 17h
- ⏳ `ANTHROPIC_API_KEY` — à ajouter dans `bot/.env`
- ⏳ USDC sur Polygon — wallet vide, à alimenter

## Bot Température Multi-Villes (actif sur Railway)
- **Script** : `bot/agent_temperature_cloud.py` (lancé via `Procfile`)
- **Villes** : Chengdu (UTC+8), Séoul (UTC+9), Hong Kong (UTC+8)
- **Ajouter une ville** : 1 entrée dans `VILLES` + 4 tables Supabase `{id}_*` + 1 bot dans `data.jsx`
- **Stratégie** : tracker les options YES >80% (marché encore ouvert), mesurer les résultats
- **Scan** : toutes les 15 min, J+0 si encore ouvert sinon J+1
- **Résolution** : détecte `closed OR resolved` (2 états Polymarket)
- **Cloud** : Railway (projet `lucid-encouragement`) → `Procfile`
- **Tables Supabase par ville** (`{ville_id}` = chengdu / seoul / hong-kong) :
  - `{ville_id}_tracking` — signaux détectés
  - `{ville_id}_stats` — stats globales
  - `{ville_id}_rapports` — rapport à chaque cycle
  - `{ville_id}_resumes` — résumé Mistral quotidien à 17h
- **Timezones** : bot interne = timezone locale de la ville, logs = `Europe/Paris`
- **Open-Meteo** : température max via coordonnées GPS de chaque ville
- **Logs Railway** : `/logs` dans le projet Railway

## Pour activer le trading réel
1. `ANTHROPIC_API_KEY=sk-ant-...` dans `bot/.env`
2. `MISTRAL_API_KEY=...` dans `bot/.env`
3. Déposer des USDC sur le wallet Polygon
4. Écrire une stratégie dans le dashboard (onglet Stratégie du bot)
5. `DRY_RUN=false` dans `bot/.env`
6. Double-cliquer sur `scripts/Lancer la stratégie.command`

## Préférences utilisateur
- L'utilisateur ne code pas — expliquer simplement
- Toujours tester en local avant de déclarer terminé
- Bot actif principal : `chengdu` (Agent Chengdu cloud sur Railway)
