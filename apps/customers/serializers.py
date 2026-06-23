from rest_framework import serializers

from apps.customers.models import Customer, LoyaltyAccount, LoyaltyTransaction, VoucherTemplate, CustomerVoucher


class CustomerPublicSerializer(serializers.ModelSerializer):
    """Read-only serializer for staff-side customer lookup (cashier link flow)."""

    class Meta:
        model = Customer
        fields = ["id", "phone", "full_name"]


class CustomerProfileSerializer(serializers.ModelSerializer):
    """Customer self-serve profile — read + partial update."""

    class Meta:
        model = Customer
        fields = ["id", "phone", "email", "full_name", "profile_photo", "created_at"]
        read_only_fields = ["id", "phone", "created_at"]


class CustomerUpdateSerializer(serializers.ModelSerializer):
    """Validated payload for PATCH /me/."""

    class Meta:
        model = Customer
        fields = ["full_name", "email", "profile_photo"]
        extra_kwargs = {
            "full_name": {"required": False},
            "email": {"required": False, "allow_null": True},
            "profile_photo": {"required": False, "allow_null": True},
        }


class LoyaltyTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyTransaction
        fields = [
            "id",
            "txn_type",
            "points",
            "balance_after",
            "reference_type",
            "reference_id",
            "note",
            "created_at",
        ]


class LoyaltyAccountSerializer(serializers.ModelSerializer):
    transactions = LoyaltyTransactionSerializer(many=True, read_only=True)
    tier_points_in_window = serializers.SerializerMethodField()
    active_voucher_count = serializers.SerializerMethodField()

    class Meta:
        model = LoyaltyAccount
        fields = ["id", "points_balance", "tier", "tier_points_in_window", "active_voucher_count", "created_at", "updated_at", "transactions"]

    def get_tier_points_in_window(self, obj):
        from apps.customers.loyalty import get_tier_points_in_window
        return get_tier_points_in_window(obj)

    def get_active_voucher_count(self, obj):
        return obj.customer.vouchers.filter(status="AVAILABLE").count()


class VoucherTemplateSerializer(serializers.ModelSerializer):
    """Read serializer for VoucherTemplate — used in catalog and customer-facing views."""

    image_url = serializers.SerializerMethodField()
    applicable_categories = serializers.SerializerMethodField()
    applicable_products = serializers.SerializerMethodField()
    brand_name = serializers.CharField(source="brand.name", read_only=True)

    class Meta:
        model = VoucherTemplate
        fields = [
            "id", "brand_id", "brand_name", "title", "description", "image_url",
            "points_cost", "discount_type", "discount_value",
            "applicable_scope", "applicable_categories", "applicable_products",
            "is_active", "valid_days", "created_at", "updated_at",
        ]

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.image.url)
        return obj.image.url

    def get_applicable_categories(self, obj):
        return list(obj.applicable_categories.values("id", "name"))

    def get_applicable_products(self, obj):
        return list(obj.applicable_products.values("id", "name"))


class VoucherTemplateWriteSerializer(serializers.ModelSerializer):
    """Write serializer for brand admin CRUD of VoucherTemplate."""

    class Meta:
        model = VoucherTemplate
        fields = [
            "title", "description", "image",
            "points_cost", "discount_type", "discount_value",
            "applicable_scope", "applicable_categories", "applicable_products",
            "is_active", "valid_days",
        ]
        extra_kwargs = {
            "description": {"required": False, "default": ""},
            "image": {"required": False, "allow_null": True},
            "discount_value": {"required": False, "allow_null": True},
            "applicable_categories": {"required": False},
            "applicable_products": {"required": False},
            "is_active": {"required": False},
            "valid_days": {"required": False},
        }


class CustomerVoucherSerializer(serializers.ModelSerializer):
    """Read serializer for a customer-owned voucher."""

    voucher_template = VoucherTemplateSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = CustomerVoucher
        fields = [
            "id", "voucher_template", "status", "status_display",
            "expires_at", "used_at", "used_on_order_id", "created_at",
        ]


class RedeemVoucherSerializer(serializers.Serializer):
    """Validated payload for POST /me/vouchers/redeem/."""

    voucher_template_id = serializers.UUIDField()

    def validate_voucher_template_id(self, value):
        try:
            template = VoucherTemplate.objects.get(pk=value, is_active=True)
        except VoucherTemplate.DoesNotExist as exc:
            raise serializers.ValidationError("Voucher template tidak ditemukan atau sudah tidak aktif.") from exc
        self._template = template
        return value
