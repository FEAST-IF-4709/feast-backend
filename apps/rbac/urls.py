from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.rbac.views import PermissionListView, RoleViewSet

router = DefaultRouter()
router.register("roles", RoleViewSet, basename="role")

urlpatterns = [
    path("permissions/", PermissionListView.as_view(), name="permission-list"),
    path("", include(router.urls)),
]
