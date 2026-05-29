from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.orders.models import Order
from core.responses.standard import StandardResponse
from core.schema import COMMON_ERROR_RESPONSES


def _require_dashboard_permission(request):
    tenant = getattr(request, "tenant", None)
    if not tenant or tenant.get("actor_type") != "EMPLOYEE":
        return False
    return "dashboard.view" in tenant.get("permissions", frozenset())


class DashboardSummaryView(APIView):
    """GET /api/v1/analytics/dashboard/summary/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Analytics"],
        summary="Dashboard revenue summary",
        description="Aggregated revenue and order counts for the brand. Requires `dashboard.view` permission.",
        parameters=[
            OpenApiParameter("date_from", str, description="Start date filter (YYYY-MM-DD)"),
            OpenApiParameter("date_to", str, description="End date filter (YYYY-MM-DD)"),
        ],
        responses={
            200: inline_serializer("DashboardSummary", fields={
                "total_revenue": drf_serializers.CharField(),
                "total_orders": drf_serializers.IntegerField(),
                "settled_orders": drf_serializers.IntegerField(),
                "pending_orders": drf_serializers.IntegerField(),
                "date_from": drf_serializers.CharField(allow_null=True),
                "date_to": drf_serializers.CharField(allow_null=True),
            }),
            **COMMON_ERROR_RESPONSES,
        },
    )
    def get(self, request):
        if not _require_dashboard_permission(request):
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Missing permission: dashboard.view",
                status=403, request=request,
            )

        tenant = request.tenant
        brand_id = tenant["brand_id"]

        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        settled_qs = Order.objects.filter(brand_id=brand_id, payment_status=Order.PaymentStatus.SETTLED)
        all_qs = Order.objects.filter(brand_id=brand_id)

        if date_from:
            settled_qs = settled_qs.filter(placed_at__date__gte=date_from)
            all_qs = all_qs.filter(placed_at__date__gte=date_from)
        if date_to:
            settled_qs = settled_qs.filter(placed_at__date__lte=date_to)
            all_qs = all_qs.filter(placed_at__date__lte=date_to)

        settled_agg = settled_qs.aggregate(
            total_revenue=Sum("grand_total"),
            settled_orders=Count("id"),
        )

        pending_count = all_qs.filter(payment_status=Order.PaymentStatus.PENDING).count()

        data = {
            "total_revenue": str(settled_agg["total_revenue"] or 0),
            "total_orders": (settled_agg["settled_orders"] or 0) + pending_count,
            "settled_orders": settled_agg["settled_orders"] or 0,
            "pending_orders": pending_count,
            "date_from": date_from,
            "date_to": date_to,
        }

        return StandardResponse(data=data, request=request)


class DailyRevenueChartView(APIView):
    """GET /api/v1/analytics/dashboard/daily-chart/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Analytics"],
        summary="Daily revenue chart data",
        description="Returns daily revenue and order count for the last N days (max 90). Requires `dashboard.view` permission.",
        parameters=[
            OpenApiParameter("days", int, description="Number of days to look back. Default: 30, max: 90"),
        ],
        responses={
            200: inline_serializer("DailyRevenuePoint", fields={
                "date": drf_serializers.DateField(),
                "revenue": drf_serializers.CharField(),
                "order_count": drf_serializers.IntegerField(),
            }, many=True),
            **COMMON_ERROR_RESPONSES,
        },
    )
    def get(self, request):
        if not _require_dashboard_permission(request):
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Missing permission: dashboard.view",
                status=403, request=request,
            )

        tenant = request.tenant
        brand_id = tenant["brand_id"]

        try:
            days = min(int(request.query_params.get("days", 30)), 90)
        except (TypeError, ValueError):
            days = 30

        cutoff = timezone.now() - timedelta(days=days)

        qs = (
            Order.objects.filter(
                brand_id=brand_id,
                payment_status=Order.PaymentStatus.SETTLED,
                placed_at__gte=cutoff,
            )
            .annotate(date=TruncDate("placed_at"))
            .values("date")
            .annotate(revenue=Sum("grand_total"), order_count=Count("id"))
            .order_by("date")
        )

        data = [
            {
                "date": row["date"].isoformat(),
                "revenue": str(row["revenue"]),
                "order_count": row["order_count"],
            }
            for row in qs
        ]

        return StandardResponse(data=data, request=request)
