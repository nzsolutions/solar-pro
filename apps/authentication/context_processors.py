from apps.masters.models import AccessControl
from apps.employees.models import Employee


def allowed_modules_processor(request):
    """
    Context processor that replicates Laravel's View::share('allowedModules', ...).
    - If user is Admin (is_admin == 1): allowedModules is None (can see all).
    - If user is Employee (is_admin == 0): queries live DB permissions based on current employee role.
    - If unauthenticated: allowedModules is empty list.
    """
    is_admin = request.session.get('is_admin')
    user_id = request.session.get('user_id')

    if not user_id:
        return {'allowedModules': []}

    if is_admin == 1:
        return {'allowedModules': None}

    # Query live role directly from Employee to prevent stale session permissions
    employee = Employee.objects.filter(id=user_id, status='active').first()
    if employee and employee.role:
        allowed = list(
            AccessControl.objects.filter(role_id=employee.role)
            .values_list('menu_key', flat=True)
        )
    else:
        allowed = []

    return {'allowedModules': allowed}
