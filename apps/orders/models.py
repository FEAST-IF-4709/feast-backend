from django.db import models
import uuid
# Create your models here.

class Order(models.Model):
    # Pilihan Status Pesanan
    ORDER_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PREPARING', 'Preparing'),
        ('COMPLETED', 'Completed'),
        ('CANCELED', 'Canceled'),
    ]

    # Pilihan Tipe Pesanan
    ORDER_TYPE_CHOICES = [
        ('DINE_IN', 'Dine In'),
        ('TAKEAWAY', 'Takeaway'),
        ('DELIVERY', 'Delivery'),
    ]

    # Pilihan Pembayaran
    PAYMENT_STATUS_CHOICES = [
        ('UNPAID', 'Unpaid'),
        ('PAID', 'Paid'),
        ('REFUNDED', 'Refunded'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('CARD', 'Debit/Credit Card'),
        ('QRIS', 'QRIS / E-Wallet'),
    ]

    # Primary Key menggunakan UUID agar aman & susah ditebak (standar struk modern)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relasi ke Tenant dan User
    outlet = models.ForeignKey('tenants.Outlet', on_delete=models.RESTRICT, related_name='orders')
    cashier = models.ForeignKey('users.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='handled_orders')
    
    # Info Pelanggan
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='DINE_IN')
    
    # Finansial (Pakai DecimalField untuk uang, JANGAN pakai FloatField agar tidak ada error pembulatan)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Status
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='PENDING')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='UNPAID')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.id} - {self.outlet.name} ({self.status})"


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    
    # Relasi ke Katalog Produk (Menggunakan Lazy Reference bentuk string)
    product = models.ForeignKey('catalog.Product', on_delete=models.RESTRICT, related_name='order_history')
    
    quantity = models.PositiveIntegerField(default=1)
    
    # Harga saat pesanan dibuat (PENTING! Harga menu bisa berubah di masa depan, harga di struk lama tidak boleh ikut berubah)
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Catatan khusus (misal: "Gula sedikit", "Jangan pakai bawang")
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (Order: {self.order.id})"
    
    @property
    def subtotal(self):
        return self.quantity * self.price_at_time