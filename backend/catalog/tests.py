from decimal import Decimal

from rest_framework.test import APITestCase

from accounts.models import User
from shops.models import Shop, ShopMembership


class ProductDefaultStockThresholdTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            username="owner",
            password="test-password",
        )
        self.shop = Shop.objects.create(name="Quincaillerie", default_min_stock=Decimal("3.500"))
        ShopMembership.objects.create(shop=self.shop, user=self.user, role="owner")
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_X_SHOP_ID=str(self.shop.id))

    def test_new_products_inherit_shop_threshold_when_not_specified(self):
        response = self.client.post(
            "/api/v1/products/",
            {"sku": "SKU-1", "name": "Produit"},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["min_stock"], "3.500")

    def test_explicit_product_threshold_overrides_shop_default(self):
        response = self.client.post(
            "/api/v1/products/",
            {"sku": "SKU-2", "name": "Produit", "min_stock": "1.250"},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["min_stock"], "1.250")
