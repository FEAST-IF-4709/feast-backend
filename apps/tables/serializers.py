from rest_framework import serializers

from apps.catalog.models import OutletProduct, Promotion
from django.utils import timezone
from .models import Table


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ["id", "outlet_id", "label", "capacity", "qr_token", "is_active",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "outlet_id", "qr_token", "created_at", "updated_at"]


class TableCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ["label", "capacity", "is_active"]


class PublicOutletSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    brand_name = serializers.SerializerMethodField()

    def get_brand_name(self, obj):
        return obj.brand.name


class PublicTableResolveSerializer(serializers.Serializer):
    outlet = serializers.SerializerMethodField()
    table = serializers.SerializerMethodField()
    menu_endpoint = serializers.SerializerMethodField()
    requires_login = serializers.SerializerMethodField()

    def get_outlet(self, obj):
        outlet = obj.outlet
        return {
            "id": str(outlet.id),
            "name": outlet.name,
            "brand_id": str(outlet.brand_id),
            "brand_name": outlet.brand.name,
        }

    def get_table(self, obj):
        return {"id": str(obj.id), "label": obj.label}

    def get_menu_endpoint(self, obj):
        return f"/api/v1/public/outlets/{obj.outlet_id}/menu/"

    def get_requires_login(self, obj):
        return True


class PublicMenuProductSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="brand_product.name")
    description = serializers.CharField(source="brand_product.description")
    category_id = serializers.UUIDField(source="brand_product.category_id")
    category_name = serializers.CharField(source="brand_product.category.name")
    image_url = serializers.SerializerMethodField()
    price = serializers.DecimalField(source="effective_price", max_digits=12, decimal_places=2)
    active_promotion = serializers.SerializerMethodField()

    class Meta:
        model = OutletProduct
        fields = [
            "id", "name", "description", "category_id", "category_name",
            "image_url", "price", "stock_available", "active_promotion",
        ]

    def get_image_url(self, obj):
        img = obj.brand_product.image
        if not img:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(img.url)
        return img.url

    def get_active_promotion(self, obj):
        now = timezone.now()
        promo = (
            Promotion.objects.filter(
                brand_product=obj.brand_product,
                is_active=True,
                starts_at__lte=now,
                ends_at__gte=now,
            )
            .order_by("-discount_value")
            .first()
        )
        if not promo:
            return None
        return {
            "discount_type": promo.discount_type,
            "discount_value": str(promo.discount_value),
        }
