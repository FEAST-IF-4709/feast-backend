from rest_framework.routers import SimpleRouter
from .views import BrandProfileViewSet

router = SimpleRouter()
router.register("brands", BrandProfileViewSet, basename="brand")
urlpatterns = router.urls
