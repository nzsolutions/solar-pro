from django.shortcuts import render, redirect
from django.contrib import messages
from apps.authentication.models import AdminUser
from apps.employees.models import Employee
from apps.authentication.hashers import LaravelBcryptPasswordHasher
from apps.authentication.decorators import admin_required


hasher = LaravelBcryptPasswordHasher()


def login_view(request):
    """
    Handles Login for both Admins and Employees.
    Matches Laravel AdminAuthController::login logic.
    """
    if request.method == 'GET':
        # If already logged in, redirect accordingly
        if request.session.get('user_id'):
            if request.session.get('is_admin') == 1:
                return redirect('admin_dashboard')
            else:
                return redirect('employee_dashboard')
        return render(request, 'admin/login.html')

    identifier = request.POST.get('email', '').strip()
    password = request.POST.get('password', '').strip()

    if not identifier or not password:
        messages.error(request, 'Username and password are required.')
        return render(request, 'admin/login.html')

    # 1) Check admin_user table (matched by real email)
    admin = AdminUser.objects.filter(email=identifier).first()
    if admin and hasher.verify(password, admin.password):
        request.session.flush()
        request.session['is_admin'] = 1
        request.session['user_id'] = admin.id
        request.session['email'] = admin.email
        request.session['company_id'] = admin.company_id
        messages.success(request, 'Welcome back!')
        return redirect('admin_dashboard')

    # 2) Check employees table (matched by app_username)
    employee = Employee.objects.filter(app_username=identifier).first()
    if employee and hasher.verify(password, employee.app_password):
        if employee.status != 'active':
            messages.error(request, 'Your account is inactive. Contact your admin.')
            return render(request, 'admin/login.html')

        request.session.flush()
        request.session['is_admin'] = 0
        request.session['user_id'] = employee.id
        request.session['role'] = employee.role
        request.session['name'] = employee.name
        request.session['email'] = employee.email
        request.session['status'] = employee.status
        request.session['company_id'] = employee.company_id
        messages.success(request, 'Welcome back!')
        return redirect('employee_dashboard')

    messages.error(request, 'Invalid credentials.')
    return render(request, 'admin/login.html')


def logout_view(request):
    """
    Logs out the current session.
    Matches Laravel AdminAuthController::logout logic.
    """
    request.session.flush()
    messages.success(request, 'You have been logged out.')
    return redirect('admin_login')


@admin_required
def account_settings_view(request):
    """
    Account Settings page.
    Matches Laravel AdminAccountController logic.
    """
    user_id = request.session.get('user_id')
    admin = AdminUser.objects.filter(id=user_id).first()

    if request.method == 'POST':
        email = request.POST.get('email')
        new_password = request.POST.get('password')
        confirm_password = request.POST.get('password_confirmation')

        if email:
            admin.email = email

        if new_password:
            if new_password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return render(request, 'admin/accountsettings.html', {'admin': admin})
            admin.password = hasher.encode(new_password)

        admin.save()
        request.session['email'] = admin.email
        messages.success(request, 'Account settings updated successfully.')
        return redirect('admin_settings_account')

    return render(request, 'admin/accountsettings.html', {'admin': admin})
