from django.contrib import admin
from apps.payments.models import PaymentTransaction, MidtransWebhookLog, ManualSettlement


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ["midtrans_order_id", "payment_type", "transaction_status", "gross_amount", "created_at"]
    list_filter = ["payment_type", "transaction_status"]
    search_fields = ["midtrans_order_id", "transaction_id"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(MidtransWebhookLog)
class MidtransWebhookLogAdmin(admin.ModelAdmin):
    list_display = ["midtrans_order_id", "transaction_status", "signature_valid", "processing_result", "received_at"]
    list_filter = ["processing_result", "signature_valid"]
    search_fields = ["midtrans_order_id"]
    readonly_fields = ["received_at"]


@admin.register(ManualSettlement)
class ManualSettlementAdmin(admin.ModelAdmin):
    list_display = ["order", "cashier_employee", "payment_method", "amount_received", "settled_at"]
    list_filter = ["payment_method"]
    readonly_fields = ["settled_at"]
