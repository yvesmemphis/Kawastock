from django.urls import path
from .views import DashboardSummaryView, LowStockView, SalesExportView, SalesReportView

urlpatterns = [
    path("dashboard/summary/", DashboardSummaryView.as_view()),
    path("reports/sales/", SalesReportView.as_view()),
    path("reports/sales/export/", SalesExportView.as_view()),
    path("reports/low-stock/", LowStockView.as_view()),
]