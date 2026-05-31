import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.orders.utils import generate_order_number


class Order(models.Model):
    class OrderSource(models.TextChoices):
        QR_TABLE = "QR_TABLE", "QR Table"
        CASHIER_POS = "CASHIER_POS", "Cashier POS"
        MOBILE_APP_DELIVERY = "MOBILE_APP_DELIVERY", "Mobile App Delivery"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        EDC = "EDC", "EDC"
        QRIS_MIDTRANS = "QRIS_MIDTRANS", "QRIS Midtrans"
        BANK_TRANSFER_MIDTRANS = "BANK_TRANSFER_MIDTRANS", "Bank Transfer Midtrans"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SETTLED = "SETTLED", "Settled"
        EXPIRED = "EXPIRED", "Expired"
        DENIED = "DENIED", "Denied"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    class FulfillmentStatus(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        READY = "READY", "Ready"
        SERVED = "SERVED", "Served"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, blank=True)
    brand = models.ForeignKey("tenants.Brand", on_delete=models.PROTECT, related_name="orders")
    outlet = models.ForeignKey("tenants.Outlet", on_delete=models.PROTECT, related_name="orders")
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
        null=True,
        blank=True,
    )
    table = models.ForeignKey(
        "tables.Table",
        on_delete=models.PROTECT,
        related_name="orders",
        null=True,
        blank=True,
    )
    cashier_employee = models.ForeignKey(
        "staff.Employee",
        on_delete=models.PROTECT,
        related_name="cashier_orders",
        null=True,
        blank=True,
    )
    order_source = models.CharField(max_length=25, choices=OrderSource.choices)
    walk_in_name = models.CharField(max_length=100, null=True, blank=True)
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, blank=True)
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    fulfillment_status = models.CharField(
        max_length=20,
        choices=FulfillmentStatus.choices,
        default=FulfillmentStatus.RECEIVED,
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    placed_at = models.DateTimeField(db_index=True, default=timezone.now)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["brand", "outlet", "fulfillment_status", "-placed_at"]),
            models.Index(fields=["brand", "payment_status", "-placed_at"]),
            models.Index(fields=["customer", "-placed_at"]),
            models.Index(fields=["table", "fulfillment_status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(grand_total__gte=0),
                name="order_grand_total_non_negative",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = generate_order_number()
        super().save(*args, **kwargs)

    def clean(self):
        src = self.order_source
        if src == self.OrderSource.QR_TABLE:
            if not self.customer_id:
                raise ValidationError({"customer": "QR_TABLE orders require a logged-in customer."})
            if not self.table_id:
                raise ValidationError({"table": "QR_TABLE orders require a table."})
            if self.cashier_employee_id:
                raise ValidationError({"cashier_employee": "QR_TABLE orders must not have a cashier."})
        elif src == self.OrderSource.CASHIER_POS:
            if not self.cashier_employee_id:
                raise ValidationError({"cashier_employee": "CASHIER_POS orders require a cashier."})
        elif src == self.OrderSource.MOBILE_APP_DELIVERY:
            if not self.customer_id:
                raise ValidationError({"customer": "MOBILE_APP_DELIVERY orders require a customer."})
            if self.table_id:
                raise ValidationError({"table": "MOBILE_APP_DELIVERY orders must not have a table."})
            if self.cashier_employee_id:
                raise ValidationError(
                    {"cashier_employee": "MOBILE_APP_DELIVERY orders must not have a cashier."}
                )

    def apply_fulfillment_transition(
        self,
        to_status: str,
        changed_by=None,
        notes: str | None = None,
        actor_permissions: frozenset[str] = frozenset(),
    ) -> None:
        """Transition fulfillment status, validate path + permission, write history row.

        Delegates transition validation (including permission check) to
        core.utils.state_machine.validate_transition.
        """
        from core.utils.state_machine import validate_transition

        validate_transition(self.fulfillment_status, to_status, actor_permissions)
        from_status = self.fulfillment_status
        self.fulfillment_status = to_status
        self.save(update_fields=["fulfillment_status"])
        OrderStatusHistory.objects.create(
            order=self,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            notes=notes,
        )

    def __str__(self):
        return f"{self.order_number} — {self.outlet.name}"


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    outlet_product = models.ForeignKey(
        "catalog.OutletProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    product_snapshot = models.JSONField()
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    item_notes = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["outlet_product", "order"]),
        ]

    def save(self, *args, **kwargs):
        self.line_total = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        name = self.product_snapshot.get("name", "?") if self.product_snapshot else "?"
        return f"{self.quantity}x {name} (Order {self.order.order_number})"


class OrderStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        "staff.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="status_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["order", "changed_at"]),
        ]

    def __str__(self):
        return f"{self.order.order_number}: {self.from_status} → {self.to_status}"


class DailyOrderCounter(models.Model):
    """Global daily sequence table for PG-native atomic order number generation.

    One row per calendar day; last_sequence is incremented atomically via
    ON CONFLICT DO UPDATE in apps.orders.utils.generate_order_number.
    """

    date = models.DateField(unique=True)
    last_sequence = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "orders_dailyordercounter"
