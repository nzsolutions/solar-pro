from apps.masters.models import AccessControl


def allowed_modules_processor(request):
    """
    Context processor that replicates Laravel's View::share('allowedModules', ...).
    - If user is Admin (is_admin == 1): allowedModules is None (can see all).
    - If user is Employee (is_admin == 0): allowedModules is a list of allowed menu_keys.
    - If unauthenticated: allowedModules is empty list.
    """
    is_admin = request.session.get('is_admin')
    user_id = request.session.get('user_id')

    if not user_id:
        return {'allowedModules': []}

    if is_admin == 1:
        return {'allowedModules': None}

    role_id = request.session.get('role')
    if role_id:
        allowed = list(
            AccessControl.objects.filter(role_id=role_id)
            .values_list('menu_key', flat=True)
        )
    else:
        allowed = []

    return {'allowedModules': allowed}
