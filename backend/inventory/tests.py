from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from catalog.models import Product
from inventory.models import StockMovement
from shops.models import Shop, ShopMembership


class StockAdjustmentTests(APITestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Commerce", slug="commerce")
        self.user = get_user_model().objects.create_user(
            email="owner@example.com", username="owner@example.com", password="password"
        )
        ShopMembership.objects.create(shop=self.shop, user=self.user, role="owner")
        self.product = Product.objects.create(
            shop=self.shop, sku="ITEM-1", name="Article", stock_quantity=Decimal("10")
        )
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_X_SHOP_ID=str(self.shop.id))

    def test_retrying_adjustment_with_same_key_changes_stock_once(self):
        key = str(uuid4())
        payload = {
            "product_id": str(self.product.id),
            "quantity_delta": "3",
            "movement_type": "adjustment",
            "reason": "Correction inventaire",
            "idempotency_key": key,
        }

        first = self.client.post("/api/v1/stock/adjustments/", payload, format="json")
        second = self.client.post("/api/v1/stock/adjustments/", payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, Decimal("13"))
        self.assertEqual(
            StockMovement.objects.filter(shop=self.shop, idempotency_key=key).count(), 1
        )
