from django.urls import path

from apps.orders import views

urlpatterns = [
    path("orders/", views.CustomerOrderListView.as_view(), name="me-orders"),
]
