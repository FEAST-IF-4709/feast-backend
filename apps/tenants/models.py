import uuid
from django.db import models
from django.contrib.gis.db import models as gis_models


class Brand(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    logo_url = models.URLField(max_length=500, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Outlet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='outlets')
    
    name = models.CharField(max_length=255)
    address = models.TextField()
    
    # Field khusus PostGIS untuk menyimpan titik koordinat (Longitude, Latitude)
    # SRID 4326 adalah standar format GPS dunia (WGS 84)
    location = gis_models.PointField(srid=4326, null=True, blank=True) 
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.brand.name}"