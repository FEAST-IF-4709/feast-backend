from rest_framework import status as http_status
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.responses.standard import StandardResponse
from core.schema import COMMON_ERROR_RESPONSES
from core.viewsets.tenant_scoped import TenantScopedViewSet

from .models import Employee
from .serializers import EmployeeSerializer, EmployeeCreateSerializer, EmployeeUpdateSerializer


@extend_schema_view(
    list=extend_schema(tags=["Employees"], summary="List employees"),
    retrieve=extend_schema(tags=["Employees"], summary="Get employee", responses={200: EmployeeSerializer, **COMMON_ERROR_RESPONSES}),
    create=extend_schema(tags=["Employees"], summary="Create employee", request=EmployeeCreateSerializer, responses={201: EmployeeSerializer, **COMMON_ERROR_RESPONSES}),
    update=extend_schema(tags=["Employees"], summary="Update employee", request=EmployeeUpdateSerializer, responses={200: EmployeeSerializer, **COMMON_ERROR_RESPONSES}),
    partial_update=extend_schema(tags=["Employees"], summary="Partial update employee", request=EmployeeUpdateSerializer, responses={200: EmployeeSerializer, **COMMON_ERROR_RESPONSES}),
    destroy=extend_schema(tags=["Employees"], summary="Delete employee", responses={204: None, **COMMON_ERROR_RESPONSES}),
)
class EmployeeViewSet(TenantScopedViewSet):
    serializer_class = EmployeeSerializer
    tenant_field = "brand"
    outlet_field = None

    required_permissions = {
        "list": "staff.view",
        "retrieve": "staff.view",
        "create": "staff.create",
        "update": "staff.update",
        "partial_update": "staff.update",
        "destroy": "staff.delete",
    }

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            return Employee.objects.none()
        return (
            Employee.objects.filter(brand_id=tenant["brand_id"])
            .select_related("role", "outlet")
            .order_by("full_name")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return EmployeeCreateSerializer
        if self.action in ("update", "partial_update"):
            return EmployeeUpdateSerializer
        return EmployeeSerializer

    def create(self, request, *args, **kwargs):
        serializer = EmployeeCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        employee = serializer.save(brand_id=request.tenant["brand_id"])
        return StandardResponse(
            data=EmployeeSerializer(employee).data,
            message="Employee created.",
            request=request,
            status=http_status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = EmployeeUpdateSerializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        return StandardResponse(
            data=EmployeeSerializer(employee).data,
            message="Employee updated.",
            request=request,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance == request.user:
            raise PermissionDenied("You cannot delete your own account.")
        instance.delete()
        return StandardResponse(message="Employee deleted.", request=request, status=http_status.HTTP_204_NO_CONTENT)
