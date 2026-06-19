# ProfitWeather V2 — Entrée précoce NO sous prévision — Design

## Contexte
L'utilisateur trade manuellement sur Polymarket une stratégie simple : acheter le NO sur la fourchette de température située environ 2° sous la prévision, dès que le marché du jour ouvre (ou quelques heures après) — sans attendre que la journée avance. Il veut que `bot/loop_v2.py` (ProfitWeather V2) s'inspire de cette approche.

Le bot a déjà cette logique de fourchette ("range sous la prévision → safe", `MIN_FORECAST_GAP_DOWN = 2.0` °F) dans `_prefilter()`, mais elle est actuellement bridée par deux verrous temporels conçus pour les autres stratégies (cascade, pic METAR) :
- il attend **15h heure locale** le jour J avant de trader un marché J+0 (lignes ~533-540)
- il ignore les marchés qui ferment dans **plus de 20h** (`MAX_HOURS_REMAINING`, lignes ~494-504)

Ces deux verrous empêchent le bot d'entrer tôt comme le fait l'utilisateur à la main.

## Changement
Dans `_prefilter()` :
1. **Réordonner les calculs** : déterminer `forecast_mean`, `bounds` et `gap_direction` (down/up/inside) **avant** d'appliquer les verrous `MAX_HOURS_REMAINING` et l'attente 15h locale J+0 (actuellement ces verrous s'exécutent avant le calcul de direction).
2. **Condition de bypass** : si `gap_direction == "down"` et `gap >= MIN_FORECAST_GAP_DOWN`, le candidat **saute** :
   - le verrou `MAX_HOURS_REMAINING` (20h)
   - le verrou "attendre 15h locale" pour J+0
3. **Garde-fous qui restent appliqués sans exception**, pour tous les chemins (down, up, cascade) :
   - `MIN_HOURS_REMAINING` (1h) — ne jamais trader à la toute dernière minute avant clôture
   - Prix NO entre `MIN_NO_PRICE` (75¢) et `MAX_NO_PRICE` (95¢)
   - `MIN_VOLUME` (1500 USDC)
   - `MAX_ENSEMBLE_PROB` (30%), `MAX_BAND_PROB` (20%), `MAX_MODELS_SPREAD` (10°F)
   - Limites d'exposition (`MAX_BET_PCT`, `MAX_EXPOSURE_PCT`), 1 trade max par ville/cycle, max 2 positions par ville/jour
4. **Le chemin "up" (range au-dessus de la prévision) garde son blocage strict actuel** — ce changement ne concerne que la direction "down".
5. **Claude Haiku continue de valider** chaque candidat retenu, exactement comme aujourd'hui — pas d'achat automatique sans passage par `brain.py`.

## Hors scope
- Pas de nouveau seuil de prix (on garde 75-95¢, décision déjà actée).
- Pas de nouvelle table Supabase, pas de nouveau bot.
- Pas de changement à la logique cascade / pic METAR / auto-hedge — elles continuent de fonctionner comme avant, en parallèle.
- Pas de changement au chemin "up" (toujours bloqué sauf pic confirmé).

## Test
Pas de suite pytest dans ce projet (convention existante). Vérification via un script `assert`-based qui appelle `_prefilter()` avec :
- un marché fictif J+0, heure locale 9h (donc avant 15h), fermant dans 18h, range sous la prévision avec un gap de 3°F, prix NO à 80¢ → doit être retenu (alors qu'avant ce changement il aurait été rejeté par le verrou 15h).
- un marché fictif fermant dans 25h (donc hors fenêtre actuelle), même conditions sous-prévision → doit être retenu.
- un marché fictif équivalent mais avec range AU-DESSUS de la prévision → doit rester rejeté (comportement inchangé).
- un marché fictif sous-prévision mais fermant dans 0.5h (`MIN_HOURS_REMAINING` non respecté) → doit rester rejeté.
