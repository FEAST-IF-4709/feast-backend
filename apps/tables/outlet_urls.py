from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

# Router for /api/v1/outlets/{outlet_id}/tables/
router = DefaultRouter()
router.register(r"", views.TableViewSet, basename="outlet-table")

urlpatterns = router.urls
