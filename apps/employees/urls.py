from django.urls import path
from apps.employees import views

urlpatterns = [
    path('admin/employees', views.employees_index, name='admin_employees_index'),
    path('admin/employees/store', views.employee_store, name='admin_employees_store'),
    path('admin/employees/<int:id>/edit', views.employee_edit, name='admin_employees_edit'),
    path('admin/employees/<int:id>/update', views.employee_update, name='admin_employees_update'),
    path('admin/employees/<int:id>/destroy', views.employee_destroy, name='admin_employees_destroy'),
]
