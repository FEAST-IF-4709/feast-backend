from django.urls import path
from . import views

urlpatterns = [
    path("tables/resolve/", views.PublicTableResolveView.as_view(), name="public-table-resolve"),
    path("outlets/<uuid:outlet_id>/menu/", views.PublicOutletMenuView.as_view(), name="public-outlet-menu"),
]
