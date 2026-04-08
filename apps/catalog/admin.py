from django.contrib import admin
from .models import Category, Product

# Register your models here.

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'created_at')
    list_filter = ('brand',)
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'category', 'price', 'is_available')
    list_filter = ('brand', 'category', 'is_available')
    search_fields = ('name',)
    list_editable = ('price', 'is_available') # Memudahkan admin mengganti harga/status langsung dari tabel