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
│   ├── page_bot.jsx    ← Onglets Aperçu / Stratégie par bot
│   ├── page_portfolio.jsx
│   ├── page_settings.jsx
│   ├── page_history.jsx← Prop transactions depuis app.jsx
│   ├── page_strategy.jsx
│   └── page_analyse.jsx← Agent Mistral — analyse indépendante
├── bot/                ← Backend Python
│   ├── config.py       ← Charge .env (MISTRAL_API_KEY, ANTHROPIC_API_KEY…)
│   ├── auth.py         ← Signature HMAC-SHA256 partagée
│   ├── polymarket.py   ← API Polymarket (marchés, balance, positions)
│   ├── mistral.py      ← Agent d'analyse Mistral
│   ├── brain.py        ← Cerveau IA Claude Haiku (décisions de trading)
│   ├── trader.py       ← Exécution ordres (DRY_RUN=true par défaut)
│   ├── loop.py         ← Boucle toutes les 15 min
│   ├── server.py       ← Flask API port 5000
│   ├── requirements.txt
│   ├── .env            ← Clés API (jamais committé)
│   └── .env.example    ← Template
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
- ⏳ `MISTRAL_API_KEY` — à ajouter dans `bot/.env`
- ⏳ `ANTHROPIC_API_KEY` — à ajouter dans `bot/.env`
- ⏳ USDC sur Polygon — wallet vide, à alimenter

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
- Un seul bot actif : `polyedge` (Polymarket Edge)
