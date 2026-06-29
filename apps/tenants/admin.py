from django.contrib import admin
from apps.tenants.models import Brand, Outlet


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "subscription_status", "is_active", "tax_rate", "created_at"]
    search_fields = ["name", "slug", "owner_email"]
    list_filter = ["subscription_status", "is_active"]
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = [
        (None, {"fields": ["name", "slug", "owner_email", "subscription_status", "is_active"]}),
        ("Tax & Fees", {"fields": ["tax_rate"]}),
        ("Profile", {"fields": ["description", "phone", "cuisine_type", "logo_url", "banner_url", "location_address", "operating_hours"]}),
        ("Operations", {"fields": ["is_accepting_orders", "is_auto_accept", "is_busy_mode"]}),
        ("Location", {"fields": ["latitude", "longitude"]}),
    ]


@admin.register(Outlet)
class OutletAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "is_active", "latitude", "longitude"]
    list_filter = ["brand", "is_active"]
    search_fields = ["name", "brand__name"]
