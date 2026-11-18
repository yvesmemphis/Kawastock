from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from shops.mixins import ShopScopedMixin
from shops.roles import LECTURE_STOCK
from .models import Supplier
from .serializers import SupplierSerializer


class SupplierViewSet(ShopScopedMixin, viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    search_fields = ["name", "phone"]              # ?search=...
    filterset_fields = ["is_active"]               # ?is_active=true

    # Le vendeur n'a pas besoin de connaître les fournisseurs (ni leurs contacts).
    # L'écriture reste réservée à GESTION_STOCK, c'est le réglage par défaut du mixin.
    read_roles = LECTURE_STOCK

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])