from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from catalog.models import Product
from inventory.exceptions import ConflictError
from inventory.services import apply_stock_movement
from shops.services import next_number
from .models import Sale, SaleItem


def arrondi(valeur):
    # Même petite fonction que dans purchases : arrondi à 2 décimales pour l'argent.
    # (On la recopie ici pour l'instant ; on pourra la ranger à un seul endroit plus tard.)
    return Decimal(valeur).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@transaction.atomic        # RÈGLE 2 : tout ou rien
def create_sale(*, shop, user, items, discount_amount=Decimal("0"), idempotency_key=None):
    """Retourne (vente, created). created=False veut dire : cette vente existait déjà."""

    # RÈGLE 3 : pas de double vente.
    # Cette clé a-t-elle déjà servi ? Alors on renvoie la vente d'origine, sans rien refaire.
    if idempotency_key:
        existing = Sale.objects.filter(shop=shop, idempotency_key=idempotency_key).first()
        if existing:
            return existing, False

    # Si le client a envoyé deux lignes du même produit, on les additionne.
    wanted = {}
    for line in items:
        wanted[line["product_id"]] = wanted.get(line["product_id"], Decimal("0")) + line["quantity"]

    # On charge les produits ET on pose un cadenas dessus.
    # order_by("id") : toujours dans le même ordre. Si deux ventes veulent les mêmes
    # produits en même temps, elles se mettent en file au lieu de se bloquer mutuellement.
    products = {
        p.id: p
        for p in Product.objects.select_for_update()
        .filter(shop=shop, id__in=wanted.keys(), is_active=True)
        .order_by("id")
    }
    if set(products) != set(wanted):
        raise ValidationError({"items": "Un des produits est introuvable ou inactif."})

    # RÈGLE 1 : le serveur calcule tout, avec SES prix (ceux du catalogue).
    lines = []
    subtotal = Decimal("0")
    for product_id, quantity in wanted.items():
        product = products[product_id]
        line_total = arrondi(quantity * product.selling_price)
        subtotal += line_total
        lines.append((product, quantity, line_total))

    discount = arrondi(discount_amount)
    if discount > subtotal:
        raise ValidationError({"discount_amount": "La remise dépasse le sous-total."})

    # On écrit l'en-tête du ticket, avec le prochain numéro.
    sale = Sale.objects.create(
        shop=shop, sold_by=user, status=Sale.Status.COMPLETED,
        number=next_number(shop.id, "sale_counter", "V"),
        subtotal=arrondi(subtotal), discount_amount=discount,
        total_amount=arrondi(subtotal - discount),
        idempotency_key=idempotency_key,
    )

    # On écrit chaque ligne, et on fait baisser le stock avec LA fonction habituelle.
    # Si le stock est insuffisant, apply_stock_movement lève une erreur 409 et
    # la transaction annule TOUT, y compris l'en-tête créé juste au-dessus.
    for product, quantity, line_total in lines:
        SaleItem.objects.create(
            sale=sale, product=product,
            product_name_snapshot=product.name, sku_snapshot=product.sku,
            quantity=quantity, unit_price=product.selling_price,
            unit_cost_snapshot=product.cost_price, line_total=line_total,
        )
        apply_stock_movement(
            shop=shop, product_id=product.id, delta=-quantity,    # le signe moins : le stock BAISSE
            movement_type="sale", user=user,
            source_type="sale", source_id=sale.id,
            reason=f"Vente {sale.number}",
        )

    return sale, True


@transaction.atomic
def cancel_sale(*, sale_id, shop, user, reason):
    # Cadenas sur la vente : deux clics sur "Annuler" ne doivent pas rendre le stock deux fois.
    sale = get_object_or_404(Sale.objects.select_for_update(), pk=sale_id, shop=shop)

    if sale.status != Sale.Status.COMPLETED:
        raise ConflictError("Cette vente est déjà annulée.")

    # RÈGLE 4 : on ne gomme rien, on ajoute des lignes INVERSES dans le cahier.
    for item in sale.items.all():
        apply_stock_movement(
            shop=shop, product_id=item.product_id, delta=item.quantity,   # le signe plus : le stock REVIENT
            movement_type="sale_return", user=user,
            source_type="sale", source_id=sale.id,
            reason=f"Annulation {sale.number} : {reason}",
        )

    sale.status = Sale.Status.CANCELLED
    sale.cancelled_at = timezone.now()
    sale.cancelled_by = user
    sale.cancel_reason = reason
    sale.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancel_reason"])
    return sale