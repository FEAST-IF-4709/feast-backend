from django.contrib import admin
from apps.tenants.models import Brand, Outlet


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "subscription_status", "is_active", "created_at"]
    search_fields = ["name", "slug", "owner_email"]
    list_filter = ["subscription_status", "is_active"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Outlet)
class OutletAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "is_active", "latitude", "longitude"]
    list_filter = ["brand", "is_active"]
    search_fields = ["name", "brand__name"]
