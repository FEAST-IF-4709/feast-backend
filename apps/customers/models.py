import uuid
from django.db import models
from django.contrib.auth.hashers import make_password, check_password as django_check_password


class Customer(models.Model):
    """
    Global customer model. Standalone auth — not linked to Django BaseUser.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(null=True, blank=True)
    password = models.CharField(max_length=128)
    full_name = models.CharField(max_length=150)
    profile_photo = models.ImageField(upload_to="customers/photos/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # DRF duck-type interface
    is_authenticated = True
    is_anonymous = False

    class Meta:
        indexes = [
            models.Index(fields=["phone"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=models.Q(email__isnull=False),
                name="unique_customer_email_when_set",
            ),
        ]

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return django_check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


class LoyaltyAccount(models.Model):
    """One-to-one loyalty wallet per customer. Points balance is always kept in sync via LoyaltyTransaction."""

    class TierLevel(models.TextChoices):
        BRONZE = "BRONZE", "Bronze"
        SILVER = "SILVER", "Silver"
        GOLD = "GOLD", "Gold"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name="loyalty_account")
    points_balance = models.IntegerField(default=0)
    tier = models.CharField(max_length=10, choices=TierLevel.choices, default=TierLevel.BRONZE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(points_balance__gte=0), name="loyalty_balance_non_negative"),
        ]

    def __str__(self):
        return f"LoyaltyAccount({self.customer.phone}, {self.points_balance} pts, {self.tier})"


class LoyaltyTransaction(models.Model):
    """Immutable ledger entry for every point change on a LoyaltyAccount."""

    class TxnType(models.TextChoices):
        EARN = "EARN", "Earn"
        REDEEM = "REDEEM", "Redeem"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"
        EXPIRE = "EXPIRE", "Expire"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE, related_name="transactions")
    txn_type = models.CharField(max_length=20, choices=TxnType.choices)
    points = models.IntegerField()
    balance_after = models.IntegerField()
    reference_type = models.CharField(max_length=50, blank=True, default="")
    reference_id = models.UUIDField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["account", "-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.txn_type} {self.points:+d} pts → {self.balance_after} (acct {self.account_id})"


class VoucherTemplate(models.Model):
    """Brand-managed voucher that customers can redeem with loyalty points."""

    class DiscountType(models.TextChoices):
        PERCENT = "PERCENT", "Percent Off"
        FIXED = "FIXED", "Fixed Amount Off"
        FREE_ITEM = "FREE_ITEM", "Free Item"

    class ApplicableScope(models.TextChoices):
        ALL = "ALL", "All Products"
        CATEGORY = "CATEGORY", "Specific Categories"
        PRODUCT = "PRODUCT", "Specific Products"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey("tenants.Brand", on_delete=models.CASCADE, related_name="voucher_templates")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="vouchers/images/", null=True, blank=True)
    points_cost = models.PositiveIntegerField()
    discount_type = models.CharField(max_length=15, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    applicable_scope = models.CharField(max_length=10, choices=ApplicableScope.choices, default=ApplicableScope.ALL)
    applicable_categories = models.ManyToManyField(
        "catalog.Category", blank=True, related_name="voucher_templates"
    )
    applicable_products = models.ManyToManyField(
        "catalog.BrandProduct", blank=True, related_name="voucher_templates"
    )
    is_active = models.BooleanField(default=True)
    valid_days = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["brand", "is_active"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.points_cost} pts)"


class CustomerVoucher(models.Model):
    """A VoucherTemplate instance owned by a customer after redeeming loyalty points."""

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        USED = "USED", "Used"
        EXPIRED = "EXPIRED", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="vouchers")
    voucher_template = models.ForeignKey(VoucherTemplate, on_delete=models.PROTECT, related_name="issued_vouchers")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.AVAILABLE)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    used_on_order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="used_vouchers"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["customer", "-created_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"Voucher({self.voucher_template.title}, {self.customer.phone}, {self.status})"
