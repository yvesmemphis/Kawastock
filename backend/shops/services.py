from .models import Shop


def next_number(shop_id, counter_field, prefix):
    """
    Distribue le prochain numéro : ACH-000001, ACH-000002, ...
    counter_field = quel compteur utiliser ("purchase_counter" ou "sale_counter").
    À appeler à l'intérieur d'une transaction (@transaction.atomic).
    """
    # select_for_update = un cadenas sur la fiche du commerce, pour que deux
    # personnes qui créent un achat en même temps n'obtiennent pas le MÊME numéro.
    shop = Shop.objects.select_for_update().get(pk=shop_id)

    # On avance le compteur d'un cran.
    value = getattr(shop, counter_field) + 1
    Shop.objects.filter(pk=shop_id).update(**{counter_field: value})

    # f"{value:06d}" = le nombre sur 6 chiffres, complété par des zéros : 1 -> 000001
    return f"{prefix}-{value:06d}"