from django.contrib import admin

from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "shop", "phone", "email", "is_active", "created_at")
    list_filter = ("shop", "is_active")
    search_fields = ("name", "phone", "email", "shop__name")
    autocomplete_fields = ("shop",)
    readonly_fields = ("created_at",)
    list_select_related = ("shop",)
