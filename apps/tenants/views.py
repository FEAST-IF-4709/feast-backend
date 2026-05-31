from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from core.permissions.has_permission import HasPermission
from core.responses.standard import StandardResponse
from .models import Brand
from .serializers import BrandSerializer


class BrandProfileViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, HasPermission]
    required_permissions = {"me": None}  # PATCH permission checked inline

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        brand = get_object_or_404(Brand, id=request.tenant["brand_id"])

        if request.method == "PATCH":
            if "brand.update" not in request.tenant.get("permissions", frozenset()):
                return StandardResponse(
                    success=False,
                    code="FORBIDDEN",
                    message="You do not have brand.update permission.",
                    status=403,
                    request=request,
                )
            serializer = BrandSerializer(brand, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return StandardResponse(
                data=serializer.data,
                message="Brand profile updated.",
                request=request,
            )

        return StandardResponse(data=BrandSerializer(brand).data, request=request)
