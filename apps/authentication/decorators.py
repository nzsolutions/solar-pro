from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    """
    Ensures that the user has an active session and is an Admin (is_admin == 1).
    Matches Laravel's CheckAdminAuth middleware.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.session.get('user_id') or request.session.get('is_admin') != 1:
            messages.error(request, 'Please log in to continue.')
            return redirect('admin_login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def employee_required(view_func):
    """
    Ensures that the user has an active session and is an Employee (is_admin == 0).
    Matches Laravel's CheckEmployeeAuth middleware.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.session.get('user_id') or request.session.get('is_admin') != 0:
            messages.error(request, 'Please log in to continue.')
            return redirect('admin_login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
