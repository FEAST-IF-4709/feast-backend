from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, BrandProductViewSet, OutletProductViewSet, PromotionViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("brand-products", BrandProductViewSet, basename="brand-product")
router.register("outlet-products", OutletProductViewSet, basename="outlet-product")
router.register("promotions", PromotionViewSet, basename="promotion")

urlpatterns = router.urls
