from rest_framework import serializers
from .models import StockMovement


class StockMovementSerializer(serializers.ModelSerializer):
    """Pour AFFICHER une ligne du cahier."""

    # On ajoute le SKU et le nom du produit à côté de son identifiant,
    # pour que l'écran puisse afficher "CIMAF50 - Ciment" sans refaire une demande.
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True, default=None)

    class Meta:
        model = StockMovement
        fields = ["id", "product", "product_sku", "product_name", "movement_type",
                  "quantity_delta", "quantity_before", "quantity_after",
                  "source_type", "source_id", "reason",
                  "created_by", "created_by_email", "created_at"]


class AdjustmentSerializer(serializers.Serializer):
    """Pour RECEVOIR une demande de correction et la vérifier."""

    # Ce n'est pas un ModelSerializer : on ne crée pas directement une fiche,
    # on reçoit juste des informations qu'on transmettra à notre fonction.
    product_id = serializers.UUIDField()
    quantity_delta = serializers.DecimalField(max_digits=12, decimal_places=3)
    movement_type = serializers.ChoiceField(choices=["adjustment", "loss"], default="adjustment")
    reason = serializers.CharField(min_length=3)      # le motif est OBLIGATOIRE

    def validate_quantity_delta(self, value):
        # Un mouvement de 0 ne sert à rien.
        if value == 0:
            raise serializers.ValidationError("La variation ne peut pas être nulle.")
        return value