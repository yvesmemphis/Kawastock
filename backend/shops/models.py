from django.db import models

# Create your models here.
import uuid
from django.conf import settings
from django.db import models

class Shop(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True, blank=True)
    currency = models.CharField(max_length=3, default="XOF")
    timezone = models.CharField(max_length=64, default="Africa/Abidjan")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class ShopMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Propriétaire"
        MANAGER = "manager", "Gestionnaire"
        STOCK_MANAGER = "stock_manager", "Gestionnaire de stock"
        SELLER = "seller", "Vendeur"
        VIEWER = "viewer", "Lecture seule"

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["shop", "user"], name="uniq_membership")]

    def __str__(self):
        return f"{self.user} — {self.shop} ({self.get_role_display()})"