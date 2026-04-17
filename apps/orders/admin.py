from django.contrib import admin
from .models import Order, OrderItem

# Register your models here.

# Membuat tampilan daftar item pesanan menyatu di dalam halaman Order
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1 # Jumlah baris kosong default yang disiapkan
    readonly_fields = ('subtotal',) # Subtotal hanya untuk dibaca karena ini adalah @property (hasil kalkulasi otomatis)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # Data yang muncul di tabel depan
    list_display = ('id', 'outlet', 'customer_name', 'total_amount', 'status', 'payment_status', 'created_at')
    
    # Filter di panel kanan
    list_filter = ('status', 'payment_status', 'order_type', 'outlet')
    
    # Fitur pencarian berdasarkan ID Struk atau Nama Pelanggan
    search_fields = ('id', 'customer_name')
    
    # Kolom yang tidak boleh diedit manual
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    # Menyisipkan daftar makanan ke dalam halaman Order
    inlines = [OrderItemInline]

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price_at_time', 'subtotal')
    search_fields = ('order__id', 'product__name')
    readonly_fields = ('subtotal',)