from django.urls import path
from . import views

urlpatterns = [
    path("initiate-qris/", views.InitiateQRISView.as_view(), name="payment-initiate-qris"),
    path("webhook/midtrans/", views.MidtransWebhookView.as_view(), name="payment-webhook-midtrans"),
    path("manual-settle/", views.ManualSettleView.as_view(), name="payment-manual-settle"),
    path("<uuid:order_id>/status/", views.PaymentStatusView.as_view(), name="payment-status"),
]
