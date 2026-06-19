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

## Changement 2 — Seuil cascade abaissé 60% → 40%
L'utilisateur observe aussi cette pratique manuelle : si une fourchette devient dominante (YES le plus haut du groupe ville/jour) même à seulement ~40%, il regarde les fourchettes adjacentes et achète NO sur celle dont le prix est dans la bonne tranche.

Le bot a déjà ce mécanisme (`_detect_cascade()`, `CASCADE_TRIGGER`) mais avec un seuil de déclenchement à 60%. Changement : `CASCADE_TRIGGER = 0.60` → `CASCADE_TRIGGER = 0.40` (ligne ~61 de `loop_v2.py`). Aucune autre logique ne change — `_detect_cascade()` continue de marquer toutes les fourchettes non-dominantes du groupe ville/jour, et le filtre de prix (75-96¢, voir Changement 3) s'applique toujours avant tout achat.

## Changement 3 — Plafond prix NO 95¢ → 96¢
Alignement sur la pratique manuelle de l'utilisateur ("tranche 75%-96%"). `MAX_NO_PRICE = 0.95` → `MAX_NO_PRICE = 0.96` (ligne ~40 de `loop_v2.py`). Ce plafond est utilisé à plusieurs endroits (prefilter ligne ~507, double vérification avant exécution ligne ~815) — un seul changement de constante suffit, pas de logique à dupliquer.

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
- `_detect_cascade()` avec un groupe ville/jour dont le YES dominant est à 45% (sous l'ancien seuil 60%, au-dessus du nouveau 40%) → les ranges adjacentes doivent être marquées `_cascade` (alors qu'avant ce changement elles ne l'auraient pas été).
- un candidat à 96¢ NO → doit passer le filtre prix (alors qu'avant ce changement, à 95¢ pile la limite, 96¢ aurait été rejeté) ; un candidat à 97¢ doit rester rejeté.
