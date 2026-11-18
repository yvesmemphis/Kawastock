import csv
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from catalog.models import Product
from sales.models import Sale, SaleItem
from shops.models import Shop, ShopMembership


User = get_user_model()


class ReportsAPITests(APITestCase):
    def setUp(self):
        self.shop = Shop.objects.create(name="Commerce rapports", slug="commerce-rapports")
        self.other_shop = Shop.objects.create(name="Autre commerce rapports", slug="autre-commerce-rapports")
        self.owner = self.make_member("owner", "patron@example.com", self.shop)
        self.viewer = self.make_member("viewer", "comptable@example.com", self.shop)
        self.seller = self.make_member("seller", "vendeur@example.com", self.shop)
        self.stock_manager = self.make_member("stock_manager", "stock@example.com", self.shop)
        self.other_owner = self.make_member("owner", "autre-patron@example.com", self.other_shop)

        self.product = Product.objects.create(
            shop=self.shop,
            sku="RAP-1",
            name="Produit rapport",
            cost_price=Decimal("10.00"),
            selling_price=Decimal("20.00"),
            stock_quantity=Decimal("3.000"),
            min_stock=Decimal("3.000"),
        )
        self.second_product = Product.objects.create(
            shop=self.shop,
            sku="RAP-2",
            name="Produit normal",
            cost_price=Decimal("5.00"),
            selling_price=Decimal("15.00"),
            stock_quantity=Decimal("10.000"),
            min_stock=Decimal("2.000"),
        )
        self.other_product = Product.objects.create(
            shop=self.other_shop,
            sku="AUTRE-1",
            name="Produit autre commerce",
            cost_price=Decimal("1.00"),
            selling_price=Decimal("900.00"),
            stock_quantity=Decimal("2.000"),
            min_stock=Decimal("1.000"),
        )

        self.first_sale = self.make_sale(
            self.shop, self.owner, "R-000001", Sale.Status.COMPLETED,
            subtotal="40.00", discount="5.00", total="35.00",
            lines=[(self.product, "2.000", "10.00", "40.00")],
        )
        self.second_sale = self.make_sale(
            self.shop, self.seller, "R-000002", Sale.Status.COMPLETED,
            subtotal="15.00", discount="0.00", total="15.00",
            lines=[(self.product, "1.000", "10.00", "15.00")],
        )
        self.cancelled_sale = self.make_sale(
            self.shop, self.owner, "R-000003", Sale.Status.CANCELLED,
            subtotal="200.00", discount="0.00", total="200.00",
            lines=[(self.second_product, "4.000", "5.00", "50.00")],
        )
        self.other_sale = self.make_sale(
            self.other_shop, self.other_owner, "O-000001", Sale.Status.COMPLETED,
            subtotal="900.00", discount="0.00", total="900.00",
            lines=[(self.other_product, "1.000", "1.00", "900.00")],
        )

        self.today = timezone.localdate()
        self.yesterday = self.today - timedelta(days=1)
        Sale.objects.filter(pk=self.first_sale.pk).update(
            created_at=timezone.now() - timedelta(hours=2)
        )
        Sale.objects.filter(pk=self.second_sale.pk).update(
            created_at=timezone.now() - timedelta(hours=1)
        )
        Sale.objects.filter(pk=self.cancelled_sale.pk).update(
            created_at=timezone.now() - timedelta(minutes=30)
        )
        Sale.objects.filter(pk=self.other_sale.pk).update(
            created_at=timezone.now() - timedelta(minutes=15)
        )

    def make_member(self, role, email, shop):
        user = User.objects.create_user(username=email, email=email, password=None)
        ShopMembership.objects.create(shop=shop, user=user, role=role)
        return user

    def make_sale(self, shop, user, number, status, *, subtotal, discount, total, lines):
        sale = Sale.objects.create(
            shop=shop,
            sold_by=user,
            number=number,
            status=status,
            subtotal=Decimal(subtotal),
            discount_amount=Decimal(discount),
            total_amount=Decimal(total),
        )
        for product, quantity, unit_cost, line_total in lines:
            SaleItem.objects.create(
                sale=sale,
                product=product,
                product_name_snapshot=product.name,
                sku_snapshot=product.sku,
                quantity=Decimal(quantity),
                unit_price=product.selling_price,
                unit_cost_snapshot=Decimal(unit_cost),
                line_total=Decimal(line_total),
            )
        return sale

    def authenticate(self, user, shop=None):
        self.client.force_authenticate(user=user)
        self.client.credentials(HTTP_X_SHOP_ID=str((shop or self.shop).id))

    def report_period(self):
        return {"date_from": self.today.isoformat(), "date_to": self.today.isoformat()}

    def test_sales_report_aggregates_only_completed_sales_for_selected_shop_and_period(self):
        self.authenticate(self.owner)

        response = self.client.get("/api/v1/reports/sales/", self.report_period())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"], {
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
            "sales_count": 2,
            "gross_amount": "55.00",
            "discount_amount": "5.00",
            "net_amount": "50.00",
            "cost_of_goods": "30.00",
            "estimated_margin": "20.00",
            "items_without_cost": 0,
            "margin_reliable": True,
        })
        self.assertEqual(response.data["by_day"], [{
            "day": self.today.isoformat(),
            "sales_count": 2,
            "net_amount": "50.00",
        }])
        self.assertEqual(response.data["top_products"], [{
            "product_id": str(self.product.id),
            "sku": self.product.sku,
            "name": self.product.name,
            "quantity": "3",
            "amount": "55.00",
        }])

    def test_sales_report_accepts_custom_period_and_rejects_invalid_dates(self):
        self.authenticate(self.owner)

        response = self.client.get(
            "/api/v1/reports/sales/",
            {"date_from": self.yesterday.isoformat(), "date_to": self.yesterday.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["sales_count"], 0)
        self.assertEqual(response.data["summary"]["net_amount"], "0.00")

        invalid_format = self.client.get(
            "/api/v1/reports/sales/", {"date_from": "not-a-date"}
        )
        self.assertEqual(invalid_format.status_code, 400)
        self.assertIn("date_from", invalid_format.data)

        reversed_period = self.client.get(
            "/api/v1/reports/sales/",
            {"date_from": self.today.isoformat(), "date_to": self.yesterday.isoformat()},
        )
        self.assertEqual(reversed_period.status_code, 400)
        self.assertIn("date_from", reversed_period.data)

    def test_sales_report_requires_report_role_and_shop_membership(self):
        self.authenticate(self.seller)
        seller_response = self.client.get("/api/v1/reports/sales/", self.report_period())
        self.assertEqual(seller_response.status_code, 403)

        self.authenticate(self.stock_manager)
        stock_manager_response = self.client.get("/api/v1/reports/sales/", self.report_period())
        self.assertEqual(stock_manager_response.status_code, 403)

        self.authenticate(self.viewer)
        viewer_response = self.client.get("/api/v1/reports/sales/", self.report_period())
        self.assertEqual(viewer_response.status_code, 200)

        self.authenticate(self.other_owner, self.shop)
        outsider_response = self.client.get("/api/v1/reports/sales/", self.report_period())
        self.assertEqual(outsider_response.status_code, 403)

    def test_sales_export_returns_scoped_csv_with_cancelled_sales_and_period(self):
        self.authenticate(self.owner)

        response = self.client.get("/api/v1/reports/sales/export/", self.report_period())

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        content = response.content.decode("utf-8-sig")
        rows = list(csv.reader(StringIO(content), delimiter=";"))
        self.assertEqual(rows[0], ["Numéro", "Date", "Vendeur", "Statut", "Sous-total", "Remise", "Total"])
        self.assertEqual({row[0] for row in rows[1:]}, {
            "R-000001", "R-000002", "R-000003",
        })
        cancelled_row = next(row for row in rows[1:] if row[0] == "R-000003")
        self.assertEqual(cancelled_row[3], "Annulée")
        self.assertNotIn("O-000001", content)

    def test_dashboard_and_low_stock_are_limited_to_selected_shop(self):
        self.authenticate(self.owner)

        dashboard = self.client.get("/api/v1/dashboard/summary/", self.report_period())
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data["sales"]["sales_count"], 2)
        self.assertEqual(dashboard.data["low_stock_count"], 1)
        self.assertEqual(dashboard.data["stock_value"], "80.00")

        low_stock = self.client.get("/api/v1/reports/low-stock/")
        self.assertEqual(low_stock.status_code, 200)
        self.assertEqual(low_stock.data["count"], 1)
        self.assertEqual(low_stock.data["results"][0]["sku"], self.product.sku)
        self.assertEqual(low_stock.data["results"][0]["missing"], "0.000")

    def test_low_stock_permissions_and_authentication(self):
        self.authenticate(self.seller)
        seller_response = self.client.get("/api/v1/reports/low-stock/")
        self.assertEqual(seller_response.status_code, 403)

        self.authenticate(self.stock_manager)
        stock_response = self.client.get("/api/v1/reports/low-stock/")
        self.assertEqual(stock_response.status_code, 200)

        self.client.force_authenticate(user=None)
        self.client.credentials()
        anonymous_response = self.client.get(
            "/api/v1/reports/sales/", self.report_period(),
            HTTP_X_SHOP_ID=str(self.shop.id),
        )
        self.assertEqual(anonymous_response.status_code, 403)
