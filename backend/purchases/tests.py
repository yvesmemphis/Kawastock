from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from catalog.models import Product
from inventory.models import StockMovement
from purchases.models import Purchase
from shops.models import Shop, ShopMembership
from suppliers.models import Supplier


class PurchaseOfflineRetryTests(APITestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Commerce", slug="commerce")
        self.user = get_user_model().objects.create_user(
            email="owner@example.com", username="owner@example.com", password="password"
        )
        ShopMembership.objects.create(shop=self.shop, user=self.user, role="owner")
        self.product = Product.objects.create(
            shop=self.shop, sku="ITEM-1", name="Article", stock_quantity=Decimal("5")
        )
        self.supplier = Supplier.objects.create(shop=self.shop, name="Fournisseur")
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_X_SHOP_ID=str(self.shop.id))

    def purchase_payload(self, key):
        return {
            "supplier_id": str(self.supplier.id),
            "idempotency_key": str(key),
            "items": [{
                "product_id": str(self.product.id),
                "quantity_ordered": "4",
                "unit_cost": "2.50",
            }],
        }

    def test_retrying_purchase_creation_with_same_key_creates_one_purchase(self):
        key = uuid4()
        payload = self.purchase_payload(key)

        first = self.client.post("/api/v1/purchases/", payload, format="json")
        second = self.client.post("/api/v1/purchases/", payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Purchase.objects.filter(shop=self.shop, idempotency_key=key).count(), 1)
        self.assertEqual(StockMovement.objects.filter(shop=self.shop).count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, Decimal("5"))

    def test_repeating_purchase_receipt_does_not_add_stock_twice(self):
        created = self.client.post(
            "/api/v1/purchases/", self.purchase_payload(uuid4()), format="json"
        )
        url = f"/api/v1/purchases/{created.data['id']}/receive/"

        first = self.client.post(url, {}, format="json")
        second = self.client.post(url, {}, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["status"], Purchase.Status.RECEIVED)
        self.assertEqual(StockMovement.objects.filter(shop=self.shop).count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, Decimal("9"))
