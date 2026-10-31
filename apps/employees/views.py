import os
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from apps.authentication.decorators import admin_required
from apps.authentication.hashers import LaravelBcryptPasswordHasher
from apps.employees.models import Employee
from apps.masters.models import DesignationMaster

hasher = LaravelBcryptPasswordHasher()


def handle_employee_document_uploads(request, existing_docs=None):
    docs = list(existing_docs or [])
    files = request.FILES.getlist('documents')
    
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'employees', 'docs')
    os.makedirs(upload_dir, exist_ok=True)

    for f in files:
        ext = os.path.splitext(f.name)[1]
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(upload_dir, unique_name)
        with open(file_path, 'wb+') as destination:
            for chunk in f.chunks():
                destination.write(chunk)

        docs.append({
            'name': f.name,
            'path': f"employees/docs/{unique_name}",
            'size': f.size,
        })
    return docs


@admin_required
def employees_index(request):
    search = request.GET.get('search', '').strip()
    qs = Employee.objects.all()

    if search:
        qs = qs.filter(name__icontains=search) | qs.filter(app_username__icontains=search)

    designations = DesignationMaster.objects.order_by('designation_name')
    desig_map = {d.id: d.designation_name for d in designations}

    employees = []
    for emp in qs.order_by('-id'):
        employees.append({
            'id': emp.id,
            'name': emp.name,
            'role_name': desig_map.get(emp.role, '—'),
            'app_username': emp.app_username,
            'phone': emp.phone or '—',
            'email': emp.email or '—',
            'status': emp.status,
            'created_at': emp.created_at,
        })

    return render(request, 'admin/master/employees.html', {
        'employees': employees,
        'designations': designations,
        'statusOptions': ['active', 'inactive'],
    })


@admin_required
def employee_store(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        role = request.POST.get('role')
        app_username = request.POST.get('app_username', '').strip()
        app_password = request.POST.get('app_password', '').strip()
        joining_date = request.POST.get('joining_date')
        relieving_date = request.POST.get('relieving_date') or None
        status = request.POST.get('status', 'active')

        if not name or not role or not app_username or not app_password or not joining_date:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('admin_employees_index')

        if Employee.objects.filter(app_username=app_username).exists():
            messages.error(request, f'Username "{app_username}" is already taken.')
            return redirect('admin_employees_index')

        documents = handle_employee_document_uploads(request)

        Employee.objects.create(
            company_id=request.session.get('company_id', 1),
            name=name,
            role=int(role),
            app_username=app_username,
            app_password=hasher.encode(app_password),
            joining_date=joining_date,
            relieving_date=relieving_date,
            status=status,
            dob=request.POST.get('dob') or None,
            gender=request.POST.get('gender') or None,
            phone=request.POST.get('phone', '').strip() or None,
            email=request.POST.get('email', '').strip() or None,
            address=request.POST.get('address', '').strip() or None,
            city=request.POST.get('city', '').strip() or None,
            pincode=request.POST.get('pincode', '').strip() or None,
            state=request.POST.get('state', '').strip() or None,
            documents=documents,
        )

        messages.success(request, f'Employee "{name}" was added successfully.')
    return redirect('admin_employees_index')


@admin_required
def employee_edit(request, id):
    employee = get_object_or_404(Employee, id=id)
    designations = DesignationMaster.objects.order_by('designation_name')

    return render(request, 'admin/master/editemployees.html', {
        'employee': employee,
        'designations': designations,
        'roles': [{'id': d.id, 'name': d.designation_name} for d in designations],
        'statusOptions': ['active', 'inactive'],
    })


@admin_required
def employee_update(request, id):
    employee = get_object_or_404(Employee, id=id)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        role = request.POST.get('role')
        app_username = request.POST.get('app_username', '').strip()
        joining_date = request.POST.get('joining_date')

        if not name or not role or not app_username or not joining_date:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('admin_employees_edit', id=id)

        if Employee.objects.filter(app_username=app_username).exclude(id=id).exists():
            messages.error(request, f'Username "{app_username}" is already taken.')
            return redirect('admin_employees_edit', id=id)

        employee.name = name
        employee.role = int(role)
        employee.app_username = app_username
        
        new_password = request.POST.get('app_password', '').strip()
        if new_password:
            employee.app_password = hasher.encode(new_password)

        employee.joining_date = joining_date
        employee.relieving_date = request.POST.get('relieving_date') or None
        employee.status = request.POST.get('status', 'active')
        employee.dob = request.POST.get('dob') or None
        employee.gender = request.POST.get('gender') or None
        employee.phone = request.POST.get('phone', '').strip() or None
        employee.email = request.POST.get('email', '').strip() or None
        employee.address = request.POST.get('address', '').strip() or None
        employee.city = request.POST.get('city', '').strip() or None
        employee.pincode = request.POST.get('pincode', '').strip() or None
        employee.state = request.POST.get('state', '').strip() or None

        # Upload additional documents if provided
        employee.documents = handle_employee_document_uploads(request, employee.documents)
        employee.save()

        messages.success(request, f'Employee "{name}" updated successfully.')
        return redirect('admin_employees_index')

    return redirect('admin_employees_edit', id=id)


@admin_required
def employee_destroy(request, id):
    employee = get_object_or_404(Employee, id=id)
    employee.delete()
    messages.success(request, 'Employee removed successfully.')
    return redirect('admin_employees_index')
