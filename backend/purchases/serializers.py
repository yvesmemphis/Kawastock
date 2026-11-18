from decimal import Decimal

from rest_framework import serializers
from .models import Purchase, PurchaseItem


# ---------- Pour RECEVOIR une demande de création ----------

class PurchaseItemInputSerializer(serializers.Serializer):
    """Une ligne envoyée par le client."""
    product_id = serializers.UUIDField()
    quantity_ordered = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001")
    )
    unit_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0")
    )


class PurchaseCreateSerializer(serializers.Serializer):
    """Le bon de commande complet envoyé par le client."""
    supplier_id = serializers.UUIDField()
    idempotency_key = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    items = PurchaseItemInputSerializer(many=True, allow_empty=False)   # au moins 1 ligne

    def validate_items(self, items):
        # Le même produit ne doit pas apparaître deux fois dans le même bon.
        ids = [line["product_id"] for line in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Un produit apparaît plusieurs fois.")
        return items


# ---------- Pour AFFICHER un achat ----------

class PurchaseItemSerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = PurchaseItem
        fields = ["id", "product", "product_sku", "product_name",
                  "quantity_ordered", "quantity_received", "unit_cost"]


class PurchaseSerializer(serializers.ModelSerializer):
    items = PurchaseItemSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)

    class Meta:
        model = Purchase
        fields = ["id", "reference", "status", "supplier", "supplier_name",
                  "total_amount", "notes", "created_at", "received_at", "items"]