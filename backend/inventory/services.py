from django.db import transaction
from django.shortcuts import get_object_or_404
from catalog.models import Product
from .exceptions import InsufficientStock
from .models import StockMovement


# @transaction.atomic = "tout ou rien".
# Si UNE seule étape échoue, TOUTES les étapes sont annulées, comme si rien ne s'était passé.
# Sans ça, on pourrait avoir un stock changé mais aucune ligne dans le cahier.
@transaction.atomic
def apply_stock_movement(*, shop, product_id, delta, movement_type, user,
                         reason="", source_type="", source_id=None):
    """
    Change le stock d'un produit ET écrit la ligne dans le cahier.
    delta > 0 : le stock augmente.  delta < 0 : le stock diminue.
    """

    # 1. On va chercher le produit, mais seulement dans CE commerce.
    #    select_for_update() = "je pose un cadenas sur ce produit pendant que je travaille",
    #    pour que deux vendeurs ne modifient pas le même stock en même temps.
    product = get_object_or_404(
        Product.objects.select_for_update(), pk=product_id, shop=shop
    )

    # 2. On calcule le nouveau score.
    before = product.stock_quantity
    after = before + delta

    # 3. Règle BR-04 : le stock ne peut jamais être négatif.
    if after < 0:
        raise InsufficientStock(product, before, -delta)

    # 4. On met à jour le score au tableau.
    product.stock_quantity = after
    product.save(update_fields=["stock_quantity", "updated_at"])

    # 5. On écrit la ligne dans le cahier.
    return StockMovement.objects.create(
        shop=shop, product=product, movement_type=movement_type,
        quantity_delta=delta, quantity_before=before, quantity_after=after,
        source_type=source_type, source_id=source_id,
        reason=reason, created_by=user,
    )