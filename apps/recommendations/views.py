from datetime import timedelta

from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.catalog.models import BrandProduct, OutletProduct
from apps.orders.models import OrderItem
from apps.tables.serializers import PublicMenuProductSerializer
from core.responses.standard import StandardResponse
from core.schema import COMMON_ERROR_RESPONSES

_CACHE_TTL = 300  # 5 minutes


class PopularProductsView(APIView):
    """GET /api/v1/recommendations/brands/{brand_id}/popular/"""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Recommendations"],
        summary="Popular products (terlaris)",
        description=(
            "Returns the top-selling products for a brand ranked by quantity sold "
            "in the given time window. When `outlet_id` is supplied the response "
            "matches the `MenuItem` shape used by the mobile menu (id = outlet_product_id, "
            "price, image_url, stock_available, active_promotion) plus `total_qty_sold`. "
            "Results are cached for 5 minutes."
        ),
        parameters=[
            OpenApiParameter("limit", int, description="Max results (default 10, max 50)"),
            OpenApiParameter("window_days", int, description="Lookback window in days (default 30, max 365)"),
            OpenApiParameter("outlet_id", str, description="Filter by outlet UUID for full MenuItem shape. Default: all outlets"),
        ],
    )
    def get(self, request, brand_id):
        try:
            limit = min(int(request.query_params.get("limit", 10)), 50)
        except (TypeError, ValueError):
            limit = 10

        try:
            window_days = min(int(request.query_params.get("window_days", 30)), 365)
        except (TypeError, ValueError):
            window_days = 30

        outlet_id = request.query_params.get("outlet_id", "all")
        cache_key = f"recommendations:popular:{brand_id}:{outlet_id}:{window_days}"

        def _rank_query():
            cutoff = timezone.now() - timedelta(days=window_days)
            qs = OrderItem.objects.filter(
                order__brand_id=brand_id,
                order__placed_at__gte=cutoff,
                order__payment_status="SETTLED",
                outlet_product__isnull=False,
            )
            if outlet_id != "all":
                qs = qs.filter(order__outlet_id=outlet_id)
            return list(
                qs.values("outlet_product__brand_product_id")
                .annotate(total_qty=Sum("quantity"))
                .order_by("-total_qty")[:limit]
            )

        ranked = cache.get_or_set(cache_key, _rank_query, _CACHE_TTL)
        if not ranked:
            return StandardResponse(data=[], request=request)

        bp_id_to_qty = {
            str(r["outlet_product__brand_product_id"]): r["total_qty"]
            for r in ranked
        }
        bp_ids = [str(r["outlet_product__brand_product_id"]) for r in ranked]

        if outlet_id != "all":
            outlet_products = {
                str(op.brand_product_id): op
                for op in OutletProduct.objects.filter(
                    outlet_id=outlet_id,
                    brand_product_id__in=bp_ids,
                    brand_product__is_active=True,
                ).select_related("brand_product__category")
            }
            data = []
            for bp_id in bp_ids:
                op = outlet_products.get(bp_id)
                if op is None:
                    continue
                item = dict(
                    PublicMenuProductSerializer(op, context={"request": request}).data
                )
                item["total_qty_sold"] = bp_id_to_qty[bp_id]
                data.append(item)
        else:
            brand_products = {
                str(bp.id): bp
                for bp in BrandProduct.objects.filter(
                    id__in=bp_ids, brand_id=brand_id, is_active=True
                ).select_related("category")
            }
            data = []
            for bp_id in bp_ids:
                bp = brand_products.get(bp_id)
                if bp is None:
                    continue
                image_url = None
                if bp.image:
                    image_url = request.build_absolute_uri(bp.image.url)
                data.append({
                    "brand_product_id": bp_id,
                    "name": bp.name,
                    "description": bp.description,
                    "category": bp.category.name,
                    "base_price": str(bp.base_price),
                    "image_url": image_url,
                    "total_qty_sold": bp_id_to_qty[bp_id],
                })

        return StandardResponse(data=data, request=request)


class OnPromotionView(APIView):
    """GET /api/v1/recommendations/brands/{brand_id}/promotions/"""

    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Recommendations"],
        summary="Products on promotion (hot deals)",
        description=(
            "Returns products with an active promotion. When `outlet_id` is supplied "
            "the response matches the `MenuItem` shape (id = outlet_product_id, price, "
            "image_url, stock_available, active_promotion). Results are cached for 5 minutes."
        ),
        parameters=[
            OpenApiParameter("limit", int, description="Max results (default 10, max 50)"),
            OpenApiParameter("outlet_id", str, description="Filter by outlet UUID for full MenuItem shape. Default: all outlets"),
        ],
    )
    def get(self, request, brand_id):
        try:
            limit = min(int(request.query_params.get("limit", 10)), 50)
        except (TypeError, ValueError):
            limit = 10

        outlet_id = request.query_params.get("outlet_id", "all")
        cache_key = f"recommendations:promotions:{brand_id}:{outlet_id}"

        def _promo_query():
            now = timezone.now()
            return list(
                BrandProduct.objects.filter(
                    brand_id=brand_id,
                    is_active=True,
                    promotions__is_active=True,
                    promotions__starts_at__lte=now,
                    promotions__ends_at__gte=now,
                )
                .distinct()
                .values_list("id", flat=True)[:limit]
            )

        bp_ids = [str(pk) for pk in cache.get_or_set(cache_key, _promo_query, _CACHE_TTL)]
        if not bp_ids:
            return StandardResponse(data=[], request=request)

        if outlet_id != "all":
            outlet_products = list(
                OutletProduct.objects.filter(
                    outlet_id=outlet_id,
                    brand_product_id__in=bp_ids,
                    brand_product__is_active=True,
                ).select_related("brand_product__category")
            )
            data = PublicMenuProductSerializer(
                outlet_products, many=True, context={"request": request}
            ).data
        else:
            now = timezone.now()
            brand_products = BrandProduct.objects.filter(
                id__in=bp_ids, is_active=True
            ).select_related("category").prefetch_related("promotions")
            result = []
            for bp in brand_products:
                image_url = request.build_absolute_uri(bp.image.url) if bp.image else None
                active_promos = [
                    p for p in bp.promotions.all()
                    if p.is_active and p.starts_at <= now <= p.ends_at
                ]
                result.append({
                    "brand_product_id": str(bp.id),
                    "name": bp.name,
                    "base_price": str(bp.base_price),
                    "category": bp.category.name,
                    "image_url": image_url,
                    "promotions": [
                        {
                            "discount_type": p.discount_type,
                            "discount_value": str(p.discount_value),
                            "ends_at": p.ends_at.isoformat(),
                        }
                        for p in active_promos
                    ],
                })
            data = result

        return StandardResponse(data=data, request=request)
