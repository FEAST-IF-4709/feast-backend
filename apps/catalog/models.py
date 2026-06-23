import uuid
from django.db import models
from django.core.validators import MinValueValidator
from core.models import TimestampedModel


class Category(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey("tenants.Brand", on_delete=models.PROTECT, related_name="categories")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    sequence = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["brand", "name"], name="unique_category_name_per_brand"),
        ]

    def __str__(self):
        return f"{self.name} ({self.brand.name})"


class BrandProduct(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey("tenants.Brand", on_delete=models.PROTECT, related_name="brand_products")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="brand_products")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    image = models.ImageField(upload_to="products/images/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["brand", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} — {self.brand.name}"


class OutletProduct(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand_product = models.ForeignKey(BrandProduct, on_delete=models.PROTECT, related_name="outlet_products")
    outlet = models.ForeignKey("tenants.Outlet", on_delete=models.PROTECT, related_name="outlet_products")
    outlet_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    stock_available = models.BooleanField(default=True)
    stock_quantity = models.IntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["brand_product", "outlet"], name="unique_outlet_product"
            ),
        ]
        indexes = [
            models.Index(fields=["outlet", "stock_available"]),
        ]

    @property
    def effective_price(self):
        return self.outlet_price if self.outlet_price is not None else self.brand_product.base_price

    def __str__(self):
        return f"{self.brand_product.name} @ {self.outlet.name}"


class Promotion(models.Model):
    class DiscountType(models.TextChoices):
        PERCENT = "PERCENT", "Percent"
        FIXED = "FIXED", "Fixed Amount"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand_product = models.ForeignKey(BrandProduct, on_delete=models.CASCADE, related_name="promotions")
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["brand_product", "is_active", "starts_at", "ends_at"]),
        ]

    is_hot_deal = models.BooleanField(default=False, db_index=True)

    def __str__(self):
        return f"{self.discount_type} {self.discount_value} on {self.brand_product.name}"


class BrandFeaturedBanner(models.Model):
    """One special-offer banner per brand, managed from the dashboard."""

    brand = models.OneToOneField(
        "tenants.Brand",
        on_delete=models.CASCADE,
        related_name="featured_banner",
    )
    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=200, blank=True, default="")
    image_url = models.URLField(max_length=500)
    target_outlet = models.ForeignKey(
        "tenants.Outlet",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="featured_banners",
    )
    is_active = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"FeaturedBanner — {self.brand.name} ({'active' if self.is_active else 'inactive'})"
