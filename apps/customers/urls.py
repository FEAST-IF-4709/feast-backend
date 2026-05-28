from django.urls import path

from . import views

urlpatterns = [
    path("search/", views.CustomerSearchView.as_view(), name="customer-search"),
]
