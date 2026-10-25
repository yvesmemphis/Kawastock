from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "parent")
    list_filter = ("shop",)
    search_fields = ("name", "shop__name", "parent__name")
    autocomplete_fields = ("shop", "parent")
    list_select_related = ("shop", "parent")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "shop",
        "category",
        "unit",
        "selling_price",
        "stock_quantity",
        "is_active",
    )
    list_filter = ("shop", "category", "unit", "is_active")
    search_fields = ("name", "sku", "barcode", "brand", "shop__name")
    autocomplete_fields = ("shop", "category")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("shop", "category")
