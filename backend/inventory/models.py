from django.db import models

# Create your models here.
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from catalog.models import Product
from shops.models import Shop


class StockMovement(models.Model):
    """Une ligne du cahier de bord : UN changement de stock, jamais modifié ensuite."""

    # Les raisons possibles d'un mouvement : une liste de choix fermée.
    class Type(models.TextChoices):
        PURCHASE_RECEIPT = "purchase_receipt", "Réception d'achat"
        SALE = "sale", "Vente"
        SALE_RETURN = "sale_return", "Annulation de vente"
        SUPPLIER_RETURN = "supplier_return", "Retour fournisseur"
        ADJUSTMENT = "adjustment", "Ajustement"
        LOSS = "loss", "Perte"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # PROTECT = "interdit d'effacer un commerce ou un produit qui a un historique".
    # On ne déchire pas une page du cahier.
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name="stock_movements")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements")

    movement_type = models.CharField(max_length=20, choices=Type.choices)

    # Le changement : +50 (on a reçu 50) ou -10 (on a vendu 10).
    quantity_delta = models.DecimalField(max_digits=12, decimal_places=3)

    # Le score AVANT et APRÈS : pratique pour vérifier que tout est cohérent.
    quantity_before = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=3)

    # D'où vient ce mouvement ? ex: source_type="sale", source_id = l'id de la vente.
    # Pour l'instant on ne s'en sert pas, mais ce sera utile avec les ventes et les achats.
    source_type = models.CharField(max_length=30, blank=True)
    source_id = models.UUIDField(null=True, blank=True)

    reason = models.TextField(blank=True)       # le motif écrit par la personne

    # Qui a fait ce changement ? SET_NULL = si la personne est supprimée, on garde la ligne.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)   # la date, mise automatiquement

    class Meta:
        ordering = ["-created_at"]      # les plus récents d'abord
        constraints = [
            # Un mouvement de "0" n'a aucun sens : on l'interdit.
            models.CheckConstraint(check=~Q(quantity_delta=0), name="movement_delta_not_zero"),
        ]
        indexes = [
            # Un index = l'index d'un livre : trouver vite sans tout relire.
            models.Index(fields=["shop", "-created_at"]),
            models.Index(fields=["product", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.product.sku} {self.quantity_delta:+} ({self.movement_type})"