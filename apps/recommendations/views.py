from datetime import timedelta

from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.catalog.models import BrandProduct
from apps.orders.models import OrderItem
from core.responses.standard import StandardResponse

_CACHE_TTL = 300  # 5 minutes


class PopularProductsView(APIView):
    """GET /api/v1/recommendations/brands/{brand_id}/popular/"""

    permission_classes = [AllowAny]

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

        def _query():
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
                qs.values(
                    "outlet_product__brand_product_id",
                    "outlet_product__brand_product__name",
                )
                .annotate(total_qty=Sum("quantity"))
                .order_by("-total_qty")[:limit]
            )

        results = cache.get_or_set(cache_key, _query, _CACHE_TTL)

        data = [
            {
                "brand_product_id": str(row["outlet_product__brand_product_id"]),
                "name": row["outlet_product__brand_product__name"],
                "total_qty_sold": row["total_qty"],
            }
            for row in results
        ]

        return StandardResponse(data=data, request=request)


class OnPromotionView(APIView):
    """GET /api/v1/recommendations/brands/{brand_id}/promotions/"""

    permission_classes = [AllowAny]

    def get(self, request, brand_id):
        try:
            limit = min(int(request.query_params.get("limit", 10)), 50)
        except (TypeError, ValueError):
            limit = 10

        outlet_id = request.query_params.get("outlet_id", "all")

        cache_key = f"recommendations:promotions:{brand_id}:{outlet_id}"

        def _query():
            now = timezone.now()
            qs = (
                BrandProduct.objects.filter(
                    brand_id=brand_id,
                    is_active=True,
                    promotions__is_active=True,
                    promotions__starts_at__lte=now,
                    promotions__ends_at__gte=now,
                )
                .distinct()
                .select_related("category")
                .prefetch_related("promotions")[:limit]
            )
            return [
                {
                    "brand_product_id": str(p.id),
                    "name": p.name,
                    "base_price": str(p.base_price),
                    "category": p.category.name,
                    "promotions": [
                        {
                            "discount_type": promo.discount_type,
                            "discount_value": str(promo.discount_value),
                            "ends_at": promo.ends_at.isoformat(),
                        }
                        for promo in p.promotions.all()
                        if promo.is_active and promo.starts_at <= now <= promo.ends_at
                    ],
                }
                for p in qs
            ]

        results = cache.get_or_set(cache_key, _query, _CACHE_TTL)

        return StandardResponse(data=results, request=request)
