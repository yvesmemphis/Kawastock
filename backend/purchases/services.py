from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from catalog.models import Product
from inventory.exceptions import ConflictError
from inventory.services import apply_stock_movement
from shops.services import next_number
from suppliers.models import Supplier
from .models import Purchase, PurchaseItem


def arrondi(valeur):
    # Arrondi à 2 décimales (pour l'argent), de façon explicite : 0.005 -> 0.01
    return Decimal(valeur).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@transaction.atomic        # "tout ou rien" : si une ligne est mauvaise, RIEN n'est créé
def create_purchase(*, shop, user, supplier_id, items, notes="", idempotency_key=None):
    if idempotency_key:
        existing = Purchase.objects.filter(
            shop=shop, idempotency_key=idempotency_key
        ).first()
        if existing:
            return existing

    # 1. Le fournisseur doit exister dans CE commerce, et être actif.
    supplier = Supplier.objects.filter(pk=supplier_id, shop=shop, is_active=True).first()
    if supplier is None:
        raise ValidationError({"supplier_id": "Fournisseur introuvable."})

    # 2. Les produits doivent exister dans CE commerce, et être actifs.
    wanted_ids = {line["product_id"] for line in items}
    products = {p.id: p for p in Product.objects.filter(shop=shop, id__in=wanted_ids, is_active=True)}
    if set(products) != wanted_ids:
        raise ValidationError({"items": "Un des produits est introuvable ou inactif."})

    # 3. On écrit l'en-tête du bon, avec le prochain numéro de ticket.
    purchase = Purchase.objects.create(
        shop=shop, supplier=supplier, created_by=user, notes=notes,
        reference=next_number(shop.id, "purchase_counter", "ACH"),
        idempotency_key=idempotency_key,
    )

    # 4. On écrit chaque ligne, et on additionne le total NOUS-MÊMES.
    total = Decimal("0")
    for line in items:
        PurchaseItem.objects.create(
            purchase=purchase,
            product=products[line["product_id"]],
            quantity_ordered=line["quantity_ordered"],
            unit_cost=line["unit_cost"],
        )
        total += line["quantity_ordered"] * line["unit_cost"]

    purchase.total_amount = arrondi(total)
    purchase.save(update_fields=["total_amount"])
    return purchase


@transaction.atomic
def receive_purchase(*, purchase_id, shop, user):
    # On pose un cadenas sur l'achat : deux clics rapides sur "Réceptionner"
    # ne doivent pas faire entrer le stock deux fois.
    purchase = get_object_or_404(
        Purchase.objects.select_for_update(), pk=purchase_id, shop=shop
    )

    if purchase.status == Purchase.Status.RECEIVED:
        return purchase

    # Seul un achat en brouillon ou commandé peut être réceptionné.
    if purchase.status not in (Purchase.Status.DRAFT, Purchase.Status.ORDERED):
        raise ConflictError("Cet achat ne peut plus être réceptionné.")

    for item in purchase.items.select_related("product"):
        # Pour l'instant, on réceptionne TOUT d'un coup (réception partielle = plus tard).
        quantity = item.quantity_ordered - item.quantity_received

        # LA MÊME fonction que pour les ajustements : elle augmente le stock
        # et écrit dans le cahier. Aucune règle de stock recopiée ici.
        apply_stock_movement(
            shop=shop, product_id=item.product_id, delta=quantity,
            movement_type="purchase_receipt", user=user,
            source_type="purchase", source_id=purchase.id,     # "ce mouvement vient de CET achat"
            reason=f"Réception {purchase.reference}",
        )

        item.quantity_received = item.quantity_ordered
        item.save(update_fields=["quantity_received"])

        # Le produit prend le dernier coût d'achat (voir la note plus bas).
        Product.objects.filter(pk=item.product_id).update(cost_price=item.unit_cost)

    purchase.status = Purchase.Status.RECEIVED
    purchase.received_at = timezone.now()
    purchase.save(update_fields=["status", "received_at"])
    return purchase


@transaction.atomic
def cancel_purchase(*, purchase_id, shop):
    purchase = get_object_or_404(
        Purchase.objects.select_for_update(), pk=purchase_id, shop=shop
    )
    # On n'annule que ce qui n'est pas encore entré en stock.
    # Annuler un achat REÇU demanderait un "retour fournisseur", qu'on verra plus tard.
    if purchase.status not in (Purchase.Status.DRAFT, Purchase.Status.ORDERED):
        raise ConflictError("Un achat déjà reçu ne peut pas être annulé.")
    purchase.status = Purchase.Status.CANCELLED
    purchase.save(update_fields=["status"])
    return purchase