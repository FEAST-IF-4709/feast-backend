from rest_framework import serializers

from apps.orders.models import Order
from .models import PaymentTransaction, ManualSettlement


class InitiateQRISSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()

    def validate_order_id(self, value):
        request = self.context["request"]
        tenant = getattr(request, "tenant", None)

        filters = {"pk": value, "payment_status__in": [Order.PaymentStatus.PENDING, Order.PaymentStatus.EXPIRED]}
        if tenant and tenant.get("actor_type") == "EMPLOYEE":
            filters["brand_id"] = tenant["brand_id"]
            # outlet_ids kosong → brand-level employee (owner), cukup scope by brand
            if tenant["outlet_ids"]:
                filters["outlet_id__in"] = tenant["outlet_ids"]

        try:
            order = Order.objects.select_related("outlet__brand").get(**filters)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found or not pending.")

        if order.payment_method not in (
            Order.PaymentMethod.QRIS_MIDTRANS,
            Order.PaymentMethod.BANK_TRANSFER_MIDTRANS,
        ):
            raise serializers.ValidationError(
                "This order does not use a Midtrans payment method."
            )

        self._order = order
        return value


class ManualSettleSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(choices=ManualSettlement.PaymentMethod.choices)
    amount_received = serializers.DecimalField(max_digits=12, decimal_places=2)
    change_given = serializers.DecimalField(max_digits=12, decimal_places=2)
    edc_reference = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)

    def validate_order_id(self, value):
        request = self.context["request"]
        tenant = request.tenant
        filters = {"pk": value, "brand_id": tenant["brand_id"]}
        if tenant["outlet_ids"]:
            filters["outlet_id__in"] = tenant["outlet_ids"]
        try:
            order = Order.objects.get(**filters)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found.")

        if order.order_source != Order.OrderSource.CASHIER_POS:
            raise serializers.ValidationError("Manual settlement only for CASHIER_POS orders.")
        if order.payment_method not in (
            Order.PaymentMethod.CASH,
            Order.PaymentMethod.EDC,
        ):
            raise serializers.ValidationError(
                "Manual settlement only for CASH or EDC payment methods."
            )
        if order.payment_status != Order.PaymentStatus.PENDING:
            raise serializers.ValidationError("Order is not pending payment.")

        self._order = order
        return value

    def validate(self, attrs):
        order = getattr(self, "_order", None)
        if order is None:
            return attrs

        pm = attrs["payment_method"]
        amount_received = attrs["amount_received"]
        change_given = attrs["change_given"]
        edc_reference = attrs.get("edc_reference")

        if pm == ManualSettlement.PaymentMethod.CASH:
            if amount_received < order.grand_total:
                raise serializers.ValidationError(
                    {"amount_received": "Amount received must be >= order grand_total."}
                )
            expected_change = amount_received - order.grand_total
            if change_given != expected_change:
                raise serializers.ValidationError(
                    {"change_given": f"Expected change_given = {expected_change}."}
                )
        elif pm == ManualSettlement.PaymentMethod.EDC:
            if not edc_reference:
                raise serializers.ValidationError(
                    {"edc_reference": "edc_reference is required for EDC payments."}
                )
            if amount_received != order.grand_total:
                raise serializers.ValidationError(
                    {"amount_received": "amount_received must equal grand_total for EDC."}
                )
            if change_given != 0:
                raise serializers.ValidationError(
                    {"change_given": "change_given must be 0 for EDC payments."}
                )

        attrs["_order"] = order
        return attrs


class PaymentStatusSerializer(serializers.ModelSerializer):
    expires_at = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ["id", "order_number", "payment_status", "fulfillment_status", "grand_total"]

    def get_expires_at(self, obj):
        try:
            return obj.payment_transaction.expires_at
        except Exception:
            return None


class ManualSettlementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManualSettlement
        fields = [
            "id", "order_id", "cashier_employee_id", "payment_method",
            "amount_received", "change_given", "edc_reference", "settled_at",
        ]
