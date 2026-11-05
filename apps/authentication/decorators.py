from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from apps.masters.models import AccessControl
from apps.employees.models import Employee

# Maps module menu_keys to allowed URL names / route name prefixes
# (matching the exact PHP AccessControlController $modules tree and sidebar)
MODULE_ROUTE_MAPPING = {
    'common-dashboard': [
        'admin_dashboard',
        'admin_projects_json',
    ],
    'department-master': [
        'admin_departments_index',
        'admin_departments_store',
        'admin_departments_update',
        'admin_departments_destroy',
    ],
    'designation-master': [
        'admin_designations_index',
        'admin_designations_store',
        'admin_designations_update',
        'admin_designations_destroy',
    ],
    'employee-master': [
        'admin_employees_index',
        'admin_employees_store',
        'admin_employees_edit',
        'admin_employees_update',
        'admin_employees_destroy',
    ],
    'access-control': [
        'admin_access_control_index',
        'admin_access_control_permissions',
        'admin_access_control_save',
    ],
    'smtp-config': [
        'admin_smtp_index',
        'admin_smtp_store',
        'admin_smtp_edit',
        'admin_smtp_update',
        'admin_smtp_destroy',
        'admin_smtp_test',
    ],
    'expense-category-master': [
        'admin_expense_categories_index',
        'admin_expense_categories_store',
        'admin_expense_categories_update',
        'admin_expense_categories_destroy',
    ],
    'stock-category-master': [
        'admin_stock_categories_index',
        'admin_stock_categories_store',
        'admin_stock_categories_update',
        'admin_stock_categories_destroy',
    ],
    'site-master': [
        'admin_sites_index',
        'admin_sites_store',
        'admin_sites_update',
        'admin_sites_destroy',
    ],
    'document-type-master': [
        'admin_document_types_index',
        'admin_document_types_store',
        'admin_document_types_update',
        'admin_document_types_destroy',
    ],
    'attendance-master': [
        'admin_attendance_master_create',
        'admin_attendance_master_store',
    ],
    'project-reports': [
        'admin_projects_report',
        'admin_projects_report_excel',
        'admin_projects_report_pdf',
    ],
    'maintenance-reports': [
        'admin_maintenance_report',
        'admin_maintenance_report_excel',
        'admin_maintenance_report_pdf',
    ],
    'attendance-report': [
        'admin_attendance_report',
        'admin_attendance_report_excel',
        'admin_attendance_report_pdf',
    ],
    'stock-report': [
        'admin_stock_report',
        'admin_stock_report_excel',
        'admin_stock_report_pdf',
    ],
    'expense-report': [
        'admin_expense_report_index',
    ],
    'all-projects': [
        'admin_projects_index',
        'admin_projects_show',
        'admin_projects_edit',
        'admin_projects_update',
        'admin_projects_destroy',
        'admin_projects_documents_remove',
        'admin_projects_stock_categories',
        'admin_projects_stock_items',
    ],
    'add-project': [
        'admin_projects_create',
        'admin_projects_store',
    ],
    'maintenance-charts': [
        'admin_maintenance_index',
    ],
    'employee-expenses': [
        'admin_employee_expenses_index',
        'admin_employee_expenses_update_status',
    ],
    'add-form': [
        'admin_forms_create',
        'admin_forms_store',
    ],
    'all-forms': [
        'admin_forms_index',
        'admin_forms_show',
        'admin_forms_edit',
        'admin_forms_update',
        'admin_forms_destroy',
    ],
    'form-submissions': [
        'admin_form_submissions_index',
        'admin_form_submissions_edit',
        'admin_form_submissions_update',
    ],
    'dashboard-config': [
        'admin_dashboard_config',
        'admin_dashboard_config_save',
        'admin_dashboard_fields',
        'admin_dashboard_section_store',
        'admin_dashboard_section_delete',
        'admin_dashboard_config_backup',
        'admin_dashboard_config_backup_save',
        'admin_dashboard_config_backup_section_store',
        'admin_dashboard_config_backup_section_delete',
        'admin_dashboard_config_backup_section_delete_alt',
        'admin_dashboard_config_backup_fields',
    ],
    'dynamic-dashboard': [
        'admin_dynamic_dashboard',
        'admin_dynamic_dashboard_backup',
        'admin_dashboard_backup_legacy',
    ],
    'stock-dashboard': [
        'admin_stock_dashboard',
    ],
    'opening-stock': [
        'admin_stock_opening_create',
        'admin_stock_opening_store',
        'admin_grn_create',
        'admin_grn_store',
    ],
    'assign-stock': [
        'admin_stock_assign_index',
        'admin_stock_assign_store',
    ],
}

# Reverse lookup: url_name -> required menu_key
URL_NAME_TO_MODULE = {}
for module_key, url_names in MODULE_ROUTE_MAPPING.items():
    for name in url_names:
        URL_NAME_TO_MODULE[name] = module_key


def get_employee_allowed_modules(employee_id):
    """
    Looks up live DB permissions for an employee based on their current designation/role.
    Prevents stale permissions by querying the DB on each request.
    """
    employee = Employee.objects.filter(id=employee_id, status='active').first()
    if not employee or not employee.role:
        return []
    
    return list(
        AccessControl.objects.filter(role_id=employee.role)
        .values_list('menu_key', flat=True)
    )


def admin_required(view_func):
    """
    Protects application routes by enforcing RBAC:
    - If not logged in -> redirect to admin_login.
    - If is_admin == 1 -> full access granted.
    - If is_admin == 0 (Employee):
        - Looks up employee's live permissions from AccessControl table.
        - If route is mapped to a module:
            - If module in allowed_modules -> access granted.
            - If module NOT in allowed_modules:
                - For AJAX / JSON API -> return 403 JSON.
                - For normal HTTP request -> message error and redirect to employee_dashboard.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user_id = request.session.get('user_id')
        if not user_id:
            messages.error(request, 'Please log in to continue.')
            return redirect('admin_login')

        is_admin = request.session.get('is_admin')
        if is_admin == 1:
            return view_func(request, *args, **kwargs)

        if is_admin == 0:
            # Check employee status
            employee = Employee.objects.filter(id=user_id).first()
            if not employee or employee.status != 'active':
                request.session.flush()
                messages.error(request, 'Your account is inactive. Contact your admin.')
                return redirect('admin_login')

            # Update session role in case admin changed employee's role
            request.session['role'] = employee.role

            url_name = getattr(request.resolver_match, 'url_name', '')
            required_module = URL_NAME_TO_MODULE.get(url_name)

            # If the view is explicitly associated with a module, verify permission
            if required_module:
                allowed_modules = get_employee_allowed_modules(user_id)
                if required_module not in allowed_modules:
                    is_ajax = (
                        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
                        request.content_type == 'application/json' or
                        'application/json' in request.headers.get('Accept', '') or
                        request.path.endswith('-json') or
                        '/api/' in request.path
                    )
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': 'Access denied. You do not have permission for this module.'}, status=403)
                    
                    messages.error(request, 'Access denied. You do not have permission to access this module.')
                    return redirect('employee_dashboard')

            return view_func(request, *args, **kwargs)

        # Neither admin nor employee
        messages.error(request, 'Please log in to continue.')
        return redirect('admin_login')

    return _wrapped_view


def employee_required(view_func):
    """
    Ensures that the user has an active session and is an Employee (is_admin == 0).
    Matches Laravel's CheckEmployeeAuth middleware.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user_id = request.session.get('user_id')
        is_admin = request.session.get('is_admin')
        if not user_id or is_admin != 0:
            messages.error(request, 'Please log in to continue.')
            return redirect('admin_login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
