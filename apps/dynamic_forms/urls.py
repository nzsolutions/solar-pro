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

    # Dynamic Dashboard
    path('dynamic-dashboard', views.dynamic_dashboard, name='admin_dynamic_dashboard'),
]
