from django.db import models

# Create your models here.
import uuid
from django.db import models
from shops.models import Shop


class Supplier(models.Model):
    """Un fournisseur. Il appartient à UN commerce (comme les produits)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # CASCADE = si on supprime le commerce, ses fournisseurs partent avec.
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="suppliers")

    name = models.CharField(max_length=180)
    phone = models.CharField(max_length=40, blank=True)     # blank=True : peut rester vide
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    # Comme pour les produits : on désactive au lieu d'effacer.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name