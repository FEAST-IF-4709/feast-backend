from django.urls import path
from . import views

urlpatterns = [
    path("qr-table/", views.OrderQRTableCreateView.as_view(), name="order-qr-table"),
    path("cashier-pos/", views.OrderCashierPOSCreateView.as_view(), name="order-cashier-pos"),
]
