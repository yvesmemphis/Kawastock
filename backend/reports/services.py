from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDate

from catalog.models import Product
from sales.models import Sale, SaleItem

# Le type de résultat quand on MULTIPLIE deux colonnes (quantité x coût) :
# on prévoit beaucoup de décimales pour ne rien perdre en route.
PRODUIT = DecimalField(max_digits=24, decimal_places=5)


def money(value):
    """
    Transforme un montant en TEXTE avec 2 décimales : "1400.00".
    Pourquoi du texte ? Si on envoyait un nombre décimal brut, le JSON le
    transformerait en "float" (nombre à virgule flottante) qui fait des erreurs
    d'arrondi (0.1 + 0.2 = 0.30000000000000004). Pour l'argent, c'est interdit (BR-03).
    """
    return str(Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def completed_sales(shop, date_from, date_to):
    """Les ventes VALIDÉES de CE commerce, entre deux dates (incluses)."""
    return Sale.objects.filter(
        shop=shop,
        status=Sale.Status.COMPLETED,            # les annulées sont exclues
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )


def sales_summary(shop, date_from, date_to):
    sales = completed_sales(shop, date_from, date_to)

    # aggregate = une calculatrice qui additionne une colonne pour toutes les lignes.
    totals = sales.aggregate(
        count=Count("id"),
        gross=Sum("subtotal"),
        discounts=Sum("discount_amount"),
        net=Sum("total_amount"),
    )

    # Les lignes de ces ventes-là : on y calcule le coût des marchandises vendues.
    items = SaleItem.objects.filter(sale__in=sales)
    costs = items.aggregate(
        cost=Sum(ExpressionWrapper(F("quantity") * F("unit_cost_snapshot"), output_field=PRODUIT)),
        # Combien de lignes ont été vendues avec un coût à 0 ? (= coût jamais renseigné)
        without_cost=Count("id", filter=Q(unit_cost_snapshot=0)),
    )

    net = Decimal(totals["net"] or 0)       # "or 0" : s'il n'y a aucune vente, la somme vaut None
    cost = Decimal(costs["cost"] or 0)

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "sales_count": totals["count"],
        "gross_amount": money(totals["gross"]),
        "discount_amount": money(totals["discounts"]),
        "net_amount": money(net),
        "cost_of_goods": money(cost),
        "estimated_margin": money(net - cost),
        "items_without_cost": costs["without_cost"],
        "margin_reliable": costs["without_cost"] == 0,
    }


def top_products(shop, date_from, date_to, limit=5):
    """Les produits les plus vendus (en quantité)."""
    items = SaleItem.objects.filter(sale__in=completed_sales(shop, date_from, date_to))
    rows = (
        items.values("product_id", "sku_snapshot", "product_name_snapshot")   # "regroupe par produit"
        .annotate(total_quantity=Sum("quantity"), total_amount=Sum("line_total"))
        .order_by("-total_quantity")[:limit]
    )
    return [
        {
            "product_id": str(r["product_id"]),
            "sku": r["sku_snapshot"],
            "name": r["product_name_snapshot"],
            "quantity": str(r["total_quantity"]),
            "amount": money(r["total_amount"]),
        }
        for r in rows
    ]


def daily_sales(shop, date_from, date_to):
    """Un total par jour (pour tracer une courbe plus tard dans Vue)."""
    rows = (
        completed_sales(shop, date_from, date_to)
        .annotate(day=TruncDate("created_at"))      # on garde seulement la date, sans l'heure
        .values("day")                              # "regroupe par jour"
        .annotate(sales_count=Count("id"), day_net=Sum("total_amount"))
        .order_by("day")
    )
    return [
        {"day": r["day"].isoformat(), "sales_count": r["sales_count"], "net_amount": money(r["day_net"])}
        for r in rows
    ]


def low_stock(shop):
    """Produits actifs dont le stock est inférieur ou égal au seuil d'alerte."""
    return Product.objects.filter(shop=shop, is_active=True, stock_quantity__lte=F("min_stock"))


def stock_value(shop):
    """Valeur estimée du stock = pour chaque produit, stock x coût d'achat."""
    total = Product.objects.filter(shop=shop, is_active=True).aggregate(
        value=Sum(ExpressionWrapper(F("stock_quantity") * F("cost_price"), output_field=PRODUIT))
    )["value"]
    return money(total)