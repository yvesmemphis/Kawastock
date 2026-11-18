from django.contrib import admin

from .models import Purchase, PurchaseItem


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ["reference", "shop", "supplier", "status", "total_amount", "created_at"]
    list_filter = ["status", "shop"]
    inlines = [PurchaseItemInline]
