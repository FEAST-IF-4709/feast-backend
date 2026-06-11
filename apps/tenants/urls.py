from rest_framework.routers import SimpleRouter
from .views import BrandProfileViewSet, BrandAdminViewSet

router = SimpleRouter()
router.register("brands", BrandProfileViewSet, basename="brand")

admin_router = SimpleRouter()
admin_router.register("admin/brands", BrandAdminViewSet, basename="admin-brand")

urlpatterns = router.urls + admin_router.urls
