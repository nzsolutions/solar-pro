from django.urls import path
from apps.masters import views

urlpatterns = [
    # Departments
    path('admin/departments', views.departments_index, name='admin_departments_index'),
    path('admin/departments/store', views.department_store, name='admin_departments_store'),
    path('admin/departments/<int:id>/update', views.department_update, name='admin_departments_update'),
    path('admin/departments/<int:id>/destroy', views.department_destroy, name='admin_departments_destroy'),

    # Designations
    path('admin/designations', views.designations_index, name='admin_designations_index'),
    path('admin/designations/store', views.designation_store, name='admin_designations_store'),
    path('admin/designations/<int:id>/update', views.designation_update, name='admin_designations_update'),
    path('admin/designations/<int:id>/destroy', views.designation_destroy, name='admin_designations_destroy'),

    # Sites
    path('admin/sites', views.sites_index, name='admin_sites_index'),
    path('admin/sites/store', views.site_store, name='admin_sites_store'),
    path('admin/sites/<int:id>/update', views.site_update, name='admin_sites_update'),
    path('admin/sites/<int:id>/destroy', views.site_destroy, name='admin_sites_destroy'),

    # Document Types
    path('admin/document-types', views.document_types_index, name='admin_document_types_index'),
    path('admin/document-types/store', views.document_type_store, name='admin_document_types_store'),
    path('admin/document-types/<int:id>/update', views.document_type_update, name='admin_document_types_update'),
    path('admin/document-types/<int:id>/destroy', views.document_type_destroy, name='admin_document_types_destroy'),

    # Attendance Master
    path('admin/attendance/master', views.attendance_master_create, name='admin_attendance_master_create'),
    path('admin/attendance/master/store', views.attendance_master_store, name='admin_attendance_master_store'),

    # SMTP Configuration
    path('admin/smtp', views.smtp_index, name='admin_smtp_index'),
    path('admin/smtp/store', views.smtp_store, name='admin_smtp_store'),
    path('admin/smtp/<int:id>/edit', views.smtp_edit, name='admin_smtp_edit'),
    path('admin/smtp/<int:id>/update', views.smtp_update, name='admin_smtp_update'),
    path('admin/smtp/<int:id>/destroy', views.smtp_destroy, name='admin_smtp_destroy'),
    path('admin/smtp/test', views.smtp_test_mail, name='admin_smtp_test'),

    # Access Control
    path('admin/access-control', views.access_control_index, name='admin_access_control_index'),
    path('admin/access-control/permissions/<int:role_id>', views.access_control_permissions, name='admin_access_control_permissions'),
    path('admin/access-control/save', views.access_control_save, name='admin_access_control_save'),

    # Activity Master
    path('admin/activities', views.activities_index, name='admin_activities_index'),
    path('admin/activities/store', views.activity_store, name='admin_activities_store'),
    path('admin/activities/<int:id>/update', views.activity_update, name='admin_activities_update'),
    path('admin/activities/<int:id>/toggle-status', views.activity_toggle_status, name='admin_activities_toggle_status'),
]
