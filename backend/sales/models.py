from django.db import models

# Create your models here.
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from catalog.models import Product
from shops.models import Shop


class Sale(models.Model):
    """L'en-tête d'un ticket de caisse."""

    class Status(models.TextChoices):
        COMPLETED = "completed", "Validée"
        CANCELLED = "cancelled", "Annulée"
    # Pas de "brouillon" ici : le panier se garde dans l'écran Vue,
    # et le serveur ne reçoit que la vente terminée.

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name="sales")
    sold_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales")

    number = models.CharField(max_length=30)                 # ex: V-000001
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)

    # Tous ces montants sont calculés par le serveur.
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)          # avant remise
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)      # à payer

    # La "clé de non-doublon" : un code unique envoyé par l'écran pour CETTE tentative de vente.
    idempotency_key = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # Rempli seulement si la vente est annulée : qui, quand, pourquoi.
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cancel_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Un numéro de vente unique PAR commerce.
            models.UniqueConstraint(fields=["shop", "number"], name="uniq_sale_number_per_shop"),
            # Une clé de non-doublon unique par commerce (quand elle est renseignée).
            # C'est la base de données elle-même qui interdit le doublon : c'est la dernière barrière.
            models.UniqueConstraint(
                fields=["shop", "idempotency_key"],
                condition=Q(idempotency_key__isnull=False),
                name="uniq_sale_idempotency_per_shop",
            ),
        ]
        indexes = [
            models.Index(fields=["shop", "-created_at"]),
            models.Index(fields=["shop", "status"]),
        ]

    def __str__(self):
        return self.number


class SaleItem(models.Model):
    """Une ligne du ticket."""

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="+")

    # Les "photos" du produit AU MOMENT de la vente. Si le produit change de nom
    # ou de prix demain, ce vieux ticket reste exact (règle BR-07).
    product_name_snapshot = models.CharField(max_length=200)
    sku_snapshot = models.CharField(max_length=80)

    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)         # prix réellement appliqué
    unit_cost_snapshot = models.DecimalField(max_digits=12, decimal_places=2) # pour calculer la marge plus tard
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self):
        return f"{self.sku_snapshot} x {self.quantity}"