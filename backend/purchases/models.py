from django.db import models

# Create your models here.
import uuid
from django.conf import settings
from django.db import models
from catalog.models import Product
from shops.models import Shop
from suppliers.models import Supplier


class Purchase(models.Model):
    """L'en-tête d'un bon de commande."""

    # Le parcours d'un achat : brouillon -> commandé -> reçu (ou annulé).
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        ORDERED = "ordered", "Commandé"
        RECEIVED = "received", "Reçu"
        CANCELLED = "cancelled", "Annulé"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT : on ne peut pas effacer un commerce ou un fournisseur qui a des achats.
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name="purchases")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")

    reference = models.CharField(max_length=30)             # ex: ACH-000001
    idempotency_key = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    # Le total est CALCULÉ par le serveur, jamais envoyé par le client (règle du cahier des charges).
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True, blank=True)   # rempli à la réception

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Deux achats du MÊME commerce ne peuvent pas avoir la même référence.
            # Deux commerces différents, oui (chacun a ses propres tickets).
            models.UniqueConstraint(fields=["shop", "reference"], name="uniq_purchase_ref_per_shop"),
            models.UniqueConstraint(
                fields=["shop", "idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False),
                name="uniq_purchase_idempotency_per_shop",
            ),
        ]

    def __str__(self):
        return self.reference


class PurchaseItem(models.Model):
    """Une ligne du bon : un produit, une quantité, un coût."""

    # CASCADE : si on supprime l'achat, ses lignes partent avec.
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")

    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    # Le coût gardé AU MOMENT de l'achat. Si le fournisseur change son prix plus tard,
    # l'historique de cet achat ne bouge pas.
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product.sku} x {self.quantity_ordered}"