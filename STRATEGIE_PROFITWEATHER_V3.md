# ProfitWeather V3 — Stratégie complète

---

## L'idée de base

Sur Polymarket, chaque marché température (ex: "la température max à Helsinki le 3 juillet sera-t-elle 18°C ?") est découpé en plusieurs fourchettes. **Au moment où le marché vient tout juste d'être créé**, personne n'a encore vraiment parié dessus — les prix sont donc souvent très bas (quelques centimes), même sur la fourchette la plus probable, simplement parce que le marché n'a pas eu le temps de "se corriger" vers le bon prix.

Cette inefficacité se referme vite : en quelques heures à quelques jours, le prix de la bonne fourchette grimpe vers 90-99¢.

**Notre stratégie : on achète OUI (YES) très tôt, sur la fourchette la plus proche de la prévision météo, pendant que c'est encore pas cher.**

Contrairement au V2 (qui vise un très bon taux de réussite mais des gains minuscules en pariant NON tard et cher), le V3 accepte de perdre plus souvent — objectif ~60% de réussite — mais chaque perte est petite (mise limitée + sortie anticipée si ça tourne mal) alors que chaque gain multiplie la mise par 6 à 20 (acheter à 5-15¢ et toucher 1$ à la résolution).

---

## Quand un marché est-il "neuf" ?

Vérifié empiriquement le 01/07/2026 : Polymarket crée les marchés température **environ 2 jours avant leur échéance**, tous vers 4h-5h du matin UTC.

Exemple concret (Helsinki) :
- Le 1er juillet à 04h05 UTC → création du marché "température à Helsinki le **3 juillet**"
- Le marché "température à Helsinki le 4 juillet" n'existe pas encore le 1er juillet

**Conséquence : le bot ne scanne QUE les marchés à J+2** (aujourd'hui + 2 jours). Les marchés J+0 (aujourd'hui) et J+1 (demain) ont déjà 1 à 2 jours de trading derrière eux — la fenêtre de prix bas est presque toujours déjà refermée dessus. Scanner J+2, c'est arriver au moment même de la création.

---

## Les étapes du bot à chaque cycle (toutes les 90 secondes)

### Étape 1 — Détection
Scan des 45 villes suivies, uniquement sur l'échéance J+2 (voir ci-dessus).

### Étape 2 — Identifier la fourchette à acheter
Pour chaque marché repéré :
1. Extraction de la **station météo officielle de résolution** depuis la fiche du marché (champ `resolutionSource` — ex: `EFHK` pour Helsinki). C'est cette station qui sera surveillée après achat, pas juste un modèle météo.
2. Récupération de la prévision météo via **Open-Meteo (blend par défaut, sans modèle spécifique)** — source retenue après un backtest comparant Open-Meteo / ECMWF / GFS / ICON / MeteoFrance sur ~180 marchés déjà résolus, toutes villes. Open-Meteo blend avait le meilleur taux de réussite et l'erreur la plus faible, net sur les villes US.
3. Identification de la fourchette dont la prévision tombe dedans. Si aucune fourchette ne colle clairement, on ignore ce marché ce cycle.

### Étape 3 — Le prix doit encore être bas
Le bot n'achète que si le prix (ask) est encore **≤ 15 centimes**. Si le marché a déjà bougé, l'opportunité est passée — le bot ignore et revérifiera aux cycles suivants (le marché peut redevenir intéressant si le prix rebaisse).

### Étape 4 — Dernière vérification : Claude Haiku
L'IA regarde le dossier (prévision, fourchette, prix) et donne une note de confiance de 1 à 5. Le bot n'achète que si la confiance est **≥ 3/5**.

### Étape 5 — Achat
- Mise = **10% du capital alloué au V3** (jamais moins de 5$)
- **Maximum 2 nouveaux achats par cycle** — même si beaucoup d'opportunités apparaissent en même temps, le bot ne engage jamais plus de 2 positions d'un coup (déploiement progressif, pas de rafale qui viderait le plafond en un cycle)

### Étape 6 — Surveillance après achat (deux façons de sortir avant l'échéance)
Dès qu'une position est achetée, elle est surveillée **chaque seconde** jusqu'à la clôture (thread séparé du scan de détection, qui lui continue tranquillement toutes les 90s) :
- **Stop-loss prix** : si le prix de revente chute de **30%** par rapport à l'achat → vente immédiate.
- **Divergence météo** : le bot surveille la vraie station officielle (pas un modèle) en continu (relevé mis en cache 60s — une station météo ne se met à jour que toutes les 20-60 min, inutile de la rappeler chaque seconde). Si le relevé du jour montre que la température a déjà dépassé la fourchette achetée, ou que le pic du jour est clairement passé (après 18h heure locale) sans avoir atteint la fourchette → vente immédiate, plutôt que d'attendre une perte totale à la clôture.
- Sinon : la position reste jusqu'à la résolution naturelle.

---

## Est-ce que la prévision à 2 jours est vraiment fiable ?

Question légitime : rien ne garantit qu'une prévision faite 2 jours à l'avance corresponde exactement à ce qui sera mesuré par la station officielle le jour J.

**Le premier backtest ne répond pas vraiment à cette question.** En interrogeant Open-Meteo pour une date passée, l'API redonne sa meilleure estimation calculée **aujourd'hui** (proche de la réalité), pas ce qu'elle aurait dit 2 jours avant l'échéance — ça triche. Il n'existe pas d'API gratuite qui garde en mémoire "ce qui était prévu il y a 2 jours".

**Solution : un suivi permanent dans le bot.** Chaque prévision faite à la détection (achetée ou non) est enregistrée dans la table Supabase `profitweather_v3_forecast_log`. Une fois le marché résolu, le bot compare automatiquement la fourchette prévue à la fourchette gagnante réelle (`check_forecast_accuracy()`, lancé à chaque cycle de scan). Ça construit une vraie statistique de fiabilité dans le temps, sans tricher.

Premier lot : 32 prévisions loggées le 01/07/2026 pour des marchés du 3 juillet (ex: Paris → 28,1°C prévu, fourchette visée 28-29°C, station LFPB). Résultat vérifiable automatiquement une fois ces marchés résolus (vers le 3-4 juillet).

---

## Garde-fous financiers

- **Même compte Polymarket que le V2**, mais chacun plafonné à **50% du solde total** en position ouverte simultanée (le V2 a aussi été bridé à 50% pour que ce partage soit réel)
- Mise par trade : max 10% du capital alloué au V3 (= 5% du solde total)
- Jamais plus de 2 nouveaux achats par cycle

---

## Paramètres actuels (`bot/loop_v3.py`)
```python
NEW_MARKET_DAY_OFFSET = 2     # scan uniquement J+2 (marchés tout juste créés)
SCAN_INTERVAL         = 90    # cycle de détection toutes les 90s
MONITOR_INTERVAL      = 1     # surveillance des positions ouvertes toutes les 1s
MAX_ENTRY_PRICE        = 0.15 # achète seulement si prix ≤ 15¢
MIN_CONFIDENCE         = 3    # confiance Haiku minimum (1-5)
MAX_TRADES_PER_CYCLE   = 2    # jamais plus de 2 achats par cycle
V3_EXPOSURE_CAP        = 0.50 # 50% max du solde total en position ouverte
MAX_TRADE_PCT          = 0.10 # mise = 10% du capital alloué au V3
MIN_BET                = 5.0  # 5$ minimum par trade
STOP_LOSS_PCT          = 0.30 # vend si prix de revente -30%
LATE_DAY_HOUR          = 18   # heure locale à partir de laquelle "pic passé" devient un signal fort
```

---

## Persistance & déploiement
- Table Supabase : `profitweather_v3_trades` (positions/trades) + `profitweather_v3_forecast_log` (suivi précision météo)
- Fly.io app `profitweather-v3`, région Toronto (yyz)
- Statut actuel : **DRY_RUN** (simulation, aucun argent réel) — bot actuellement à l'arrêt en attendant le feu vert pour relancer la collecte de données

---

## Exemple réel travaillé (01/07/2026 — Helsinki, marché du 3 juillet)
- Prévision Open-Meteo : 18.3°C → fourchette visée : "18°C" (18-19°C)
- Station officielle : EFHK (aéroport de Vantaa)
- Prix ask réel au carnet d'ordres CLOB au moment du test : 99¢ (le prix affiché sur le site Polymarket, ~32,5¢, reflète les derniers échanges, pas forcément le carnet d'ordres actuel — quand la liquidité est faible, ces deux chiffres peuvent diverger)
- Décision du bot : **pas d'achat**, prix bien au-dessus de 15¢ dans les deux cas — la fenêtre d'ouverture est déjà passée sur ce marché
