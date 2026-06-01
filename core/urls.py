from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from core.views import HealthCheckView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth
    path("api/v1/auth/", include("apps.authentication.urls")),

    # Brand profile
    path("api/v1/", include("apps.tenants.urls")),

    # RBAC
    path("api/v1/rbac/", include("apps.rbac.urls")),

    # Orders
    path("api/v1/orders/", include("apps.orders.urls")),

    # Customer self-service (me/)
    path("api/v1/me/", include("apps.orders.me_urls")),

    # Customers (staff-side lookup)
    path("api/v1/customers/", include("apps.customers.urls")),

    # Payments
    path("api/v1/payments/", include("apps.payments.urls")),

    # Kitchen Display System
    path("api/v1/kitchen/", include("apps.kitchen.urls")),

    # Catalog management (categories, brand products, outlet products, promotions)
    path("api/v1/catalog/", include("apps.catalog.urls")),

    # Outlet management (CRUD)
    # Geolocation must come before outlet CRUD so /outlets/nearby/ resolves correctly
    path("api/v1/", include("apps.geolocation.urls")),
    path("api/v1/outlets/", include("apps.tenants.outlet_urls")),

    # Employee/Staff management (CRUD)
    path("api/v1/employees/", include("apps.staff.urls")),

    # Tables (outlet-scoped list/create + global retrieve/update/delete/rotate-qr)
    path("api/v1/outlets/<uuid:outlet_id>/tables/", include("apps.tables.outlet_urls")),
    path("api/v1/tables/", include("apps.tables.urls")),

    # Public endpoints (no auth required)
    path("api/v1/public/", include("apps.tables.public_urls")),

    # Recommendations
    path("api/v1/recommendations/", include("apps.recommendations.urls")),

    # Analytics Dashboard
    path("api/v1/analytics/", include("apps.analytics.urls")),

    # Health check
    path("api/v1/health/", HealthCheckView.as_view(), name="health"),

    # API Schema & Docs
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
