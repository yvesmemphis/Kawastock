from decimal import Decimal
from rest_framework import serializers
from .models import Sale, SaleItem


# ---------- Pour RECEVOIR une demande de vente ----------

class SaleLineInputSerializer(serializers.Serializer):
    """Une ligne envoyée : seulement QUEL produit et COMBIEN. Jamais de prix."""
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))


class SaleCreateSerializer(serializers.Serializer):
    items = SaleLineInputSerializer(many=True, allow_empty=False)    # au moins 1 ligne
    discount_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"), default=Decimal("0")
    )
    idempotency_key = serializers.UUIDField(required=False, allow_null=True)


# ---------- Pour AFFICHER un ticket ----------

class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        # On n'affiche PAS unit_cost_snapshot : le vendeur ne doit pas voir le prix d'achat.
        fields = ["product", "product_name_snapshot", "sku_snapshot",
                  "quantity", "unit_price", "line_total"]


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    sold_by_email = serializers.CharField(source="sold_by.email", read_only=True)

    class Meta:
        model = Sale
        fields = ["id", "number", "status", "subtotal", "discount_amount", "total_amount",
                  "sold_by", "sold_by_email", "created_at",
                  "cancelled_at", "cancel_reason", "items"]