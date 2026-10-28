from rest_framework.permissions import BasePermission


class HasShopRole(BasePermission):
    """
    Le gardien. Il regarde le badge de la personne dans CE commerce,
    et vérifie que son rôle est dans la liste autorisée pour cette action.
    """
    message = "Votre rôle ne vous permet pas de faire cette action."

    def has_permission(self, request, view):
        # 1. Quel est le rôle de la personne dans ce commerce ?
        role = view.get_membership().role
        # 2. Quels sont les rôles autorisés pour cette action ?
        # 3. Le rôle est-il dans la liste ? Oui = la porte s'ouvre, non = 403.
        return role in view.get_allowed_roles(request)