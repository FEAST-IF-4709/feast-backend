from rest_framework import serializers
from .models import Category, BrandProduct, OutletProduct, Promotion


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "brand_id", "name", "description", "sequence", "created_at", "updated_at"]
        read_only_fields = ["id", "brand_id", "created_at", "updated_at"]


class CategoryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["name", "description", "sequence"]


class BrandProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = BrandProduct
        fields = [
            "id", "brand_id", "category_id", "category_name",
            "name", "description", "base_price", "image_url",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "brand_id", "created_at", "updated_at"]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class BrandProductCreateSerializer(serializers.ModelSerializer):
    category_id = serializers.UUIDField()

    class Meta:
        model = BrandProduct
        fields = ["category_id", "name", "description", "base_price", "image", "is_active"]

    def validate_category_id(self, value):
        request = self.context.get("request")
        if request and hasattr(request, "tenant"):
            from apps.catalog.models import Category as Cat
            if not Cat.objects.filter(id=value, brand_id=request.tenant["brand_id"]).exists():
                raise serializers.ValidationError("Category does not belong to your brand.")
        return value


class OutletProductSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="brand_product.name", read_only=True)
    outlet_name = serializers.CharField(source="outlet.name", read_only=True)
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OutletProduct
        fields = [
            "id", "brand_product_id", "product_name", "outlet_id", "outlet_name",
            "outlet_price", "effective_price", "stock_available", "stock_quantity",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OutletProductCreateSerializer(serializers.ModelSerializer):
    brand_product_id = serializers.UUIDField()
    outlet_id = serializers.UUIDField()

    class Meta:
        model = OutletProduct
        fields = ["brand_product_id", "outlet_id", "outlet_price", "stock_available", "stock_quantity"]

    def validate_brand_product_id(self, value):
        request = self.context.get("request")
        if request and hasattr(request, "tenant"):
            from apps.catalog.models import BrandProduct as BP
            if not BP.objects.filter(id=value, brand_id=request.tenant["brand_id"]).exists():
                raise serializers.ValidationError("Product does not belong to your brand.")
        return value

    def validate_outlet_id(self, value):
        request = self.context.get("request")
        if not (request and hasattr(request, "tenant")):
            return value
        tenant = request.tenant
        outlet_ids = tenant.get("outlet_ids", [])
        if outlet_ids:
            if str(value) not in [str(x) for x in outlet_ids]:
                raise serializers.ValidationError("Outlet is not accessible for your account.")
        else:
            from apps.tenants.models import Outlet
            if not Outlet.objects.filter(id=value, brand_id=tenant["brand_id"]).exists():
                raise serializers.ValidationError("Outlet does not belong to your brand.")
        return value


class PromotionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="brand_product.name", read_only=True)

    class Meta:
        model = Promotion
        fields = [
            "id", "brand_product_id", "product_name",
            "discount_type", "discount_value", "starts_at", "ends_at", "is_active",
        ]
        read_only_fields = ["id"]


class PromotionCreateSerializer(serializers.ModelSerializer):
    brand_product_id = serializers.UUIDField()

    class Meta:
        model = Promotion
        fields = ["brand_product_id", "discount_type", "discount_value", "starts_at", "ends_at", "is_active"]

    def validate_brand_product_id(self, value):
        request = self.context.get("request")
        if request and hasattr(request, "tenant"):
            from apps.catalog.models import BrandProduct as BP
            if not BP.objects.filter(id=value, brand_id=request.tenant["brand_id"]).exists():
                raise serializers.ValidationError("Product does not belong to your brand.")
        return value

    def validate(self, attrs):
        if attrs.get("starts_at") and attrs.get("ends_at"):
            if attrs["ends_at"] <= attrs["starts_at"]:
                raise serializers.ValidationError({"ends_at": "ends_at must be after starts_at."})
        return attrs
