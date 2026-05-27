import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimestampedModel


class Brand(TimestampedModel):
    class SubscriptionStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        TRIAL = "TRIAL", "Trial"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True)
    owner_email = models.EmailField(unique=True)
    subscription_status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.TRIAL,
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Outlet(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="outlets")
    name = models.CharField(max_length=150)
    address = models.TextField()
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    opening_hours = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["brand", "name"], name="unique_outlet_name_per_brand"),
        ]
        indexes = [
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return f"{self.name} — {self.brand.name}"
