from django.contrib import admin
from apps.catalog.models import Category, BrandProduct, OutletProduct, Promotion


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "created_at"]
    list_filter = ["brand"]
    search_fields = ["name", "brand__name"]


@admin.register(BrandProduct)
class BrandProductAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "category", "base_price", "is_active"]
    list_filter = ["brand", "category", "is_active"]
    search_fields = ["name", "brand__name"]


@admin.register(OutletProduct)
class OutletProductAdmin(admin.ModelAdmin):
    list_display = ["brand_product", "outlet", "outlet_price", "stock_available", "stock_quantity"]
    list_filter = ["outlet", "stock_available"]
    search_fields = ["brand_product__name", "outlet__name"]


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ["brand_product", "discount_type", "discount_value", "starts_at", "ends_at", "is_active"]
    list_filter = ["discount_type", "is_active"]
    search_fields = ["brand_product__name"]
