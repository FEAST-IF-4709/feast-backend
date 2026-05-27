from django.utils import timezone
from rest_framework import serializers

from apps.catalog.models import OutletProduct, Promotion
from .models import Order, OrderItem, OrderStatusHistory


class OrderItemCreateSerializer(serializers.Serializer):
    outlet_product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    item_notes = serializers.CharField(max_length=255, required=False, allow_blank=True)


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["id", "outlet_product_id", "product_name", "product_snapshot",
                  "quantity", "unit_price", "line_total", "item_notes"]

    def get_product_name(self, obj):
        if obj.product_snapshot:
            return obj.product_snapshot.get("name")
        return None


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusHistory
        fields = ["from_status", "to_status", "changed_at", "notes"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "brand_id", "outlet_id", "customer_id", "table_id",
            "cashier_employee_id", "order_source", "walk_in_name", "payment_method",
            "payment_status", "fulfillment_status", "subtotal", "discount_total",
            "grand_total", "placed_at", "notes", "items",
        ]


class OrderQRTableCreateSerializer(serializers.Serializer):
    table_id = serializers.UUIDField()
    items = OrderItemCreateSerializer(many=True, min_length=1)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_table_id(self, value):
        from apps.tables.models import Table
        try:
            table = Table.objects.select_related("outlet__brand").get(pk=value, is_active=True)
        except Table.DoesNotExist:
            raise serializers.ValidationError("Table not found or inactive.")
        if not table.outlet.is_active:
            raise serializers.ValidationError("Outlet is inactive.")
        self._table = table
        return value

    def validate(self, attrs):
        table = getattr(self, "_table", None)
        if table is None:
            return attrs

        outlet = table.outlet
        items_data = attrs["items"]
        product_ids = [item["outlet_product_id"] for item in items_data]

        products = OutletProduct.objects.select_related("brand_product").filter(
            pk__in=product_ids, outlet=outlet
        )
        product_map = {str(p.pk): p for p in products}

        for item in items_data:
            pid = str(item["outlet_product_id"])
            if pid not in product_map:
                raise serializers.ValidationError(
                    {"items": f"Product {pid} not found in this outlet."}
                )
            if not product_map[pid].stock_available:
                raise serializers.ValidationError(
                    {"items": f"Product {product_map[pid].brand_product.name} is out of stock."}
                )

        attrs["_table"] = table
        attrs["_outlet"] = outlet
        attrs["_product_map"] = product_map
        return attrs


class OrderCashierPOSCreateSerializer(serializers.Serializer):
    outlet_id = serializers.UUIDField(required=False)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    walk_in_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    table_id = serializers.UUIDField(required=False, allow_null=True)
    items = OrderItemCreateSerializer(many=True, min_length=1)
    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context["request"]
        tenant = request.tenant

        outlet_id = attrs.get("outlet_id")
        tenant_outlet_ids = [str(o) for o in tenant["outlet_ids"]]

        if outlet_id:
            if str(outlet_id) not in tenant_outlet_ids:
                raise serializers.ValidationError(
                    {"outlet_id": "Outlet not accessible in tenant context."}
                )
        else:
            if len(tenant["outlet_ids"]) != 1:
                raise serializers.ValidationError(
                    {"outlet_id": "outlet_id wajib diisi karena karyawan memiliki akses ke banyak outlet."}
                )
            outlet_id = tenant["outlet_ids"][0]
            attrs["outlet_id"] = outlet_id

        from apps.tenants.models import Outlet
        try:
            outlet = Outlet.objects.get(pk=outlet_id, is_active=True)
        except Outlet.DoesNotExist:
            raise serializers.ValidationError({"outlet_id": "Outlet not found or inactive."})

        customer_id = attrs.get("customer_id")
        if customer_id:
            from apps.customers.models import Customer
            try:
                Customer.objects.get(pk=customer_id, is_active=True)
            except Customer.DoesNotExist:
                raise serializers.ValidationError({"customer_id": "Customer not found."})

        table_id = attrs.get("table_id")
        if table_id:
            from apps.tables.models import Table
            try:
                Table.objects.get(pk=table_id, outlet=outlet, is_active=True)
            except Table.DoesNotExist:
                raise serializers.ValidationError({"table_id": "Table not found in this outlet."})

        items_data = attrs["items"]
        product_ids = [item["outlet_product_id"] for item in items_data]
        products = OutletProduct.objects.select_related("brand_product").filter(
            pk__in=product_ids, outlet=outlet
        )
        product_map = {str(p.pk): p for p in products}

        for item in items_data:
            pid = str(item["outlet_product_id"])
            if pid not in product_map:
                raise serializers.ValidationError(
                    {"items": f"Product {pid} not found in this outlet."}
                )
            if not product_map[pid].stock_available:
                raise serializers.ValidationError(
                    {"items": f"Product {product_map[pid].brand_product.name} is out of stock."}
                )

        attrs["_outlet"] = outlet
        attrs["_product_map"] = product_map
        return attrs


def compute_order_totals(items_data, product_map):
    """Compute subtotal, discount_total, grand_total and build OrderItem list."""
    now = timezone.now()
    order_items_payload = []
    subtotal = 0
    discount_total = 0

    for item_data in items_data:
        pid = str(item_data["outlet_product_id"])
        outlet_product = product_map[pid]
        base_unit_price = outlet_product.effective_price

        active_promotion = (
            Promotion.objects.filter(
                brand_product=outlet_product.brand_product,
                is_active=True,
                starts_at__lte=now,
                ends_at__gte=now,
            )
            .order_by("-discount_value")
            .first()
        )

        discount_per_unit = 0
        if active_promotion:
            if active_promotion.discount_type == Promotion.DiscountType.PERCENT:
                discount_per_unit = base_unit_price * active_promotion.discount_value / 100
            else:
                discount_per_unit = active_promotion.discount_value

        unit_price = max(base_unit_price - discount_per_unit, 0)
        quantity = item_data["quantity"]
        line_total = unit_price * quantity

        subtotal += base_unit_price * quantity
        discount_total += discount_per_unit * quantity

        snapshot = {
            "name": outlet_product.brand_product.name,
            "base_price": str(base_unit_price),
            "discount_applied": str(discount_per_unit) if discount_per_unit else None,
            "image_url": (
                outlet_product.brand_product.image.url
                if outlet_product.brand_product.image
                else None
            ),
        }

        order_items_payload.append({
            "outlet_product": outlet_product,
            "product_snapshot": snapshot,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
            "item_notes": item_data.get("item_notes", ""),
        })

    grand_total = subtotal - discount_total
    return order_items_payload, subtotal, discount_total, grand_total
