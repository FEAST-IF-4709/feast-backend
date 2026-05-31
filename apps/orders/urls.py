from django.urls import path
from . import views

urlpatterns = [
    path("", views.OrderListView.as_view(), name="order-list"),
    path("qr-table/", views.OrderQRTableCreateView.as_view(), name="order-qr-table"),
    path("cashier-pos/", views.OrderCashierPOSCreateView.as_view(), name="order-cashier-pos"),
    path("<uuid:pk>/", views.OrderDetailView.as_view(), name="order-detail"),
]
