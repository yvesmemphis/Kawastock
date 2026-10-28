from .models import ShopMembership

# Un raccourci pour ne pas réécrire "ShopMembership.Role" à chaque fois
R = ShopMembership.Role

# On utilise .value pour obtenir le texte simple ("owner", "seller"...),
# car c'est ce texte qui est écrit dans la base de données.
TOUS = {r.value for r in R}                              # tout le monde
PATRONS = {R.OWNER.value, R.MANAGER.value}               # le patron et le gérant
GESTION_STOCK = {R.OWNER.value, R.MANAGER.value, R.STOCK_MANAGER.value}   # ceux qui gèrent les produits
# Ceux qui ont le droit de LIRE le cahier du stock : les gestionnaires + la lecture seule.
# Le vendeur (seller) n'en fait pas partie.
LECTURE_STOCK = GESTION_STOCK | {R.VIEWER.value}