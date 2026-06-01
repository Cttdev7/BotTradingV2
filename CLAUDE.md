# TradingBot V2 — Instructions pour Claude

## Ce que fait ce projet
Bot de trading autonome sur **Polymarket** (marchés de prédiction) avec dashboard iOS-style.
Le bot utilise Claude Haiku pour analyser les marchés et décider quoi trader selon une stratégie écrite en langage naturel.

## Lancer le projet

```bash
# Dashboard (interface web)
python3 -m http.server 8080        # → http://localhost:8080

# Serveur API bot (connexion Polymarket)
python3 bot/server.py              # → http://localhost:5000

# Boucle de trading automatique
python3 bot/loop.py
```

Ou double-cliquer sur les fichiers `.command` dans le dossier.

## Architecture

### Frontend (`/`)
| Fichier | Rôle |
|---|---|
| `index.html` | Point d'entrée — React 18 + Babel via CDN, aucun build |
| `styles.css` | Design tokens iOS (light/dark, densité, couleurs CSS vars) |
| `data.jsx` | Bot unique (polyedge), TXNS et POSITIONS vides — remplis par api.jsx |
| `api.jsx` | Fetch données réelles depuis localhost:5000, mappers vers format composants |
| `app.jsx` | Shell, navigation, sidebar, bannière serveur, sync toutes les 30s |
| `icons.jsx` | Icônes SVG SF-style |
| `charts.jsx` | Sparkline, AreaChart (hover), Donut, Meter |
| `ui.jsx` | Card, Toggle, Button, Segmented, BotGlyph… |
| `page_dashboard.jsx` | Dashboard bots + portfolio hero |
| `page_bot.jsx` | Détail bot — onglets Aperçu / Stratégie (prompt par bot) |
| `page_portfolio.jsx` | Vue agrégée portefeuille |
| `page_settings.jsx` | Réglages bot (sliders, toggles) |
| `page_history.jsx` | Historique trades (prop `transactions` depuis app.jsx) |
| `page_strategy.jsx` | Éditeur stratégie global (page nav) |

### Backend (`bot/`)
| Fichier | Rôle |
|---|---|
| `config.py` | Charge `.env` — `validate()` + `can_trade()` |
| `auth.py` | Signature HMAC-SHA256 partagée (L2 auth Polymarket) |
| `polymarket.py` | API Polymarket — marchés, balance, positions, activité |
| `brain.py` | Cerveau IA — appelle Claude Haiku avec stratégie + marchés + historique |
| `trader.py` | Exécution ordres — `DRY_RUN=true` par défaut |
| `loop.py` | Boucle toutes les 15 min — décide → exécute → sauvegarde → réflexion 24h |
| `server.py` | Flask API locale port 5000 — endpoints pour le dashboard |
| `.env` | Clés API (jamais committé) |

### Fichiers générés (ignorés par git)
- `bot/history.json` — historique des trades du bot
- `bot/strategy.json` — prompts de stratégie par bot_id
- `bot/reflections.json` — analyses quotidiennes de Claude
- `bot/bot.log` — logs de la boucle

## Conventions frontend
- React 18 via CDN, Babel transpile JSX dans le navigateur
- Composants exposés sur `window` (ex. `window.BotPage`)
- Styles inline React partout (pas de classes CSS sauf layout global)
- Variables CSS : `var(--accent)`, `var(--green)`, `var(--text)`, `var(--fill)`…

## État actuel
- ✅ Dashboard iOS complet (5 pages, light/dark, rename inline)
- ✅ Connexion Polymarket réelle (API Key + Secret + Passphrase + Private Key)
- ✅ `can_trade: True` — prêt à passer des ordres
- ✅ Cerveau IA (brain.py) — Claude Haiku décide selon le prompt
- ✅ Mode simulation (DRY_RUN=true) — aucun vrai ordre sans activation explicite
- ✅ Réflexion quotidienne — le bot apprend de ses erreurs
- ⏳ USDC sur Polygon — wallet vide, à alimenter
- ⏳ Clé Anthropic — à ajouter dans .env pour activer le cerveau IA

## Pour activer le trading réel
1. Ajouter `ANTHROPIC_API_KEY=sk-ant-...` dans `bot/.env`
2. Déposer des USDC sur le wallet Polygon
3. Écrire une stratégie dans le dashboard (onglet Stratégie du bot)
4. Activer le toggle "Activer ce bot"
5. Changer `DRY_RUN=false` dans `bot/.env`
6. Double-cliquer sur `Lancer la stratégie.command`

## Préférences utilisateur
- L'utilisateur ne code pas — expliquer simplement
- Toujours tester en local avant de déclarer terminé
- Un seul bot actif : `polyedge` (Polymarket Edge)
