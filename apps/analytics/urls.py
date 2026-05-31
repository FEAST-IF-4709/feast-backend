from django.urls import path
from .views import DashboardSummaryView, DailyRevenueChartView

urlpatterns = [
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="analytics-dashboard-summary"),
    path("dashboard/daily-chart/", DailyRevenueChartView.as_view(), name="analytics-dashboard-daily-chart"),
]
