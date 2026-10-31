from django.urls import path
from apps.reports import views

urlpatterns = [
    # Project Reports
    path('admin/reports/projects', views.project_report, name='admin_projects_report'),
    path('admin/reports/projects/export/excel', views.project_report_export_excel, name='admin_projects_report_excel'),
    path('admin/reports/projects/export/pdf', views.project_report_export_pdf, name='admin_projects_report_pdf'),

    # Maintenance Reports
    path('admin/reports/maintenance', views.maintenance_report, name='admin_maintenance_report'),
    path('admin/reports/maintenance/export/excel', views.maintenance_report_export_excel, name='admin_maintenance_report_excel'),
    path('admin/reports/maintenance/export/pdf', views.maintenance_report_export_pdf, name='admin_maintenance_report_pdf'),

    # Attendance Reports
    path('admin/reports/attendance', views.attendance_report, name='admin_attendance_report'),
    path('admin/reports/attendance/export/excel', views.attendance_report_export_excel, name='admin_attendance_report_excel'),
    path('admin/reports/attendance/export/pdf', views.attendance_report_export_pdf, name='admin_attendance_report_pdf'),

    # Stock Reports
    path('admin/reports/stock', views.stock_report, name='admin_stock_report'),
    path('admin/reports/stock/export/excel', views.stock_report_export_excel, name='admin_stock_report_excel'),
    path('admin/reports/stock/export/pdf', views.stock_report_export_pdf, name='admin_stock_report_pdf'),
]
