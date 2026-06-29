from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, BrandProductViewSet, FeaturedBannerView, OutletProductViewSet, PromotionViewSet, BrandPushNotificationView

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("brand-products", BrandProductViewSet, basename="brand-product")
router.register("outlet-products", OutletProductViewSet, basename="outlet-product")
router.register("promotions", PromotionViewSet, basename="promotion")

urlpatterns = router.urls + [
    path("featured-banner/", FeaturedBannerView.as_view(), name="featured-banner"),
    path("push-notification/", BrandPushNotificationView.as_view(), name="brand-push-notification"),
]
