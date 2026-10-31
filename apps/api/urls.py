from django.urls import path
from apps.api import views

urlpatterns = [
    # Auth
    path('login', views.login, name='api_login'),
    path('password/send-otp', views.send_otp, name='api_password_send_otp'),
    path('password/validate-otp', views.validate_otp, name='api_password_validate_otp'),
    path('password/reset', views.reset_password, name='api_password_reset'),

    # Projects
    path('get-project-by-employee-id', views.get_projects_by_employee_id, name='api_get_projects_by_employee_id'),

    # Employee Profile
    path('get-employee-profile', views.get_employee_profile, name='api_get_employee_profile'),
    path('update-employee-profile', views.update_employee_profile, name='api_update_employee_profile'),

    # Punch In / Punch Out
    path('punch-in', views.punch_in, name='api_punch_in'),
    path('punch-out', views.punch_out, name='api_punch_out'),

    # Expenses
    path('get-expenses', views.get_employee_expenses, name='api_get_expenses'),
    path('add-expense', views.add_expense, name='api_add_expense'),
    path('get-expense-categories', views.get_expense_categories, name='api_get_expense_categories'),
    path('get-employee-expenses', views.get_employee_expenses, name='api_get_employee_expenses'),

    # Stock
    path('get-stock-by-project-id', views.get_stock_by_project_id, name='api_get_stock_by_project_id'),

    # Dynamic Forms
    path('get-dynamic-forms', views.get_dynamic_forms, name='api_get_dynamic_forms'),
    path('submit-form', views.submit_form, name='api_submit_form'),
    path('get-employee-submissions/<int:emp_id>', views.get_employee_submissions, name='api_get_employee_submissions'),

    # Firebase
    path('test-firebase', views.test_firebase_connection, name='api_test_firebase'),
    path('test-topic-push', views.test_topic_notification, name='api_test_topic_push'),
    path('test-token-push', views.test_token_notification, name='api_test_token_push'),
    path('send-employee-notification', views.send_employee_notification, name='api_send_employee_notification'),

    # Analytics
    path('employee-graph-analytics', views.employee_graph_analytics, name='api_employee_graph_analytics'),
]
