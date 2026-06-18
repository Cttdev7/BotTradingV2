"""Test des fonctions de timing pures de zerotoherobtc.py (pas d'appel réseau)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from zerotoherobtc import current_window_end_epoch, slug_for_end_epoch

# 1781808300 est un multiple exact de 300 (confirmé via l'event réel
# btc-updown-5m-1781808300 pendant le design) -> juste avant cette frontière,
# la fin de fenêtre attendue est ce même timestamp.
assert current_window_end_epoch(1781808299) == 1781808300, "doit arrondir au prochain multiple de 300"
assert current_window_end_epoch(1781808300) == 1781808300, "pile sur la frontière -> elle-même"
assert current_window_end_epoch(1781808001) == 1781808300, "doit arrondir au-dessus, pas en dessous"
assert current_window_end_epoch(1781808300 - 300) == 1781808300 - 300, "frontière précédente"

assert slug_for_end_epoch(1781808300) == "btc-updown-5m-1781808300"

print("✅ Tous les tests de timing passent")
