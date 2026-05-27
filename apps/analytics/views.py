from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.orders.models import Order
from core.responses.standard import StandardResponse


def _require_dashboard_permission(request):
    tenant = getattr(request, "tenant", None)
    if not tenant or tenant.get("actor_type") != "EMPLOYEE":
        return False
    return "dashboard.view" in tenant.get("permissions", frozenset())


class DashboardSummaryView(APIView):
    """GET /api/v1/analytics/dashboard/summary/"""

    permission_classes = [IsAuthenticated]

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
