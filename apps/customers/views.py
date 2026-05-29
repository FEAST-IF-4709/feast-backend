from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.customers.models import Customer
from apps.customers.serializers import CustomerPublicSerializer
from core.responses.standard import StandardResponse
from core.schema import COMMON_ERROR_RESPONSES


class CustomerSearchView(APIView):
    """GET /api/v1/customers/search/?phone=<phone> — Cashier lookup by exact phone number."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Customers"],
        summary="Search customer by phone",
        description="Exact-match lookup of a customer by phone number. Used by cashiers to link a customer to a POS order. Requires `customer.view` permission.",
        parameters=[OpenApiParameter("phone", str, required=True, description="Customer phone number (exact match)")],
        responses={200: CustomerPublicSerializer, **COMMON_ERROR_RESPONSES},
    )
    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant or tenant.get("actor_type") != "EMPLOYEE":
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Only employees can search customers.",
                status=403, request=request,
            )
        if "customer.view" not in tenant.get("permissions", frozenset()):
            return StandardResponse(
                success=False, code="PERMISSION_DENIED",
                message="Missing permission: customer.view",
                status=403, request=request,
            )

        phone = request.query_params.get("phone", "").strip()
        if not phone:
            return StandardResponse(
                success=False, code="VALIDATION_ERROR",
                message="Query param 'phone' wajib diisi.",
                status=400, request=request,
            )

        customer = Customer.objects.filter(phone=phone, is_active=True).first()
        if not customer:
            return StandardResponse(
                success=False, code="NOT_FOUND",
                message="Customer tidak ditemukan.",
                status=404, request=request,
            )

        return StandardResponse(
            data=CustomerPublicSerializer(customer).data,
            request=request,
        )
