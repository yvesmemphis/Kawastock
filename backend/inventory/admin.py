from django.contrib import admin
from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "product",
        "movement_type",
        "quantity_delta",
        "quantity_after",
        "created_by",
    ]
    list_filter = ["movement_type", "shop"]
    search_fields = ["product__sku", "product__name"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
