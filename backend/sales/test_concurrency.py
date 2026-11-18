import threading
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase

from catalog.models import Product
from inventory.exceptions import InsufficientStock
from sales.models import Sale
from sales.services import create_sale
from shops.models import Shop

User = get_user_model()


# skipUnless = "ne lance ce test QUE si la base est PostgreSQL".
# Sur SQLite, il serait faux (SQLite ignore les cadenas), donc on le saute.
@skipUnless(connection.vendor == "postgresql", "Ce test nécessite PostgreSQL.")
class ConcurrentSaleTests(TransactionTestCase):

    def test_deux_vendeurs_pour_le_dernier_article(self):
        # --- Préparation : UN seul article en stock ---
        shop = Shop.objects.create(name="Quincaillerie A")
        seller1 = User.objects.create_user(email="v1@a.ci", username="v1", password="MotDePasse123!")
        seller2 = User.objects.create_user(email="v2@a.ci", username="v2", password="MotDePasse123!")
        product = Product.objects.create(
            shop=shop, sku="CLOU-50", name="Clou 50mm",
            selling_price=Decimal("500"), cost_price=Decimal("300"),
            stock_quantity=Decimal("1"),
        )

        results = []
        # Le portillon de départ : il ne s'ouvre que quand 2 vendeurs sont arrivés.
        start_line = threading.Barrier(2)

        def sell(user):
            try:
                start_line.wait()                    # "j'attends l'autre au portillon..."
                create_sale(                         # ...et on tente la vente en même temps
                    shop=shop, user=user,
                    items=[{"product_id": product.id, "quantity": Decimal("1")}],
                )
                results.append("vendu")
            except InsufficientStock:
                results.append("refusé")             # le bon comportement pour le perdant
            except Exception as error:
                results.append(f"ERREUR: {error!r}") # tout autre problème = un vrai bug
            finally:
                # Chaque "fil" a sa propre connexion à la base : on la ferme proprement.
                connections.close_all()

        threads = [threading.Thread(target=sell, args=(u,)) for u in (seller1, seller2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()        # "attends que les deux aient fini"

        # --- Vérifications ---
        self.assertEqual(sorted(results), ["refusé", "vendu"])    # un gagnant, un perdant
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, Decimal("0"))    # 0, jamais -1
        self.assertEqual(Sale.objects.filter(shop=shop).count(), 1)   # une seule vente existe