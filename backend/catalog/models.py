from django.db import models

# Create your models here.
import uuid
from django.db import models
from django.db.models import Q
from shops.models import Shop

class Category(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=120)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["shop", "name"], name="uniq_category_per_shop")]

    def __str__(self):
        return f"{self.name} ({self.shop})"


class Product(models.Model):
    class Unit(models.TextChoices):
        PIECE = "piece", "Pièce"
        BOX = "box", "Boîte"
        PACK = "pack", "Paquet"
        METER = "meter", "Mètre"
        ROLL = "roll", "Rouleau"
        LITER = "liter", "Litre"
        KG = "kg", "Kilogramme"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.PROTECT, related_name="products")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    sku = models.CharField(max_length=80)
    barcode = models.CharField(max_length=100, blank=True)
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=120, blank=True)
    unit = models.CharField(max_length=20, choices=Unit.choices, default=Unit.PIECE)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    min_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["shop", "sku"], name="uniq_sku_per_shop"),
            models.CheckConstraint(check=Q(stock_quantity__gte=0), name="stock_non_negative"),
        ]
        indexes = [models.Index(fields=["shop", "name"]), models.Index(fields=["shop", "barcode"])]

    def __str__(self):
        return f"{self.name} ({self.sku})"
