from django.urls import path
from apps.authentication import views

urlpatterns = [
    path('admin/login', views.login_view, name='admin_login'),
    path('admin/login/submit', views.login_view, name='admin_login_submit'),
    path('admin/logout', views.logout_view, name='admin_logout'),
    path('employee/logout', views.logout_view, name='employee_logout'),
    path('admin/settings/account', views.account_settings_view, name='admin_settings_account'),
]
