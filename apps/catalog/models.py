from django.db import models
import uuid

# Create your models here.
class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Kategori ini milik Brand yang mana?
    brand = models.ForeignKey('tenants.Brand', on_delete=models.CASCADE, related_name='categories')
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories" # Supaya di Admin tidak tertulis "Categorys"
        # Memastikan tidak ada nama kategori yang sama di dalam satu Brand
        unique_together = ('brand', 'name') 

    def __str__(self):
        return f"{self.name} ({self.brand.name})"


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relasi
    brand = models.ForeignKey('tenants.Brand', on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    
    # Detail Produk
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    
    # Harga wajib DecimalField
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Foto Makanan (Bisa kosong dulu sementara)
    image = models.ImageField(upload_to='products/images/', blank=True, null=True)
    
    # Status ketersediaan (Habis / Tersedia)
    is_available = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.brand.name}"