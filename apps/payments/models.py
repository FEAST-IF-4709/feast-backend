import uuid
from django.db import models


class PaymentTransaction(models.Model):
    class PaymentType(models.TextChoices):
        QRIS = "qris", "QRIS"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"

    class TransactionStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SETTLEMENT = "settlement", "Settlement"
        EXPIRE = "expire", "Expire"
        DENY = "deny", "Deny"
        CANCEL = "cancel", "Cancel"
        REFUND = "refund", "Refund"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payment_transaction",
    )
    midtrans_order_id = models.CharField(max_length=100, unique=True, db_index=True)
    transaction_id = models.CharField(max_length=64, null=True, blank=True)
    payment_type = models.CharField(max_length=20, choices=PaymentType.choices)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    qr_string = models.TextField(null=True, blank=True)
    qr_image_url = models.URLField(null=True, blank=True)
    va_number = models.CharField(max_length=40, null=True, blank=True)
    va_bank = models.CharField(max_length=20, null=True, blank=True)
    expires_at = models.DateTimeField()
    transaction_status = models.CharField(max_length=20, choices=TransactionStatus.choices)
    fraud_status = models.CharField(max_length=20, null=True, blank=True)
    raw_request_payload = models.JSONField()
    raw_response_payload = models.JSONField()
    last_webhook_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.midtrans_order_id} ({self.transaction_status})"


class MidtransWebhookLog(models.Model):
    class ProcessingResult(models.TextChoices):
        APPLIED = "APPLIED", "Applied"
        IGNORED_OUT_OF_ORDER = "IGNORED_OUT_OF_ORDER", "Ignored Out Of Order"
        IGNORED_DUPLICATE = "IGNORED_DUPLICATE", "Ignored Duplicate"
        REJECTED_INVALID_SIG = "REJECTED_INVALID_SIG", "Rejected Invalid Signature"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    midtrans_order_id = models.CharField(max_length=100, db_index=True)
    transaction_status = models.CharField(max_length=20)
    signature_valid = models.BooleanField()
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
    processing_result = models.CharField(max_length=30, choices=ProcessingResult.choices)

    class Meta:
        indexes = [
            models.Index(fields=["midtrans_order_id"]),
            models.Index(fields=["-received_at"]),
        ]

    def __str__(self):
        return f"Webhook {self.midtrans_order_id} — {self.processing_result}"


class ManualSettlement(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        EDC = "EDC", "EDC"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="manual_settlement",
    )
    cashier_employee = models.ForeignKey(
        "staff.Employee",
        on_delete=models.PROTECT,
        related_name="manual_settlements",
    )
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    amount_received = models.DecimalField(max_digits=12, decimal_places=2)
    change_given = models.DecimalField(max_digits=12, decimal_places=2)
    edc_reference = models.CharField(max_length=50, null=True, blank=True)
    settled_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Manual {self.payment_method} — {self.order.order_number}"
