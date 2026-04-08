from django.contrib import admin
from .models import Brand, Outlet

# Register your models here.
@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at') # Kolom yang muncul di tabel
    search_fields = ('name',)             # Fitur pencarian

@admin.register(Outlet)
class OutletAdmin(admin.ModelAdmin):
    # Hapus 'city', ganti dengan field yang ada di modelmu (contoh: 'address')
    # Kalau ragu, pakai ('name', 'brand', 'is_active') saja dulu
    list_display = ('name', 'brand', 'is_active') 
    list_filter = ('brand', 'is_active')