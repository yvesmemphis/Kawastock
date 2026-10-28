from django.shortcuts import render

# Create your views here.
import django_filters
from rest_framework import generics, viewsets
from rest_framework.response import Response
from shops.mixins import ShopScopedMixin
from shops.roles import GESTION_STOCK, LECTURE_STOCK
from .models import StockMovement
from .serializers import AdjustmentSerializer, StockMovementSerializer
from .services import apply_stock_movement


class StockMovementFilter(django_filters.FilterSet):
    # ?date_from=2026-10-01&date_to=2026-10-31 : tous les mouvements du mois d'octobre
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = StockMovement
        fields = ["product", "movement_type"]     # ?product=<id>&movement_type=sale


# Guichet 1 : LIRE le cahier.
# ReadOnlyModelViewSet = un guichetier qui sait seulement lister et montrer UNE ligne.
# Il ne sait pas créer, modifier ni supprimer : le cahier ne se modifie jamais à la main.
class StockMovementViewSet(ShopScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = StockMovement.objects.select_related("product", "created_by")
    serializer_class = StockMovementSerializer
    filterset_class = StockMovementFilter
    read_roles = LECTURE_STOCK             # le vendeur n'a PAS le droit de lire
    ordering_fields = ["created_at"]


# Guichet 2 : CORRIGER le stock.
class StockAdjustmentView(ShopScopedMixin, generics.GenericAPIView):
    queryset = StockMovement.objects.all()
    serializer_class = AdjustmentSerializer
    write_roles = GESTION_STOCK            # seuls patron, gérant, gestionnaire de stock

    def post(self, request):
        # 1. Le traducteur vérifie la demande (motif présent, nombre valide...).
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # 2. Une perte retire TOUJOURS du stock, même si la personne a écrit un "+".
        delta = data["quantity_delta"]
        if data["movement_type"] == "loss":
            delta = -abs(delta)

        # 3. On appelle LA fonction qui sait changer le stock en sécurité.
        #    C'est elle qui vérifie que le produit est bien dans CE commerce.
        movement = apply_stock_movement(
            shop=self.get_membership().shop,
            product_id=data["product_id"],
            delta=delta,
            movement_type=data["movement_type"],
            user=request.user,
            reason=data["reason"],
        )

        # 4. On renvoie la ligne du cahier qu'on vient d'écrire (201 = "créé").
        return Response(StockMovementSerializer(movement).data, status=201)