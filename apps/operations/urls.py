from django.urls import path
from apps.operations import views

urlpatterns = [
    path('admin/dashboard', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin/projects-json', views.admin_projects_json_view, name='admin_projects_json'),
    path('employee/dashboard', views.employee_dashboard_view, name='employee_dashboard'),

    # Projects CRUD
    path('admin/projects', views.projects_index, name='admin_projects_index'),
    path('admin/projects/create', views.project_create, name='admin_projects_create'),
    path('admin/projects/store', views.project_store, name='admin_projects_store'),
    path('admin/projects/stock/categories', views.project_stock_categories_json, name='admin_projects_stock_categories'),
    path('admin/projects/stock/items', views.project_stock_items_json, name='admin_projects_stock_items'),
    path('admin/projects/<int:id>', views.project_show, name='admin_projects_show'),
    path('admin/projects/<int:id>/edit', views.project_edit, name='admin_projects_edit'),
    path('admin/projects/<int:id>/update', views.project_update, name='admin_projects_update'),
    path('admin/projects/<int:id>/destroy', views.project_destroy, name='admin_projects_destroy'),
    path('admin/projects/<int:id>/documents/remove', views.remove_project_document, name='admin_projects_documents_remove'),

    # Maintenance
    path('admin/maintenance', views.maintenance_charts_view, name='admin_maintenance_index'),

    # Leads Management
    path('admin/leads', views.leads_index, name='admin_leads_index'),
    path('admin/leads/create', views.lead_create, name='admin_addlead'),
    path('admin/leads/store', views.lead_store, name='admin_addlead_store'),
    path('admin/reports/leads', views.lead_report, name='admin_leads_report'),
    path('admin/reports/leads/excel', views.lead_report_excel, name='admin_leads_report_excel'),

    # Staff Management
    path('admin/staff', views.staff_index, name='admin_staff_index'),
    path('admin/staff/store', views.staff_store, name='admin_staff_store'),
    path('admin/staff/<int:id>/update', views.staff_update, name='admin_staff_update'),
    path('admin/staff/<int:id>/destroy', views.staff_destroy, name='admin_staff_destroy'),
]
