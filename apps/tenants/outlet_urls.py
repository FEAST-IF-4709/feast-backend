from rest_framework.routers import DefaultRouter
from .views import OutletViewSet

router = DefaultRouter()
router.register("", OutletViewSet, basename="outlet")

urlpatterns = router.urls
