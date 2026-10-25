from django.contrib import admin

from .models import Shop, ShopMembership


class ShopMembershipInline(admin.TabularInline):
    model = ShopMembership
    extra = 0
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "currency", "timezone", "is_active", "created_at")
    list_filter = ("is_active", "currency", "timezone")
    search_fields = ("name", "slug")
    readonly_fields = ("created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ShopMembershipInline,)


@admin.register(ShopMembership)
class ShopMembershipAdmin(admin.ModelAdmin):
    list_display = ("shop", "user", "role", "is_active", "created_at")
    list_filter = ("role", "is_active", "shop")
    search_fields = ("shop__name", "user__username", "user__email")
    autocomplete_fields = ("shop", "user")
    readonly_fields = ("created_at",)
    list_select_related = ("shop", "user")
