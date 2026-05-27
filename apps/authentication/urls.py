from django.urls import path
from apps.authentication.views import (
    StaffLoginView,
    CustomerLoginView,
    CustomerRegisterView,
    FeastTokenRefreshView,
    LogoutView,
)

urlpatterns = [
    path("staff/login/", StaffLoginView.as_view(), name="staff-login"),
    path("customer/login/", CustomerLoginView.as_view(), name="customer-login"),
    path("customer/register/", CustomerRegisterView.as_view(), name="customer-register"),
    path("token/refresh/", FeastTokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
