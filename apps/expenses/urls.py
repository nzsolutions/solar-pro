from django.urls import path
from apps.expenses import views

urlpatterns = [
    # Expense Categories
    path('admin/expense-categories', views.expense_categories_index, name='admin_expense_categories_index'),
    path('admin/expense-categories/store', views.expense_category_store, name='admin_expense_categories_store'),
    path('admin/expense-categories/<int:id>/update', views.expense_category_update, name='admin_expense_categories_update'),
    path('admin/expense-categories/<int:id>/destroy', views.expense_category_destroy, name='admin_expense_categories_destroy'),

    # Employee Expenses Approval
    path('admin/employee-expenses', views.employee_expenses, name='admin_employee_expenses_index'),
    path('admin/employee-expenses/<int:id>/status', views.update_expense_status, name='admin_employee_expenses_update_status'),

    # Expense Report
    path('admin/expense-report', views.expense_report, name='admin_expense_report_index'),
]
