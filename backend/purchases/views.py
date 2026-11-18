from django.shortcuts import render

# Create your views here.
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from django.db import IntegrityError
from rest_framework.response import Response
from shops.mixins import ShopScopedMixin
from shops.roles import GESTION_STOCK, LECTURE_STOCK
from .models import Purchase
from .serializers import PurchaseCreateSerializer, PurchaseSerializer
from .services import cancel_purchase, create_purchase, receive_purchase


# Ici on n'utilise PAS ModelViewSet : on ne veut ni modifier ni supprimer un achat
# par la voie classique. On assemble seulement les morceaux dont on a besoin :
#   ListModelMixin     -> lister les achats
#   RetrieveModelMixin -> voir UN achat
class PurchaseViewSet(ShopScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    queryset = Purchase.objects.select_related("supplier").prefetch_related("items__product")
    serializer_class = PurchaseSerializer
    filterset_fields = ["status", "supplier"]
    search_fields = ["reference", "supplier__name"]

    read_roles = LECTURE_STOCK      # le vendeur ne voit pas les achats
    write_roles = GESTION_STOCK     # créer, réceptionner, annuler

    def create(self, request):
        # 1. On vérifie la demande avec le traducteur d'ENTRÉE.
        serializer = PurchaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # 2. On appelle la fonction de création (c'est elle qui fait le vrai travail).
        shop = self.get_membership().shop
        key = data.get("idempotency_key")
        status = 201
        if key:
            purchase = Purchase.objects.filter(shop=shop, idempotency_key=key).first()
            if purchase:
                return Response(PurchaseSerializer(purchase).data, status=200)
        try:
            purchase = create_purchase(
                shop=shop, user=request.user,
                supplier_id=data["supplier_id"], items=data["items"], notes=data["notes"],
                idempotency_key=key,
            )
        except IntegrityError:
            if not key:
                raise
            purchase = Purchase.objects.get(shop=shop, idempotency_key=key)
            status = 200

        # 3. On répond avec le traducteur de SORTIE (201 = "créé").
        return Response(PurchaseSerializer(purchase).data, status=status)

    # @action ajoute une adresse en plus : POST /purchases/<id>/receive/
    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        # get_object() retrouve l'achat ET vérifie qu'il est dans mon commerce.
        purchase = receive_purchase(
            purchase_id=self.get_object().id,
            shop=self.get_membership().shop, user=request.user,
        )
        return Response(PurchaseSerializer(purchase).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        purchase = cancel_purchase(
            purchase_id=self.get_object().id, shop=self.get_membership().shop
        )
        return Response(PurchaseSerializer(purchase).data)