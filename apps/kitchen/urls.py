from django.urls import path
from . import views

urlpatterns = [
    path("outlets/", views.KitchenOutletListView.as_view(), name="kitchen-outlet-list"),
    path("orders/", views.KitchenOrderListView.as_view(), name="kitchen-order-list"),
    path("orders/<uuid:pk>/status/", views.KitchenOrderStatusUpdateView.as_view(), name="kitchen-order-status"),
    path("orders/<uuid:pk>/cancel/", views.KitchenOrderCancelView.as_view(), name="kitchen-order-cancel"),
]
