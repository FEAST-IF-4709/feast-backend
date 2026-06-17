from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("admin/vouchers", views.VoucherTemplateViewSet, basename="admin-voucher")

urlpatterns = [
    path("search/", views.CustomerSearchView.as_view(), name="customer-search"),
    path("me/", views.CustomerMeView.as_view(), name="customer-me"),
    path("me/loyalty/", views.CustomerLoyaltyView.as_view(), name="customer-loyalty"),
    path("me/vouchers/", views.CustomerVoucherListView.as_view(), name="customer-vouchers"),
    path("me/vouchers/redeem/", views.RedeemVoucherView.as_view(), name="customer-voucher-redeem"),
    path("voucher-catalog/", views.VoucherCatalogView.as_view(), name="voucher-catalog"),
    *router.urls,
]
