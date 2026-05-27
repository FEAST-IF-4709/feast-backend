from django.urls import path
from .views import NearbyOutletsView

urlpatterns = [
    path("outlets/nearby/", NearbyOutletsView.as_view(), name="outlets-nearby"),
]
