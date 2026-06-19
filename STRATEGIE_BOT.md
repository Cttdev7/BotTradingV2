# ProfitWeather V2 — Stratégie complète

---

## L'idée de base

On trade sur **Polymarket**, un site de paris de prédiction.
Pour chaque ville, Polymarket propose des marchés du type :
> "La température max à Paris le 18 juin sera-t-elle 37°C ?"

On peut parier **OUI** (YES) ou **NON** (NO).

**Notre stratégie : on parie toujours NON.**
Pourquoi ? Parce qu'il y a 10-11 fourchettes possibles pour chaque ville chaque jour, et une seule sera vraie. Les 9-10 autres perdent. On cherche les "NON" les plus évidents — ceux où la météo dit clairement que la température n'ira pas là.

---

## Comment Polymarket décide qui gagne

Polymarket utilise **Weather Underground (WU)** — un site météo qui agrège les données des aéroports. Chaque ville a une station précise :

- Paris → **Le Bourget (LFPB)**
- London → **London City Airport (EGLC)** (pas Heathrow !)
- NYC → **LaGuardia (KLGA)** (pas JFK !)
- Madrid → **Barajas (LEMD)**
- Chicago → **O'Hare (KORD)**
- etc.

La résolution se fait sur la **température max enregistrée** à cette station ce jour-là, arrondie au degré Celsius entier (ou en Fahrenheit pour les villes US).

---

## Les 7 étapes du bot à chaque cycle (toutes les 5 min)

### Étape 1 — Gérer les positions ouvertes
Avant de chercher de nouveaux trades, le bot vérifie ce qu'il a déjà en cours.
⚠️ **Important** : le SDK Polymarket actuel ne permet pas de vendre une position avant résolution. Le bot ne peut donc plus "vendre" — il attend que le marché se résolve naturellement, sauf pour le hedge :
- **Stop-Loss à -50%** : si un NO qu'on a acheté 90¢ tombe à 45¢ → le bot ne vend plus, il attend la résolution (le P&L final est enregistré quand le prix touche ~0)
- **Take-Profit à 96¢** : si notre NO monte à 96¢ → considéré comme quasi-gagné, le P&L estimé est enregistré
- **Auto-Hedge** : si un NO perd et que le YES en face monte entre 60% et 90% → le bot achète le YES avec une mise calculée pour ressortir +10% si le YES gagne (limite les dégâts, comme Cape Town et London). Pas de hedge si YES ≥ 90% (marché quasi-résolu)

### Étape 2 — Récupérer la météo réelle (METAR)
Le bot lit en direct les données des aéroports via **METAR** (même source que WU) :
- Température actuelle
- Max observé depuis minuit
- Tendance (montée ou descente)
- **Pic confirmé** : si la temp a baissé de 2°C depuis le max → le max est verrouillé

### Étape 3 — Récupérer la prévision ECMWF
ECMWF = le meilleur modèle météo européen (utilisé par Météo France).
Le bot récupère :
- **Température moyenne prévue** (moyenne des 50 modèles)
- **Probabilité par fourchette** (quelle chance que la temp soit dans cette plage ?)
- **Spread** = à quel point les modèles sont d'accord entre eux

### Étape 4 — Filtrer les marchés (pré-filtre)

Le bot élimine un marché si :

| Condition | Seuil | Raison |
|-----------|-------|--------|
| Prix NO trop bas | < 75¢ | Marge insuffisante |
| Prix NO trop haut | > 95¢ | Presque rien à gagner |
| ECMWF prédit > 30% dans ce range | → refus | Trop risqué |
| Band probability > 20% | → refus | ECMWF confirme risque |
| Modèles trop dispersés | spread > 10°F | Météo incertaine |
| Volume trop faible | < 1 500 USDC | Marché illiquide |
| Déjà une position sur cette ville | → refus | max 2 trades/ville/jour (1 normal + 1 cascade) |

Note : le blocage des marchés à valeur unique °C ("be 26°C") a été retiré — ils sont maintenant traités comme une fourchette d'1°C.

### Étape 5 — Direction du gap (la règle Chicago/Cape Town)

L'erreur du passé : acheter NO sur une fourchette *au-dessus* de la prévision le matin, alors que la temp va encore monter toute la journée.

**Règle actuelle (durcie le 17 juin) :**
- Fourchette **en-dessous** de la prévision → 2°F minimum d'écart (temp déjà dépassée → safe)
- Fourchette **au-dessus** de la prévision → **toujours bloquée**, sauf si le signal "pic METAR confirmé" dit que le maximum du jour est déjà tombé (la température ne peut plus monter, donc on connaît le résultat)

**Timing :**
- Marchés J+0 (aujourd'hui) : le bot attend 15h heure locale avant de trader
- Exception : si le METAR confirme que le pic est passé → trade immédiat autorisé

### Étape 6 — Claude Haiku décide

Le bot envoie à Claude Haiku (IA d'Anthropic) :
- La liste des candidats avec leur prix
- La prévision ECMWF
- Les données METAR en direct
- Le signal de sailor82 (si disponible)
- L'historique des trades récents

Claude Haiku répond : **acheter ou ne pas acheter**, avec une certitude (low/medium/high) et une raison.

**Règles que Claude ne peut PAS changer :**
- Jamais plus de 5% du solde sur un seul trade
- Jamais acheter YES (sauf auto-hedge)
- Jamais acheter si le prix est hors limites

**Signal Deko (sailor82) :**
Si le trader pro sailor82 a aussi un NO sur ce même marché → +1 niveau de certitude.

### Étape 7 — Exécution et enregistrement

Le bot place l'ordre via le SDK Polymarket, double-vérifie le prix 4 secondes après (si le prix a bougé de +2¢ → annulation), puis enregistre tout dans Supabase.

---

## Les types de marchés

### Marchés en °F (villes US)
Format : "Will the highest temperature in Chicago be 72-73°F on June 17?"
→ **Fourchettes de 2°F** — plus stables, plus faciles à analyser
→ Résolution via WU station locale (KORD, KLAX, KMIA...)

### Marchés en °C (villes hors-US)
Format : "Will the highest temperature in Paris be 37°C on June 18?"
→ **Valeurs uniques** — 1°C d'écart entre gagner et perdre
→ Plus risqués mais bons gains si prévision claire

---

## Le signal Cascade

Si un range domine à **60%** YES → les ranges adjacents reçoivent un signal NO automatique.

Exemple : si "78-79°F" monte à 60% YES pour Chicago → les ranges "72-73°F" et "80-81°F" reçoivent un signal NO (le marché dit que la temp sera ~79°F, donc pas dans ces autres ranges).

---

## L'auto-hedge (leçon Cape Town)

Si on a un NO qui perd et que le YES monte à 60-90% :
Le bot achète le YES en face avec une mise calculée pour que **si le YES gagne, on récupère notre mise initiale + 10%**.

Résultat : on transforme une perte certaine en situation neutre ou légèrement gagnante.

Exemple réel (London, 17 juin) :
- NO 26°C acheté à 85¢ → tombe à 33¢ (-61%)
- Bot achète YES à 67¢
- Si London atteint 26°C → YES gagne, on récupère +66¢ net
- Si London reste à 25°C → NO gagne, YES perd → -4.68$

---

## Les paramètres clés (hard-codés, jamais modifiés par l'IA)

```
MIN_NO_PRICE      = 0.75    → NO minimum 75¢
MAX_NO_PRICE      = 0.95    → NO maximum 95¢
MAX_BET_PCT       = 0.05    → max 5% du solde par trade
MAX_EXPOSURE_PCT  = 100%    → du portefeuille total (cash + positions ouvertes)
MIN_FORECAST_GAP_DOWN = 2°F → gap mini si range en-dessous prévision
MIN_FORECAST_GAP_UP   = 8°F → gap mini si range au-dessus prévision (cas exceptionnel, pic confirmé)
MAX_ENSEMBLE_PROB = 30%     → refuse si ECMWF prédit >30% dans ce range
MAX_BAND_PROB     = 20%     → refuse si band_prob > 20%
MAX_MODELS_SPREAD = 10°F    → refuse si modèles trop dispersés
MIN_VOLUME        = 1 500$  → refuse les marchés trop illiquides
NO_STOP_LOSS_PCT  = -50%    → attend la résolution naturelle (le SDK ne vend plus), déclenche post-mortem
NO_TAKE_PROFIT    = 0.96    → considéré comme gagné, P&L estimé enregistré
CASCADE_TRIGGER   = 60%     → cascade si YES dominant > 60%
HEDGE_YES_TRIGGER = 60%     → hedge si YES entre 60% et 90%
HEDGE_MULTIPLIER  = 1.10    → mise hedge calculée pour +10% si le YES gagne
```

---

## Les stations Weather Underground par ville (source de résolution)

| Ville | Station WU | Aéroport réel |
|-------|-----------|---------------|
| London | EGLC | London City (pas Heathrow) |
| Paris | LFPB | Le Bourget (pas CDG) |
| NYC | KLGA | LaGuardia (pas JFK) |
| Dallas | KDAL | Love Field (pas DFW) |
| Denver | KBKF | Buckley AFB (pas Denver Int'l) |
| Seoul | RKSI | Incheon |
| Taipei | RCSS | Songshan (pas Taoyuan) |
| Milan | LIMC | Malpensa (pas Linate) |
| Chicago | KORD | O'Hare ✓ |
| Miami | KMIA | Miami Int'l ✓ |
| Madrid | LEMD | Barajas ✓ |
| Tokyo | RJTT | Haneda ✓ |

---

## Ce que le bot surveille en permanence

1. **45 villes** sur Railway 24/7 → signaux YES > 75%
2. **sailor82** (agent Deko) → ses trades en temps réel → signal bonus
3. **Stratège Mistral** → analyse cross-ville toutes les 15 min, apprend des erreurs
4. **Postmortem automatique** → chaque trade perdu est analysé (heure, météo réelle, gap)

---

## Leçons apprises

| Date | Ville | Erreur | Correction |
|------|-------|--------|------------|
| Juin 16 | Dallas | NO à 97¢ — marge trop faible | MAX_NO_PRICE = 0.95 |
| Juin 16 | Beijing/Seoul/... | SL déclenché (stop-loss) | Maintien du SL à -50% |
| Juin 17 | Cape Town | NO sur marché °C unique, 0.2°C d'écart | Blocage marchés °C uniques |
| Juin 17 | London | Même problème + hedge activé | Idem + stations WU corrigées |
| Juin 17 | Chicago | NO acheté le matin sur fourchette au-dessus | Règle directionnelle 2°F/8°F |
| Divers | 8 villes | Mauvaises stations METAR (EGLL, KJFK...) | Stations WU corrigées depuis descriptions Polymarket |
