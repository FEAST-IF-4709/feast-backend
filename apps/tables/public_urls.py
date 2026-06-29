from django.urls import path
from . import views
from apps.tenants.views import PublicBrandListView, PublicOutletListView
from apps.catalog.views import PublicFeaturedBannersView, PublicHotDealsView

urlpatterns = [
    path("brands/", PublicBrandListView.as_view(), name="public-brand-list"),
    path("outlets/", PublicOutletListView.as_view(), name="public-outlet-list"),
    path("tables/resolve/", views.PublicTableResolveView.as_view(), name="public-table-resolve"),
    path("outlets/<uuid:outlet_id>/menu/", views.PublicOutletMenuView.as_view(), name="public-outlet-menu"),
    path("featured-banners/", PublicFeaturedBannersView.as_view(), name="public-featured-banners"),
    path("hot-deals/", PublicHotDealsView.as_view(), name="public-hot-deals"),
]
