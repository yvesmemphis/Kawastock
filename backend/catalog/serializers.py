from rest_framework import serializers
from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        exclude = ["shop"]          # "tous les champs SAUF le commerce"

    def validate_name(self, value):
        # "Existe-t-il déjà une catégorie de ce nom dans CE commerce ?"
        shop = self.context["shop"]
        existing = Category.objects.filter(shop=shop, name__iexact=value)
        if self.instance:                       # si on modifie, on s'exclut soi-même
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("Cette catégorie existe déjà.")
        return value

    def validate_parent(self, value):
        # La catégorie parente doit être dans le même commerce.
        if value and value.shop_id != self.context["shop"].id:
            raise serializers.ValidationError("Catégorie invalide.")
        return value


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        exclude = ["shop"]
        # Le stock se verra, mais ne s'écrira pas ici (il bougera avec les ventes/achats).
        read_only_fields = ["stock_quantity"]

    def validate_sku(self, value):
        # "Ce SKU existe-t-il déjà dans CE commerce ?" (règle BR-02)
        shop = self.context["shop"]
        existing = Product.objects.filter(shop=shop, sku__iexact=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("Ce SKU existe déjà dans ce commerce.")
        return value

    def validate_category(self, value):
        # Empêche de ranger mon produit dans la catégorie d'un autre commerce.
        if value and value.shop_id != self.context["shop"].id:
            raise serializers.ValidationError("Catégorie invalide.")
        return value

    def to_representation(self, instance):
        # to_representation = "transforme le produit en JSON pour l'envoyer".
        # On laisse DRF faire son travail normal, puis on retouche le résultat.
        data = super().to_representation(instance)

        membership = self.context.get("membership")
        if membership and membership.role == "seller":
            data.pop("cost_price", None)    # on retire le prix d'achat de la réponse
        return data