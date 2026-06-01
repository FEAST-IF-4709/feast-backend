from rest_framework import status as http_status
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.db.models.deletion import ProtectedError

from core.responses.standard import StandardResponse
from core.schema import COMMON_ERROR_RESPONSES
from core.viewsets.tenant_scoped import TenantScopedViewSet

from .models import Category, BrandProduct, OutletProduct, Promotion
from .serializers import (
    CategorySerializer,
    CategoryCreateSerializer,
    BrandProductSerializer,
    BrandProductCreateSerializer,
    OutletProductSerializer,
    OutletProductCreateSerializer,
    PromotionSerializer,
    PromotionCreateSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=["Catalog"], summary="List categories"),
    retrieve=extend_schema(tags=["Catalog"], summary="Get category", responses={200: CategorySerializer, **COMMON_ERROR_RESPONSES}),
    create=extend_schema(tags=["Catalog"], summary="Create category", request=CategoryCreateSerializer, responses={201: CategorySerializer, **COMMON_ERROR_RESPONSES}),
    update=extend_schema(tags=["Catalog"], summary="Update category", request=CategoryCreateSerializer, responses={200: CategorySerializer, **COMMON_ERROR_RESPONSES}),
    partial_update=extend_schema(tags=["Catalog"], summary="Partial update category", request=CategoryCreateSerializer, responses={200: CategorySerializer, **COMMON_ERROR_RESPONSES}),
    destroy=extend_schema(tags=["Catalog"], summary="Delete category", responses={204: None, **COMMON_ERROR_RESPONSES}),
)
class CategoryViewSet(TenantScopedViewSet):
    serializer_class = CategorySerializer
    tenant_field = "brand"
    outlet_field = None

    required_permissions = {
        "list": "categories.view",
        "retrieve": "categories.view",
        "create": "categories.create",
        "update": "categories.update",
        "partial_update": "categories.update",
        "destroy": "categories.delete",
    }

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Category.objects.none()
        return Category.objects.filter(brand_id=tenant["brand_id"]).order_by("sequence", "name")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CategoryCreateSerializer
        return CategorySerializer

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return StandardResponse(data=CategorySerializer(qs, many=True).data, request=request)

    def create(self, request, *args, **kwargs):
        serializer = CategoryCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        category = serializer.save(brand_id=request.tenant["brand_id"])
        return StandardResponse(
            data=CategorySerializer(category).data,
            message="Category created.",
            request=request,
            status=http_status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = CategoryCreateSerializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return StandardResponse(
            data=CategorySerializer(category).data,
            message="Category updated.",
            request=request,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return StandardResponse(
                success=False,
                code="CONFLICT",
                message="Kategori tidak bisa dihapus karena masih memiliki produk. Hapus semua produk dalam kategori ini terlebih dahulu.",
                status=http_status.HTTP_409_CONFLICT,
                request=request,
            )
        return StandardResponse(message="Category deleted.", request=request, status=http_status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(tags=["Catalog"], summary="List brand products"),
    retrieve=extend_schema(tags=["Catalog"], summary="Get brand product", responses={200: BrandProductSerializer, **COMMON_ERROR_RESPONSES}),
    create=extend_schema(tags=["Catalog"], summary="Create brand product", request=BrandProductCreateSerializer, responses={201: BrandProductSerializer, **COMMON_ERROR_RESPONSES}),
    update=extend_schema(tags=["Catalog"], summary="Update brand product", request=BrandProductCreateSerializer, responses={200: BrandProductSerializer, **COMMON_ERROR_RESPONSES}),
    partial_update=extend_schema(tags=["Catalog"], summary="Partial update brand product", request=BrandProductCreateSerializer, responses={200: BrandProductSerializer, **COMMON_ERROR_RESPONSES}),
    destroy=extend_schema(tags=["Catalog"], summary="Delete brand product", responses={204: None, **COMMON_ERROR_RESPONSES}),
)
class BrandProductViewSet(TenantScopedViewSet):
    serializer_class = BrandProductSerializer
    tenant_field = "brand"
    outlet_field = None

    required_permissions = {
        "list": "products.view",
        "retrieve": "products.view",
        "create": "products.create",
        "update": "products.update",
        "partial_update": "products.update",
        "destroy": "products.delete",
    }

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return BrandProduct.objects.none()
        return (
            BrandProduct.objects.filter(brand_id=tenant["brand_id"])
            .select_related("category")
            .order_by("category__name", "name")
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return BrandProductCreateSerializer
        return BrandProductSerializer

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return StandardResponse(
            data=BrandProductSerializer(qs, many=True, context={"request": request}).data,
            request=request,
        )

    def create(self, request, *args, **kwargs):
        serializer = BrandProductCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        product = serializer.save(brand_id=request.tenant["brand_id"])
        return StandardResponse(
            data=BrandProductSerializer(product, context={"request": request}).data,
            message="Product created.",
            request=request,
            status=http_status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = BrandProductCreateSerializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return StandardResponse(
            data=BrandProductSerializer(product, context={"request": request}).data,
            message="Product updated.",
            request=request,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return StandardResponse(
                success=False,
                code="CONFLICT",
                message="Produk tidak bisa dihapus karena masih aktif di outlet. Hapus produk dari semua outlet terlebih dahulu.",
                status=http_status.HTTP_409_CONFLICT,
                request=request,
            )
        return StandardResponse(message="Product deleted.", request=request, status=http_status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(tags=["Catalog"], summary="List outlet products"),
    retrieve=extend_schema(tags=["Catalog"], summary="Get outlet product", responses={200: OutletProductSerializer, **COMMON_ERROR_RESPONSES}),
    create=extend_schema(tags=["Catalog"], summary="Create outlet product", request=OutletProductCreateSerializer, responses={201: OutletProductSerializer, **COMMON_ERROR_RESPONSES}),
    update=extend_schema(tags=["Catalog"], summary="Update outlet product", request=OutletProductCreateSerializer, responses={200: OutletProductSerializer, **COMMON_ERROR_RESPONSES}),
    partial_update=extend_schema(tags=["Catalog"], summary="Partial update outlet product", request=OutletProductCreateSerializer, responses={200: OutletProductSerializer, **COMMON_ERROR_RESPONSES}),
    destroy=extend_schema(tags=["Catalog"], summary="Delete outlet product", responses={204: None, **COMMON_ERROR_RESPONSES}),
)
class OutletProductViewSet(TenantScopedViewSet):
    serializer_class = OutletProductSerializer
    tenant_field = "brand"
    outlet_field = None

    required_permissions = {
        "list": "outlet_products.view",
        "retrieve": "outlet_products.view",
        "create": "outlet_products.create",
        "update": "outlet_products.update",
        "partial_update": "outlet_products.update",
        "destroy": "outlet_products.delete",
    }

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return OutletProduct.objects.none()
        qs = OutletProduct.objects.filter(
            outlet__brand_id=tenant["brand_id"],
        ).select_related("brand_product__category", "outlet")
        if tenant["outlet_ids"]:
            qs = qs.filter(outlet_id__in=tenant["outlet_ids"])
        if outlet_id := self.request.query_params.get("outlet_id"):
            qs = qs.filter(outlet_id=outlet_id)
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return OutletProductCreateSerializer
        return OutletProductSerializer

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return StandardResponse(
            data=OutletProductSerializer(qs, many=True, context={"request": request}).data,
            request=request,
        )

    def create(self, request, *args, **kwargs):
        serializer = OutletProductCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        op = serializer.save()
        op.refresh_from_db()
        return StandardResponse(
            data=OutletProductSerializer(op, context={"request": request}).data,
            message="Outlet product created.",
            request=request,
            status=http_status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = OutletProductCreateSerializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        op = serializer.save()
        return StandardResponse(
            data=OutletProductSerializer(op, context={"request": request}).data,
            message="Outlet product updated.",
            request=request,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return StandardResponse(message="Outlet product deleted.", request=request, status=http_status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(tags=["Catalog"], summary="List promotions"),
    retrieve=extend_schema(tags=["Catalog"], summary="Get promotion", responses={200: PromotionSerializer, **COMMON_ERROR_RESPONSES}),
    create=extend_schema(tags=["Catalog"], summary="Create promotion", request=PromotionCreateSerializer, responses={201: PromotionSerializer, **COMMON_ERROR_RESPONSES}),
    update=extend_schema(tags=["Catalog"], summary="Update promotion", request=PromotionCreateSerializer, responses={200: PromotionSerializer, **COMMON_ERROR_RESPONSES}),
    partial_update=extend_schema(tags=["Catalog"], summary="Partial update promotion", request=PromotionCreateSerializer, responses={200: PromotionSerializer, **COMMON_ERROR_RESPONSES}),
    destroy=extend_schema(tags=["Catalog"], summary="Delete promotion", responses={204: None, **COMMON_ERROR_RESPONSES}),
)
class PromotionViewSet(TenantScopedViewSet):
    serializer_class = PromotionSerializer
    tenant_field = "brand"
    outlet_field = None

    required_permissions = {
        "list": "promotions.view",
        "retrieve": "promotions.view",
        "create": "promotions.create",
        "update": "promotions.update",
        "partial_update": "promotions.update",
        "destroy": "promotions.delete",
    }

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Promotion.objects.none()
        return (
            Promotion.objects.filter(brand_product__brand_id=tenant["brand_id"])
            .select_related("brand_product")
            .order_by("-starts_at")
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return PromotionCreateSerializer
        return PromotionSerializer

    def create(self, request, *args, **kwargs):
        serializer = PromotionCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        promo = serializer.save()
        promo.refresh_from_db()
        return StandardResponse(
            data=PromotionSerializer(promo, context={"request": request}).data,
            message="Promotion created.",
            request=request,
            status=http_status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = PromotionCreateSerializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        promo = serializer.save()
        return StandardResponse(
            data=PromotionSerializer(promo, context={"request": request}).data,
            message="Promotion updated.",
            request=request,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return StandardResponse(message="Promotion deleted.", request=request, status=http_status.HTTP_204_NO_CONTENT)
