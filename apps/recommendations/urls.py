from django.urls import path
from .views import PopularProductsView, OnPromotionView

urlpatterns = [
    path("brands/<uuid:brand_id>/popular/", PopularProductsView.as_view(), name="recommendations-popular"),
    path("brands/<uuid:brand_id>/promotions/", OnPromotionView.as_view(), name="recommendations-promotions"),
]
