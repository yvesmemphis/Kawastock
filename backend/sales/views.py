from django.shortcuts import render

# Create your views here.
import django_filters
from django.db import IntegrityError
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from shops.mixins import ShopScopedMixin
from shops.roles import PATRONS, TOUS, VENDEURS
from .models import Sale
from .serializers import SaleCreateSerializer, SaleSerializer
from .services import cancel_sale, create_sale


class SaleFilter(django_filters.FilterSet):
    # ?date_from=2026-10-01&date_to=2026-10-31
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = Sale
        fields = ["status", "sold_by"]


class SaleViewSet(ShopScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                  viewsets.GenericViewSet):
    queryset = Sale.objects.select_related("sold_by").prefetch_related("items")
    serializer_class = SaleSerializer
    filterset_class = SaleFilter
    ordering_fields = ["created_at", "total_amount"]

    read_roles = TOUS       # tout le monde peut regarder les ventes (le vendeur : seulement les siennes, voir plus bas)
    # Règles action par action : créer = les vendeurs, annuler = les patrons seulement.
    action_roles = {"create": VENDEURS, "cancel": PATRONS}

    def get_queryset(self):
        queryset = super().get_queryset()      # déjà filtré sur MON commerce par le mixin
        # Un vendeur ne voit que SES ventes, pas celles de ses collègues.
        if self.get_membership().role == "seller":
            queryset = queryset.filter(sold_by=self.request.user)
        return queryset

    def create(self, request):
        # 1. Le traducteur d'entrée vérifie la forme de la demande.
        serializer = SaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        membership = self.get_membership()

        # 2. Seuls le patron et le gérant peuvent accorder une remise.
        if data["discount_amount"] > 0 and membership.role not in PATRONS:
            raise PermissionDenied("Seuls le patron et le gérant peuvent accorder une remise.")

        key = data.get("idempotency_key")
        try:
            # 3. La fonction du cerveau fait tout le travail.
            sale, created = create_sale(
                shop=membership.shop, user=request.user, items=data["items"],
                discount_amount=data["discount_amount"], idempotency_key=key,
            )
        except IntegrityError:
            # Cas rare : deux demandes IDENTIQUES arrivées exactement en même temps.
            # La base a refusé la seconde. On renvoie alors la vente de la première.
            if not key:
                raise
            sale = Sale.objects.get(shop=membership.shop, idempotency_key=key)
            created = False

        # 201 = "vente créée" ; 200 = "cette vente existait déjà, la voici".
        return Response(SaleSerializer(sale).data, status=201 if created else 200)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        # Le motif est obligatoire : une annulation doit s'expliquer.
        reason = str(request.data.get("reason", "")).strip()
        if len(reason) < 3:
            raise ValidationError({"reason": "Le motif est obligatoire (3 caractères minimum)."})

        sale = cancel_sale(
            sale_id=self.get_object().id,       # get_object() vérifie que la vente est dans MON commerce
            shop=self.get_membership().shop, user=request.user, reason=reason,
        )
        return Response(SaleSerializer(sale).data)