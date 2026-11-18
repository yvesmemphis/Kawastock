import uuid
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from .models import ShopMembership
from .permissions import HasShopRole
from .roles import TOUS, GESTION_STOCK


class ShopScopedMixin:
    # Deux gardiens, dans cet ordre.
    # D'abord "es-tu connecté ?", ensuite "ton rôle est-il le bon ?".
    permission_classes = [IsAuthenticated, HasShopRole]

    # Qui a le droit de REGARDER (GET) et qui a le droit d'ÉCRIRE (POST, PATCH, DELETE).
    # Chaque guichetier peut changer ces listes.
    read_roles = TOUS
    write_roles = GESTION_STOCK

    # Des exceptions action par action.
    # Exemple : {"cancel": PATRONS} veut dire "pour l'action cancel, regarde cette liste-là".
    action_roles = {}

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

    # Choisit la bonne liste de rôles selon ce qu'on essaie de faire.
    def get_allowed_roles(self, request):
        # self.action = le nom de l'action en cours ("list", "create", "cancel"...).
        # Pour une vue simple (APIView) il n'existe pas, d'où le getattr avec None.
        action = getattr(self, "action", None)

        # 1. Y a-t-il une règle spéciale pour cette action ? Alors on l'utilise.
        if action in self.action_roles:
            return self.action_roles[action]

        # 2. Sinon, règle habituelle : lire ou écrire.
        if request.method in SAFE_METHODS:
            return self.read_roles
        return self.write_roles

    def get_queryset(self):
        # "Je suis juste en train de fabriquer la documentation /api/docs/" :
        # personne n'est connecté, donc on renvoie une liste vide au lieu de planter.
        if getattr(self, "swagger_fake_view", False):          # GARDE 1
            return super().get_queryset().none()
        # Sinon : la liste normale, mais SEULEMENT ce qui appartient à mon commerce.
        return super().get_queryset().filter(shop=self.get_membership().shop)

    def perform_create(self, serializer):
        # Quand on crée quelque chose, on le range d'office dans mon commerce.
        # Le client ne peut pas "tricher" sur le commerce.
        serializer.save(shop=self.get_membership().shop)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Même raison que la garde 1 : pas de commerce à chercher pour la documentation.
        if getattr(self, "swagger_fake_view", False):          # GARDE 2
            return context
        # On donne le commerce et le badge aux serializers (ils en ont besoin
        # pour leurs vérifications, et pour cacher le prix d'achat au vendeur).
        context["shop"] = self.get_membership().shop
        context["membership"] = self.get_membership()
        return context