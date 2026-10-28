import django_filters
from django.db.models import F
from .models import Product


class ProductFilter(django_filters.FilterSet):
    # Un filtre "oui/non" qu'on appelle avec ?low_stock=true
    low_stock = django_filters.BooleanFilter(method="filter_low_stock")

    class Meta:
        model = Product
        # Ces filtres-là sont fabriqués automatiquement : ?category=2, ?is_active=true ...
        fields = ["category", "is_active", "brand", "unit"]

    def filter_low_stock(self, queryset, name, value):
        # F("min_stock") veut dire "la valeur de la colonne min_stock DE CE PRODUIT".
        # On compare donc, ligne par ligne : stock actuel <= seuil d'alerte ?
        is_low = {"stock_quantity__lte": F("min_stock")}
        if value:
            return queryset.filter(**is_low)     # ?low_stock=true  -> les produits en alerte
        return queryset.exclude(**is_low)        # ?low_stock=false -> les autres