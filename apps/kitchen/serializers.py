from rest_framework import serializers

from apps.orders.models import Order, OrderItem
from core.utils.state_machine import FULFILLMENT_TRANSITIONS


class KitchenOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["id", "product_name", "category_name", "product_snapshot",
                  "quantity", "unit_price", "line_total", "item_notes"]

    def get_product_name(self, obj):
        if obj.product_snapshot:
            return obj.product_snapshot.get("name")
        if obj.outlet_product:
            return obj.outlet_product.brand_product.name
        return None

    def get_category_name(self, obj):
        if obj.outlet_product:
            return obj.outlet_product.brand_product.category.name
        return None


class KitchenOrderSerializer(serializers.ModelSerializer):
    items = KitchenOrderItemSerializer(many=True, read_only=True)
    table_label = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "order_source", "payment_status", "fulfillment_status",
            "table_label", "customer_name", "walk_in_name", "grand_total",
            "placed_at", "notes", "items",
        ]

    def get_table_label(self, obj):
        return obj.table.label if obj.table else None

    def get_customer_name(self, obj):
        return obj.customer.full_name if obj.customer else None


class KitchenStatusUpdateSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=Order.FulfillmentStatus.choices)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_to_status(self, value):
        order = self.context.get("order")
        if order is None:
            return value
        allowed = FULFILLMENT_TRANSITIONS.get(order.fulfillment_status, [])
        if value not in allowed:
            raise serializers.ValidationError(
                f"Cannot transition from {order.fulfillment_status} to {value}. "
                f"Allowed: {allowed}"
            )
        return value
