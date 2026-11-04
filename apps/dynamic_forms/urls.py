from django.urls import path
from apps.dynamic_forms import views

urlpatterns = [
    # Forms CRUD
    path('admin/forms', views.forms_index, name='admin_forms_index'),
    path('admin/forms/create', views.forms_create, name='admin_forms_create'),
    path('admin/forms/store', views.forms_store, name='admin_forms_store'),
    path('admin/forms/<int:id>', views.forms_show, name='admin_forms_show'),
    path('admin/forms/<int:id>/edit', views.forms_edit, name='admin_forms_edit'),
    path('admin/forms/<int:id>/update', views.forms_update, name='admin_forms_update'),
    path('admin/forms/<int:id>/destroy', views.forms_destroy, name='admin_forms_destroy'),

    # Submissions
    path('admin/form-submissions', views.form_submissions_index, name='admin_form_submissions_index'),
    path('admin/form-submissions/<int:id>/edit', views.form_submissions_edit, name='admin_form_submissions_edit'),
    path('admin/form-submissions/<int:id>/update', views.form_submissions_update, name='admin_form_submissions_update'),

    # Dynamic Dashboard Config
    path('dashboard/config', views.dashboard_config_index, name='admin_dashboard_config'),
    path('dashboard/config/save', views.dashboard_config_save, name='admin_dashboard_config_save'),
    path('admin/config/fields/<int:formId>', views.get_form_fields, name='admin_dashboard_fields'),

    # Dashboard Section Master (AJAX)
    path('dashboard/section/store', views.dashboard_section_store, name='admin_dashboard_section_store'),
    path('dashboard/section/<int:section_id>/delete', views.dashboard_section_delete, name='admin_dashboard_section_delete'),

    # Dynamic Dashboard
    path('dynamic-dashboard', views.dynamic_dashboard, name='admin_dynamic_dashboard'),

    # BACKUP (TEST) Dynamic Dashboard Config & Routes (matching Laravel web.php)
    path('dashboard-backup/config', views.dashboard_config_backup_index, name='admin_dashboard_config_backup'),
    path('dashboard-backup/config/save', views.dashboard_config_backup_save, name='admin_dashboard_config_backup_save'),
    path('dashboard-backup/section', views.dashboard_backup_section_store, name='admin_dashboard_config_backup_section_store'),
    path('dashboard-backup/section/<int:section_id>', views.dashboard_backup_section_delete, name='admin_dashboard_config_backup_section_delete'),
    path('dashboard-backup/section/<int:section_id>/delete', views.dashboard_backup_section_delete, name='admin_dashboard_config_backup_section_delete_alt'),
    path('admin/config-backup/fields/<int:formId>', views.get_form_fields, name='admin_dashboard_config_backup_fields'),
    path('dynamic-dashboard-backup', views.dynamic_dashboard_backup, name='admin_dynamic_dashboard_backup'),
    path('dashboard-backup', views.dynamic_dashboard_backup, name='admin_dashboard_backup_legacy'),
]
