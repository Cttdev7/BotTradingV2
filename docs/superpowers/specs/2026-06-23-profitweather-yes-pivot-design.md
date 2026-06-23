# ProfitWeather V2 — Ajout d'une voie YES à haute conviction

## Contexte

Le 21/06, l'auto-amélioration de Claude Haiku (`bot_strategies`, id=`polyedge2`) a recommandé de
pivoter d'une stratégie NO pure vers des achats YES sur les villes où le bot multi-villes
(`agent_temperature_cloud.py`) observe un historique de réussite de 92-100% quand son signal YES≥75%
se déclenche (Chengdu, Seoul, London, Tokyo — 13-15/14 victoires citées).

Cette recommandation n'a aucun effet aujourd'hui : `loop_v2.py` n'autorise que `outcome="No"`
(`brain.py:695` force `d["outcome"]="No"` quoi que Claude réponde — règle durcie après les épisodes
Dallas/Amsterdam où Claude Haiku ignorait les limites de prix dans le prompt).

Décision validée avec l'utilisateur : on **ajoute** une voie YES en plus du NO existant (qui ne change
pas), restreinte aux 4 villes où la donnée est réellement prouvée, avec les mêmes garde-fous que le NO
mais en miroir, testée en simulation avant l'argent réel.

**Point de vigilance clarifié pendant le brainstorm** : la donnée "92-100% de réussite" mesure
*prix du marché ≥75% → résultat réel*, pas *prévision ECMWF → résultat réel* (ce backtest n'existe pas).
Le déclenchement YES doit donc se baser sur le **prix du marché**, pas sur l'accord ECMWF (qui reste le
signal du NO).

## Périmètre

- Le NO existant (filtres, mises, take-profit, stop-loss, hedge, cascade) n'est pas modifié.
- Nouvelle voie YES, mécanisme indépendant, activable/désactivable séparément.
- Pas de gestion take-profit/stop-loss/hedge spécifique au YES pour l'instant — positions tenues
  jusqu'à résolution naturelle (réévalué après la phase DRY_RUN).

## Paramètres hard-codés (loop_v2.py — jamais modifiables par Claude/Supabase)

```python
YES_WHITELIST_CITIES = {"chengdu", "seoul", "london", "tokyo"}
MIN_YES_PRICE         = 0.75
MAX_YES_PRICE         = 0.96
MAX_YES_EXPOSURE_PCT  = 0.20   # plafond séparé du NO : max 20% du portefeuille total en YES ouverts
```

`YES_DRY_RUN` (env var, défaut `"true"`) — interrupteur indépendant du `DRY_RUN` global utilisé par
le NO (déjà en trading réel). Tant que `YES_DRY_RUN=true`, les ordres YES sont simulés (loggés +
enregistrés en DB avec `dry_run:true`) sans appeler `trader.place_market_order` réellement, quel que
soit l'état du `DRY_RUN` global.

## Détection (`_prefilter` dans loop_v2.py)

Pour les marchés des 4 villes whitelistées uniquement, ajoute les candidats où :
- prix YES ∈ `[MIN_YES_PRICE, MAX_YES_PRICE]`
- volume ≥ `MIN_VOLUME` (réutilise la constante existante)

Pas de filtre ECMWF additionnel pour le YES (la donnée prouvée est le seuil de prix, pas l'accord
modèle météo). Marque ces candidats `m["_yes_eligible"] = True` pour que la suite de la boucle les
distingue.

## Décision (`brain.decide_v2` dans brain.py)

- `_format_markets_v2` doit aussi inclure les marchés YES-éligibles des villes whitelistées (ils sont
  aujourd'hui exclus car la fonction filtre tout `no_price < 0.60`, ce qui exclut justement les
  marchés où le YES est haut). Ajout d'une section séparée dans le texte envoyé à Claude listant ces
  candidats avec leur prix YES.
- Prompt système : nouvelle section expliquant la stratégie YES (villes whitelistées, prix YES
  70-96¢, même barème de certitude high/medium/low → 5/3/2% du solde).
- Le JSON de réponse peut contenir `"outcome": "Yes"` en plus de `"No"`.
- Suppression du hard-code `d["outcome"] = "No"` (ligne ~695). Remplacé par une validation : la
  décision n'est conservée que si `outcome == "No"`, ou (`outcome == "Yes"` ET la ville du marché est
  dans `YES_WHITELIST_CITIES`) — sinon rejetée silencieusement (defense-in-depth, en plus du filtre de
  prefilter).

## Exécution (boucle principale `run_cycle` dans loop_v2.py)

- La boucle accepte désormais `d.get("outcome") in ("No", "Yes")` au lieu de `("No", "NO")` strict.
- Pour les décisions YES :
  - même double vérification de prix T1/T2 (pause 4s, annulation si chute >2¢ ou hors zone
    `[MIN_YES_PRICE, MAX_YES_PRICE]`)
  - même `_calc_bet` (barème par certitude)
  - exposition YES suivie séparément (`total_exposed_yes`), plafonnée à
    `total_portfolio * MAX_YES_EXPOSURE_PCT` — indépendant du calcul d'exposition NO existant
  - avant l'ordre réel : si `YES_DRY_RUN` est vrai, construire un résultat simulé (même format que
    `trader.place_market_order` en mode DRY_RUN) sans appeler le SDK
  - trade enregistré avec `"sym": "YES"`, `"side": "buy"`
- Règle "max 2 trades/ville/jour" : compteur partagé avec le NO (une ville qui a déjà tradé NO ce jour
  ne devrait pas aussi être tradée YES le même jour — cohérent avec la limite existante par
  ville+date).

## Pas de changement

- Take-profit (`NO_TAKE_PROFIT`), stop-loss (`NO_STOP_LOSS_PCT`), auto-hedge, cascade : continuent de
  ne s'appliquer qu'aux positions NO. Les positions YES sont tenues jusqu'à résolution naturelle.
- `check_market_outcomes` doit cependant reconnaître `sym="YES"` pour calculer le P&L correctement à
  la résolution (vérifier qu'il ne suppose pas `sym="No"` implicitement).

## Plan de déploiement

1. Implémenter avec `YES_DRY_RUN=true` par défaut.
2. Tourner quelques jours en simulation, vérifier dans les logs que les déclenchements YES sont
   cohérents (bonnes villes, bon prix, bonne fréquence).
3. Si ok, l'utilisateur passe `YES_DRY_RUN=false` manuellement dans `bot/.env` pour activer le réel.

## Hors périmètre

- Pas de backtest ECMWF↔résultat réel (question soulevée pendant le brainstorm, confirmée absente du
  code actuel — pourrait être une amélioration future séparée).
- Pas d'extension de la whitelist à d'autres villes pour l'instant (Milan/Paris écartés — historique
  jugé moins établi par l'utilisateur).
