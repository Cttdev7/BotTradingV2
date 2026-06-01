# TradingBot V2 — Instructions pour Claude

## Ce que fait ce projet
Application web de gestion de bots de trading (Crypto, Actions, Polymarket).
Interface iOS-style, entièrement en HTML/CSS/JSX, aucun build nécessaire.

## Lancer le projet
```bash
cd "/Users/clementctt/Documents/Claude code/Bottrading V2"
python3 -m http.server 8080
```
Puis ouvrir http://localhost:8080

## Structure des fichiers
| Fichier | Rôle |
|---|---|
| `index.html` | Point d'entrée, charge React 18 + Babel via CDN |
| `styles.css` | Design tokens iOS (light/dark, densité, couleurs) |
| `data.jsx` | Données mock — **remplacer par API plus tard** |
| `icons.jsx` | Icônes SVG SF-style |
| `charts.jsx` | Sparkline, AreaChart, Donut, Meter |
| `ui.jsx` | Composants partagés (Card, Toggle, Button…) |
| `app.jsx` | Shell, navigation, sidebar, feuille "Nouveau bot" |
| `page_dashboard.jsx` | Liste de tous les bots |
| `page_bot.jsx` | Détail d'un bot (graphique P&L, positions, risque) |
| `page_portfolio.jsx` | Vue agrégée du portefeuille |
| `page_settings.jsx` | Réglages d'un bot |
| `page_history.jsx` | Historique des transactions |
| `tweaks-panel.jsx` | Panneau flottant thème/accent/densité |

## Conventions du code
- React 18 via CDN (pas de npm, pas de build)
- Babel transpile le JSX dans le navigateur
- Tous les composants sont exposés sur `window` (ex. `window.BotPage`)
- Variables CSS pour les couleurs : `var(--accent)`, `var(--green)`, `var(--text)`…
- Styles inline React partout (pas de classes CSS sauf layout global)

## État actuel
- ✅ 5 pages complètes et navigables
- ✅ Light/dark mode + densité switchable
- ✅ Rename des bots inline (sidebar + page bot)
- ⏳ APIs non connectées — données mock dans `data.jsx`
- ⏳ Dépôt GitHub à créer (git init fait, commit initial fait)

## APIs à brancher plus tard
Les marqueurs `// TODO: API` dans `data.jsx` indiquent où remplacer les données mock.
Marchés supportés : Crypto (Binance/Coinbase), Actions (Alpaca/IBKR), Polymarket.

## Préférences utilisateur
- L'utilisateur ne code pas — expliquer simplement
- Toujours tester en local avant de déclarer terminé
- Serveur local : `python3 -m http.server 8080`
