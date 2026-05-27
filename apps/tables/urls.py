from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

# Router for /api/v1/tables/{id}/ (retrieve, update, delete, rotate-qr)
router = DefaultRouter()
router.register(r"", views.TableViewSet, basename="table")

urlpatterns = router.urls
