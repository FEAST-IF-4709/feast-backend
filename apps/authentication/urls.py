from django.urls import path
from apps.authentication.views import (
    StaffLoginView,
    CustomerLoginView,
    CustomerRegisterView,
    FeastTokenRefreshView,
    SuperAdminLoginView,
    LogoutView,
    MeView,
)

urlpatterns = [
    path("staff/login/", StaffLoginView.as_view(), name="staff-login"),
    path("customer/login/", CustomerLoginView.as_view(), name="customer-login"),
    path("customer/register/", CustomerRegisterView.as_view(), name="customer-register"),
    path("token/refresh/", FeastTokenRefreshView.as_view(), name="token-refresh"),
    path("superadmin/login/", SuperAdminLoginView.as_view(), name="superadmin-login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
