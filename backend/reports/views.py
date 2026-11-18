from django.shortcuts import render

# Create your views here.
import csv
from datetime import date, timedelta

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from inventory.models import StockMovement
from inventory.serializers import StockMovementSerializer
from sales.models import Sale
from shops.mixins import ShopScopedMixin
from shops.roles import LECTURE_STOCK, RAPPORTS
from . import services

MAX_DAYS = 366      # on refuse les périodes de plus d'un an (pour ne pas faire ramer le serveur)


def parse_period(request, default_days=0):
    """
    Lit ?date_from=2026-10-01&date_to=2026-10-31 dans l'adresse.
    Sans rien : par défaut, de (aujourd'hui - default_days) jusqu'à aujourd'hui.
    """
    # localdate() = la date d'AUJOURD'HUI chez vous (fuseau Africa/Abidjan de settings.py).
    today = timezone.localdate()

    def read(name, default):
        raw = request.query_params.get(name)
        if not raw:
            return default
        try:
            return date.fromisoformat(raw)
        except ValueError:
            raise ValidationError({name: "Format attendu : AAAA-MM-JJ (exemple 2026-10-31)."})

    date_from = read("date_from", today - timedelta(days=default_days))
    date_to = read("date_to", today)

    if date_from > date_to:
        raise ValidationError({"date_from": "La date de début est après la date de fin."})
    if (date_to - date_from).days > MAX_DAYS:
        raise ValidationError({"date_to": "Période trop longue (maximum 366 jours)."})
    return date_from, date_to


# Ces vues sont des APIView : plus simples qu'un ViewSet, car ici il n'y a
# ni "créer" ni "modifier", seulement UNE réponse à une question.
# On garde quand même ShopScopedMixin : il vérifie le badge et le rôle comme partout.

class DashboardSummaryView(ShopScopedMixin, APIView):
    read_roles = RAPPORTS

    def get(self, request):
        shop = self.get_membership().shop
        date_from, date_to = parse_period(request)      # par défaut : aujourd'hui seulement

        recent = StockMovement.objects.filter(shop=shop).select_related("product", "created_by")[:5]
        return Response({
            "sales": services.sales_summary(shop, date_from, date_to),
            "top_products": services.top_products(shop, date_from, date_to),
            "low_stock_count": services.low_stock(shop).count(),
            "stock_value": services.stock_value(shop),
            "recent_movements": StockMovementSerializer(recent, many=True).data,
        })


class SalesReportView(ShopScopedMixin, APIView):
    read_roles = RAPPORTS

    def get(self, request):
        shop = self.get_membership().shop
        date_from, date_to = parse_period(request, default_days=29)     # par défaut : 30 derniers jours
        return Response({
            "summary": services.sales_summary(shop, date_from, date_to),
            "by_day": services.daily_sales(shop, date_from, date_to),
            "top_products": services.top_products(shop, date_from, date_to, limit=10),
        })


class LowStockView(ShopScopedMixin, APIView):
    read_roles = LECTURE_STOCK

    def get(self, request):
        shop = self.get_membership().shop
        products = services.low_stock(shop).select_related("category").order_by("stock_quantity", "name")
        results = [
            {
                "id": str(p.id), "sku": p.sku, "name": p.name, "unit": p.unit,
                "category": p.category.name if p.category else None,
                "stock_quantity": str(p.stock_quantity),
                "min_stock": str(p.min_stock),
                "missing": str(p.min_stock - p.stock_quantity),    # combien il manque pour atteindre le seuil
            }
            for p in products
        ]
        return Response({"count": len(results), "results": results})


class SalesExportView(ShopScopedMixin, APIView):
    read_roles = RAPPORTS

    def get(self, request):
        shop = self.get_membership().shop
        date_from, date_to = parse_period(request, default_days=29)

        # Toutes les ventes de la période (annulées incluses : la colonne "Statut" les distingue).
        sales = (
            Sale.objects.filter(shop=shop, created_at__date__gte=date_from, created_at__date__lte=date_to)
            .select_related("sold_by").order_by("created_at")
        )

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="ventes_{date_from}_{date_to}.csv"'

        # Deux astuces pour qu'Excel en français l'ouvre correctement :
        # 1. le "BOM" (\ufeff) au début : sans lui, les accents deviennent "Ã©".
        # 2. le séparateur ";" au lieu de "," : en français, la virgule sert déjà aux décimales.
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(["Numéro", "Date", "Vendeur", "Statut", "Sous-total", "Remise", "Total"])

        def comma(amount):
            return str(amount).replace(".", ",")      # 1500.00 -> 1500,00 (Excel français)

        for sale in sales.iterator():       # iterator = on lit par petits paquets, sans tout charger en mémoire
            writer.writerow([
                sale.number,
                timezone.localtime(sale.created_at).strftime("%d/%m/%Y %H:%M"),
                sale.sold_by.email,
                sale.get_status_display(),
                comma(sale.subtotal), comma(sale.discount_amount), comma(sale.total_amount),
            ])
        return response