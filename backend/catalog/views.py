from rest_framework import viewsets
from shops.mixins import ShopScopedMixin
from .filters import ProductFilter                      # NOUVEAU
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


class CategoryViewSet(ShopScopedMixin, viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ["name"]                            # NOUVEAU : ?search=clou


class ProductViewSet(ShopScopedMixin, viewsets.ModelViewSet):
    # select_related("category") : "va chercher le nom de la catégorie en même temps".
    # Sans lui, Django ferait une demande à la base pour CHAQUE produit.
    queryset = Product.objects.select_related("category")
    serializer_class = ProductSerializer

    filterset_class = ProductFilter                     # NOUVEAU : utilise notre filtre
    search_fields = ["name", "sku", "barcode", "brand"] # NOUVEAU : dans quelles colonnes chercher
    ordering_fields = ["name", "sku", "selling_price", "stock_quantity", "created_at"]  # NOUVEAU : tris permis

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])