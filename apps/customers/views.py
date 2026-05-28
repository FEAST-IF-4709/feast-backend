from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.customers.models import Customer
from apps.customers.serializers import CustomerPublicSerializer
from core.responses.standard import StandardResponse


class CustomerSearchView(APIView):
    """GET /api/v1/customers/search/?phone=<phone> — Cashier lookup by exact phone number."""

    permission_classes = [IsAuthenticated]

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
