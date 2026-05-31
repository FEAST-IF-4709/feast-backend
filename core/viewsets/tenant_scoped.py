from rest_framework.viewsets import ModelViewSet
from rest_framework.exceptions import PermissionDenied


class TenantScopedViewSet(ModelViewSet):
    """
    Base ViewSet that auto-filters querysets by the request's tenant context.

    Subclasses MUST declare:
      tenant_field: str         e.g. "brand"
      outlet_field: str | None  e.g. "outlet", or None if brand-scoped only
    """

    tenant_field = "brand"
    outlet_field = None

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            raise PermissionDenied("Tenant context missing.")

        qs = qs.filter(**{f"{self.tenant_field}_id": tenant["brand_id"]})

        if self.outlet_field and tenant["outlet_ids"]:
            qs = qs.filter(**{f"{self.outlet_field}_id__in": tenant["outlet_ids"]})

        return qs

    def perform_create(self, serializer):
        tenant = self.request.tenant
        extra = {f"{self.tenant_field}_id": tenant["brand_id"]}
        if self.outlet_field and len(tenant["outlet_ids"]) == 1:
            extra[f"{self.outlet_field}_id"] = tenant["outlet_ids"][0]
        serializer.save(**extra)
