from django.shortcuts import render

# Create your views here.
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .mixins import ShopScopedMixin
from .models import Shop, ShopMembership
from .roles import PATRONS, PROPRIETAIRE
from .serializers import MemberCreateSerializer, MembershipSerializer, ShopSerializer

User = get_user_model()


class ShopViewSet(viewsets.ModelViewSet):
    """Les commerces où j'ai un badge. Pas de DELETE : on ne supprime pas un commerce."""
    serializer_class = ShopSerializer
    # On liste les actions permises : voir, créer, modifier (PATCH). Pas de PUT ni DELETE.
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):      # pour la documentation automatique
            return Shop.objects.none()
        # "Les commerces qui ont un badge actif à mon nom". distinct() = pas de doublon.
        return Shop.objects.filter(
            memberships__user=self.request.user, memberships__is_active=True, is_active=True
        ).distinct()

    @transaction.atomic        # tout ou rien : pas de commerce sans propriétaire
    def perform_create(self, serializer):
        shop = serializer.save()
        # Celui qui crée le commerce en devient le patron.
        ShopMembership.objects.create(shop=shop, user=self.request.user, role=ShopMembership.Role.OWNER)

    def perform_update(self, serializer):
        is_owner = ShopMembership.objects.filter(
            shop=serializer.instance, user=self.request.user,
            role=ShopMembership.Role.OWNER, is_active=True,
        ).exists()
        if not is_owner:
            raise PermissionDenied("Seul le propriétaire peut modifier le commerce.")
        serializer.save()


class MembershipViewSet(ShopScopedMixin, viewsets.ModelViewSet):
    """Les employés de MON commerce (celui de X-Shop-ID)."""
    queryset = ShopMembership.objects.select_related("user")
    serializer_class = MembershipSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    read_roles = PATRONS            # le patron et le gérant voient l'équipe
    write_roles = PROPRIETAIRE      # seul le patron ajoute ou modifie

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = MemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # 1. On crée le compte de l'employé...
        user = User.objects.create_user(
            email=data["email"], username=data["username"], password=data["password"]
        )
        # 2. ...et on lui donne un badge dans MON commerce.
        membership = ShopMembership.objects.create(
            shop=self.get_membership().shop, user=user, role=data["role"]
        )
        return Response(MembershipSerializer(membership).data, status=201)

    def perform_update(self, serializer):
        # Garde-fou : le patron ne peut pas se rétrograder ni se suspendre lui-même
        # (sinon le commerce se retrouverait sans patron).
        if serializer.instance.user_id == self.request.user.id:
            raise PermissionDenied("Vous ne pouvez pas modifier votre propre badge.")
        serializer.save()