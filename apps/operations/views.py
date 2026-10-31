import os
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.contrib import messages
from django.conf import settings
from apps.authentication.decorators import admin_required, employee_required
from apps.operations.models import Project, ProjectDocument, Lead
from apps.employees.models import Employee, EmployeeAttendance
from apps.inventory.models import OpeningStock, StockCategory, AssignedStock
from apps.expenses.models import Expense
from apps.masters.models import SiteMaster, DocumentTypeMaster


# ==========================================
# 1. DASHBOARD VIEWS
# ==========================================
@admin_required
def admin_dashboard_view(request):
    project_id = request.GET.get('project')
    today = timezone.localdate()

    field_staff_total = Employee.objects.filter(status='active').count()
    field_staff_on_duty = Employee.objects.filter(status='active').count()

    total_projects = Project.objects.count()
    planning_projects = Project.objects.filter(status='planning').count()
    active_projects = Project.objects.filter(status='in_progress').count()
    on_hold_projects = Project.objects.filter(status='on_hold').count()

    exp_qs = Expense.objects.all()
    if project_id:
        exp_qs = exp_qs.filter(project_id=project_id)
    
    expenses_approved = exp_qs.filter(status='approved').aggregate(s=Sum('amount'))['s'] or 0
    expenses_pending = exp_qs.filter(status='pending').aggregate(s=Sum('amount'))['s'] or 0

    stock_val = OpeningStock.objects.annotate(
        val=ExpressionWrapper(F('quantity') * F('rate'), output_field=DecimalField())
    ).aggregate(s=Sum('val'))['s'] or 0

    attendance_today = EmployeeAttendance.objects.filter(punch_in__date=today).count()
    att_qs = EmployeeAttendance.objects.filter(punch_in__date=today).order_by('-punch_in')
    
    emp_map = {e.id: e.name for e in Employee.objects.all()}
    proj_map = {p.id: p.client_name for p in Project.objects.all()}

    attendance_log = []
    for att in att_qs:
        attendance_log.append({
            'employee_name': emp_map.get(att.employee_id, f"Employee #{att.employee_id}"),
            'project_name': proj_map.get(att.employee_id, '—'),
            'punch_in': att.punch_in,
            'punch_out': att.punch_out,
        })

    selected_project = Project.objects.filter(id=project_id).first() if project_id else None

    data = {
        'field_staff_on_duty': field_staff_on_duty,
        'field_staff_total': field_staff_total,
        'active_projects': active_projects,
        'total_projects': total_projects,
        'planning_projects': planning_projects,
        'on_hold_projects': on_hold_projects,
        'expenses_approved': expenses_approved,
        'expenses_pending': expenses_pending,
        'stock_total_value': stock_val,
        'attendance_today': attendance_today,
    }

    context = {
        'data': data,
        'attendance_log': attendance_log,
        'selected_project': selected_project,
        'project_id': project_id,
        'today_date': today.strftime('%d %b %Y'),
    }
    return render(request, 'admin/dashboard.html', context)


@admin_required
def admin_projects_json_view(request):
    sites = {s.id: s.site_address for s in SiteMaster.objects.all()}
    projects = []
    for p in Project.objects.order_by('-created_at'):
        projects.append({
            'id': p.id,
            'client_name': p.client_name,
            'address': sites.get(p.site_id, '—'),
            'status': p.status,
        })
    return JsonResponse(projects, safe=False)


@employee_required
def employee_dashboard_view(request):
    user_id = request.session.get('user_id')
    employee = get_object_or_404(Employee, id=user_id)
    
    projects = []
    for p in Project.objects.all():
        staff_list = p.field_staff if isinstance(p.field_staff, list) else []
        if p.site_manager == user_id or str(user_id) in [str(x) for x in staff_list]:
            projects.append(p)

    return render(request, 'admin/employee-dashboard.html', {
        'employee': employee,
        'projects': projects,
    })


# ==========================================
# 2. PROJECTS OPERATIONS VIEWS
# ==========================================
@admin_required
def projects_index(request):
    search = request.GET.get('search', '').strip()
    qs = Project.objects.all()

    if search:
        qs = qs.filter(client_name__icontains=search)

    sites_map = {s.id: s for s in SiteMaster.objects.all()}
    emp_map = {e.id: e.name for e in Employee.objects.all()}

    projects = []
    for p in qs.order_by('-created_at'):
        site = sites_map.get(p.site_id)
        projects.append({
            'id': p.id,
            'code': f"SP-{str(p.id).zfill(4)}",
            'client_name': p.client_name,
            'site_name': site.site_name if site else '—',
            'address': site.site_address if site else '—',
            'manager_name': emp_map.get(p.site_manager, '—'),
            'manager_role': 'Site Manager',
            'status': p.status,
            'system_size': 0,
            'generated_kwh': 0,
            'panel_type': '—',
            'created_at': p.created_at,
        })

    data = {
        'total_projects': Project.objects.count(),
        'active_projects': Project.objects.filter(status='in_progress').count(),
        'completed_projects': Project.objects.filter(status='completed').count(),
        'planning_projects': Project.objects.filter(status='planning').count(),
        'on_hold_projects': Project.objects.filter(status='on_hold').count(),
        'maintenance_projects': Project.objects.filter(status='maintenance').count(),
    }

    return render(request, 'admin/operation/projects.html', {
        'projects': projects,
        'data': data,
    })


@admin_required
def project_stock_categories_json(request):
    search = request.GET.get('search', '').strip()
    qs = StockCategory.objects.all()
    if search:
        qs = qs.filter(category_name__icontains=search)
    data = [{'id': c.id, 'category_name': c.category_name} for c in qs[:50]]
    return JsonResponse(data, safe=False)


@admin_required
def project_stock_items_json(request):
    category_id = request.GET.get('category')
    search = request.GET.get('search', '').strip()
    if not category_id:
        return JsonResponse([], safe=False)

    qs = OpeningStock.objects.filter(category=category_id)
    if search:
        qs = qs.filter(item_name__icontains=search)

    data = [{
        'id': item.id,
        'item_name': item.item_name,
        'unit': item.unit,
        'quantity': float(item.quantity),
        'rate': float(item.rate),
    } for item in qs[:100]]
    return JsonResponse(data, safe=False)


@admin_required
def project_create(request):
    site_managers = Employee.objects.order_by('name')
    field_staff = Employee.objects.order_by('name')
    stock_categories = StockCategory.objects.order_by('category_name')
    sites = SiteMaster.objects.order_by('site_name')
    document_types = DocumentTypeMaster.objects.filter(status='active').order_by('type_name')

    status_options = ['planning', 'in_progress', 'completed', 'on_hold', 'maintenance']
    reporting_frequencies = ['Hourly', 'Daily', 'Weekly', 'As Required', 'Monthly']

    return render(request, 'admin/operation/addproject.html', {
        'siteManagers': site_managers,
        'fieldStaff': field_staff,
        'stockCategories': stock_categories,
        'sites': sites,
        'documentTypes': document_types,
        'statusOptions': status_options,
        'reportingFrequencies': reporting_frequencies,
    })


@admin_required
def project_store(request):
    if request.method == 'POST':
        client_name = request.POST.get('client_name', '').strip()
        site_id = request.POST.get('site_id')
        status = request.POST.get('status', 'planning')

        if not client_name or not site_id:
            messages.error(request, 'Client name and site are required.')
            return redirect('admin_projects_create')

        staff_list = [int(x) for x in request.POST.getlist('field_staff[]') if x.isdigit()]

        project = Project.objects.create(
            company_id=request.session.get('company_id', 1),
            client_name=client_name,
            site_id=int(site_id),
            site_manager=int(request.POST.get('site_manager')) if request.POST.get('site_manager') else None,
            field_staff=staff_list,
            status=status,
            start_date=request.POST.get('start_date') or None,
            end_date=request.POST.get('end_date') or None,
            reporting_frequency=request.POST.get('reporting_frequency', 'Weekly'),
            notes=request.POST.get('notes', ''),
        )

        # Handle Assigned Stock
        stock_ids = request.POST.getlist('stock_selected[]')
        for item_id in stock_ids:
            if item_id.isdigit():
                qty = request.POST.get(f'stock_qty[{item_id}]', 1)
                AssignedStock.objects.create(
                    project_id=project.id,
                    item_id=int(item_id),
                    qty=float(qty),
                )

        # Handle Multi-Document Uploads
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'project_documents')
        os.makedirs(upload_dir, exist_ok=True)

        type_ids = request.POST.getlist('document_type_id[]')
        for idx, type_id in enumerate(type_ids):
            files = request.FILES.getlist(f'document[{idx}][]')
            saved_paths = []
            for f in files:
                ext = os.path.splitext(f.name)[1]
                fname = f"{uuid.uuid4().hex}{ext}"
                dest = os.path.join(upload_dir, fname)
                with open(dest, 'wb+') as d:
                    for chunk in f.chunks():
                        d.write(chunk)
                saved_paths.append(f"project_documents/{fname}")

            if saved_paths and type_id.isdigit():
                ProjectDocument.objects.create(
                    project_id=project.id,
                    document_type_id=int(type_id),
                    file=",".join(saved_paths),
                    name=",".join(saved_paths),
                )

        messages.success(request, f'Project "{client_name}" created successfully.')
        return redirect('admin_projects_index')

    return redirect('admin_projects_create')


@admin_required
def project_show(request, id):
    """
    Project Stock & Document Popup (JSON).
    Matches Laravel AdminProjectController::show.
    """
    project = get_object_or_404(Project, id=id)

    stock_items_map = {item.id: item for item in OpeningStock.objects.all()}
    cat_map = {c.id: c.category_name for c in StockCategory.objects.all()}

    assigned_stock = []
    for ast in AssignedStock.objects.filter(project_id=id):
        item = stock_items_map.get(ast.item_id)
        if item:
            assigned_stock.append({
                'item_id': item.id,
                'item_name': item.item_name,
                'category': cat_map.get(item.category, '—'),
                'unit': item.unit,
                'rate': float(item.rate),
                'qty': float(ast.qty),
            })

    doc_types_map = {dt.id: dt.type_name for dt in DocumentTypeMaster.objects.all()}
    documents = []
    for doc in ProjectDocument.objects.filter(project_id=id):
        file_paths = [p for p in doc.file.split(',') if p]
        file_objs = []
        for path in file_paths:
            filename = os.path.basename(path)
            file_objs.append({
                'name': filename,
                'url': f"/media/{path}",
            })
        documents.append({
            'type_name': doc_types_map.get(doc.document_type_id, 'Document'),
            'files': file_objs,
        })

    return JsonResponse({
        'client_name': project.client_name,
        'code': f"SP-{str(project.id).zfill(4)}",
        'stock': assigned_stock,
        'documents': documents,
    })


@admin_required
def project_edit(request, id):
    project = get_object_or_404(Project, id=id)
    site_managers = Employee.objects.order_by('name')
    field_staff = Employee.objects.order_by('name')
    stock_categories = StockCategory.objects.order_by('category_name')
    sites = SiteMaster.objects.order_by('site_name')
    document_types = DocumentTypeMaster.objects.filter(status='active').order_by('type_name')

    assigned_stock = AssignedStock.objects.filter(project_id=id)
    project_documents = ProjectDocument.objects.filter(project_id=id)

    status_options = ['planning', 'in_progress', 'completed', 'on_hold', 'maintenance']
    reporting_frequencies = ['Hourly', 'Daily', 'Weekly', 'As Required', 'Monthly']

    return render(request, 'admin/operation/editprojects.html', {
        'project': project,
        'siteManagers': site_managers,
        'fieldStaff': field_staff,
        'stockCategories': stock_categories,
        'sites': sites,
        'documentTypes': document_types,
        'assignedStock': assigned_stock,
        'projectDocuments': project_documents,
        'statusOptions': status_options,
        'reportingFrequencies': reporting_frequencies,
    })


@admin_required
def project_update(request, id):
    project = get_object_or_404(Project, id=id)

    if request.method == 'POST':
        client_name = request.POST.get('client_name', '').strip()
        site_id = request.POST.get('site_id')

        if not client_name or not site_id:
            messages.error(request, 'Client name and site are required.')
            return redirect('admin_projects_edit', id=id)

        staff_list = [int(x) for x in request.POST.getlist('field_staff[]') if x.isdigit()]

        project.client_name = client_name
        project.site_id = int(site_id)
        project.site_manager = int(request.POST.get('site_manager')) if request.POST.get('site_manager') else None
        project.field_staff = staff_list
        project.status = request.POST.get('status', project.status)
        project.start_date = request.POST.get('start_date') or None
        project.end_date = request.POST.get('end_date') or None
        project.reporting_frequency = request.POST.get('reporting_frequency', project.reporting_frequency)
        project.notes = request.POST.get('notes', project.notes)
        project.save()

        messages.success(request, f'Project "{client_name}" updated successfully.')
        return redirect('admin_projects_index')

    return redirect('admin_projects_edit', id=id)


@admin_required
def project_destroy(request, id):
    project = get_object_or_404(Project, id=id)
    project.delete()
    messages.success(request, 'Project removed successfully.')
    return redirect('admin_projects_index')


@admin_required
def remove_project_document(request, id):
    if request.method == 'POST':
        doc_id = request.POST.get('document_id')
        file_to_remove = request.POST.get('file')

        doc = ProjectDocument.objects.filter(id=doc_id, project_id=id).first()
        if not doc:
            messages.error(request, 'Document not found.')
            return redirect('admin_projects_edit', id=id)

        paths = [p for p in doc.file.split(',') if p]
        remaining = [p for p in paths if os.path.basename(p) != file_to_remove]

        # Remove physical file if exists
        for p in paths:
            if os.path.basename(p) == file_to_remove:
                abs_p = os.path.join(settings.MEDIA_ROOT, p)
                if os.path.exists(abs_p):
                    try:
                        os.remove(abs_p)
                    except Exception:
                        pass

        if not remaining:
            doc.delete()
        else:
            doc.file = ",".join(remaining)
            doc.name = ",".join(remaining)
            doc.save()

        messages.success(request, 'Document removed successfully.')
    return redirect('admin_projects_edit', id=id)


@admin_required
def maintenance_charts_view(request):
    """
    Maintenance Charts Analytics.
    Matches Laravel AdminProjectController::maintenanceCharts.
    """
    return render(request, 'admin/operation/maintenancecharts.html')
