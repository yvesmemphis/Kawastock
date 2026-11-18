from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from catalog.models import Product
from inventory.models import StockMovement
from sales.models import Sale
from shops.models import Shop, ShopMembership

User = get_user_model()


class SaleTests(APITestCase):
    # APITestCase = une classe de test avec un "faux navigateur" (self.client).

    def setUp(self):
        # setUp s'exécute AVANT chaque test : il prépare un petit monde tout neuf.
        self.shop = Shop.objects.create(name="Quincaillerie A", slug="quincaillerie-a")
        self.other_shop = Shop.objects.create(name="Quincaillerie B", slug="quincaillerie-b")

        self.owner = self.make_user(self.shop, "owner", "patron@a.ci")
        self.seller = self.make_user(self.shop, "seller", "vendeur@a.ci")

        # Un produit : 10 en stock, vendu 500, acheté 300.
        self.product = Product.objects.create(
            shop=self.shop, sku="CLOU-50", name="Clou 50mm",
            selling_price=Decimal("500"), cost_price=Decimal("300"),
            stock_quantity=Decimal("10"),
        )

    # ---------- Petits outils pour ne pas répéter le même code ----------

    def make_user(self, shop, role, email):
        user = User.objects.create_user(email=email, username=email, password="MotDePasse123!")
        ShopMembership.objects.create(shop=shop, user=user, role=role)
        return user

    def as_user(self, user, shop):
        # "Fais comme si cette personne était connectée, dans ce commerce."
        self.client.force_authenticate(user=user)
        self.client.credentials(HTTP_X_SHOP_ID=str(shop.id))

    def post_sale(self, quantity, key=None, **extra):
        body = {
            "items": [{"product_id": str(self.product.id), "quantity": quantity}],
            "idempotency_key": str(key or uuid4()),
        }
        body.update(extra)
        return self.client.post("/api/v1/sales/", body, format="json")

    def stock(self):
        self.product.refresh_from_db()     # "relis le produit dans la base"
        return self.product.stock_quantity

    # ---------- Les tests : un par règle ----------

    def test_vente_baisse_le_stock_et_calcule_le_total(self):
        self.as_user(self.seller, self.shop)
        response = self.post_sale("3")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.data["total_amount"]), Decimal("1500.00"))   # 3 x 500
        self.assertEqual(self.stock(), Decimal("7"))

    def test_le_client_ne_choisit_pas_le_prix(self):
        self.as_user(self.seller, self.shop)
        # Un tricheur essaie d'envoyer son propre prix : 1 franc au lieu de 500.
        body = {"items": [{"product_id": str(self.product.id), "quantity": "2", "unit_price": "1"}]}
        response = self.client.post("/api/v1/sales/", body, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.data["total_amount"]), Decimal("1000.00"))   # 2 x 500, pas 2 x 1

    def test_stock_insuffisant_ne_change_rien(self):
        self.as_user(self.seller, self.shop)
        response = self.post_sale("11")        # on n'en a que 10
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.stock(), Decimal("10"))       # le stock n'a pas bougé
        self.assertEqual(Sale.objects.count(), 0)           # et aucune vente n'a été créée

    def test_meme_cle_ne_vend_qu_une_fois(self):
        self.as_user(self.seller, self.shop)
        key = uuid4()
        first = self.post_sale("2", key=key)
        second = self.post_sale("2", key=key)               # la même demande, rejouée
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)           # "déjà fait", pas 201
        self.assertEqual(first.data["number"], second.data["number"])
        self.assertEqual(Sale.objects.count(), 1)
        self.assertEqual(self.stock(), Decimal("8"))        # 10 - 2, et non 10 - 4

    def test_le_vendeur_ne_peut_pas_faire_de_remise(self):
        self.as_user(self.seller, self.shop)
        response = self.post_sale("1", discount_amount="100")
        self.assertEqual(response.status_code, 403)

    def test_le_patron_peut_faire_une_remise(self):
        self.as_user(self.owner, self.shop)
        response = self.post_sale("2", discount_amount="100")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.data["total_amount"]), Decimal("900.00"))    # 1000 - 100

    def test_le_vendeur_ne_peut_pas_annuler(self):
        self.as_user(self.seller, self.shop)
        sale_id = self.post_sale("2").data["id"]
        response = self.client.post(f"/api/v1/sales/{sale_id}/cancel/", {"reason": "erreur"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.stock(), Decimal("8"))        # rien n'a été rendu

    def test_le_patron_annule_et_le_stock_revient(self):
        self.as_user(self.seller, self.shop)
        sale_id = self.post_sale("4").data["id"]
        self.assertEqual(self.stock(), Decimal("6"))

        self.as_user(self.owner, self.shop)
        response = self.client.post(
            f"/api/v1/sales/{sale_id}/cancel/", {"reason": "Erreur de saisie"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "cancelled")
        self.assertEqual(self.stock(), Decimal("10"))       # le stock est revenu

        # Le cahier garde les DEUX lignes : on n'a rien effacé.
        types = set(StockMovement.objects.values_list("movement_type", flat=True))
        self.assertEqual(types, {"sale", "sale_return"})

    def test_on_ne_peut_pas_annuler_deux_fois(self):
        self.as_user(self.owner, self.shop)
        sale_id = self.post_sale("1").data["id"]
        self.client.post(f"/api/v1/sales/{sale_id}/cancel/", {"reason": "premier essai"}, format="json")
        response = self.client.post(f"/api/v1/sales/{sale_id}/cancel/", {"reason": "deuxième essai"}, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.stock(), Decimal("10"))       # rendu une seule fois

    def test_un_etranger_ne_peut_pas_vendre_dans_mon_commerce(self):
        # Un patron du commerce B essaie d'utiliser le commerce A.
        outsider = self.make_user(self.other_shop, "owner", "patron@b.ci")
        self.as_user(outsider, self.shop)       # il envoie l'identifiant du commerce A
        response = self.post_sale("1")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.stock(), Decimal("10"))