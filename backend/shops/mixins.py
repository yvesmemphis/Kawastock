import uuid
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from .models import ShopMembership
from .permissions import HasShopRole
from .roles import TOUS, GESTION_STOCK


class ShopScopedMixin:
    # NOUVEAU : deux gardiens, dans cet ordre.
    # D'abord "es-tu connecté ?", ensuite "ton rôle est-il le bon ?".
    # L'ordre compte : on ne peut pas lire le badge d'un inconnu.
    permission_classes = [IsAuthenticated, HasShopRole]

    # NOUVEAU : qui a le droit de REGARDER (GET) et qui a le droit d'ÉCRIRE
    # (POST, PATCH, DELETE). Chaque guichetier peut changer ces listes.
    read_roles = TOUS
    write_roles = GESTION_STOCK

    def get_membership(self):
        if not hasattr(self, "_membership"):
            raw_id = (self.request.headers.get("X-Shop-ID")
                      or self.request.query_params.get("shop_id"))
            try:
                shop_id = uuid.UUID(str(raw_id))
            except ValueError:
                raise PermissionDenied("Il faut indiquer le commerce (X-Shop-ID ou ?shop_id=).")

            membership = ShopMembership.objects.select_related("shop").filter(
                user=self.request.user,
                shop_id=shop_id,
                is_active=True,
                shop__is_active=True,
            ).first()

            if membership is None:
                raise PermissionDenied("Vous n'avez pas accès à ce commerce.")
            self._membership = membership
        return self._membership

    # NOUVEAU : choisit la bonne liste selon ce qu'on essaie de faire.
    def get_allowed_roles(self, request):
        # SAFE_METHODS = GET, HEAD, OPTIONS : les actions "je regarde sans toucher".
        if request.method in SAFE_METHODS:
            return self.read_roles
        return self.write_roles

    def get_queryset(self):
        return super().get_queryset().filter(shop=self.get_membership().shop)

    def perform_create(self, serializer):
        serializer.save(shop=self.get_membership().shop)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["shop"] = self.get_membership().shop
        context["membership"] = self.get_membership()   # NOUVEAU : le traducteur connaîtra le rôle
        return context