import os
import uuid
import json
import calendar
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Count, Q
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.hashers import make_password
from apps.authentication.decorators import admin_required, employee_required
from apps.operations.models import Project, ProjectDocument, Lead
from apps.employees.models import Employee, EmployeeAttendance
from apps.inventory.models import OpeningStock, StockCategory, AssignedStock
from apps.expenses.models import Expense
from apps.masters.models import SiteMaster, DocumentTypeMaster, DesignationMaster, ActivityMaster
from apps.dynamic_forms.models import DynamicForm
from apps.operations.models import (
    Project,
    ProjectDocument,
    Lead,
    ProjectActivity,
    ProjectActivityInstance,
    ProjectActivityPhoto,
    ProjectActivityIssue,
)
from apps.operations.activity_service import ProjectActivityService
import openpyxl


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
    
    # Map employees to their projects via field_staff list or site_manager
    emp_project_map = {}
    for p in Project.objects.all():
        p_name = p.project_name or p.client_name or f"Project #{p.id}"
        if p.site_manager:
            emp_project_map[p.site_manager] = p_name
        if isinstance(p.field_staff, list):
            for eid in p.field_staff:
                try:
                    emp_project_map[int(eid)] = p_name
                except (ValueError, TypeError):
                    pass

    attendance_log = []
    for att in att_qs:
        attendance_log.append({
            'employee_name': emp_map.get(att.employee_id, f"Employee #{att.employee_id}"),
            'project_name': emp_project_map.get(att.employee_id, '—'),
            'punch_in': att.punch_in,
            'punch_out': att.punch_out,
        })

    selected_project = Project.objects.filter(id=project_id).first() if project_id else None

    # Dynamic Funnel data from Lead model
    lead_stages = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('site_visit_scheduled', 'Visit'),
        ('proposal_sent', 'Proposal'),
        ('won', 'Won')
    ]
    funnel_labels = [label for _, label in lead_stages]
    lead_counts = {item['status']: item['cnt'] for item in Lead.objects.values('status').annotate(cnt=Count('id'))}
    total_leads = sum(lead_counts.values())
    if total_leads > 0:
        funnel_data = [lead_counts.get(st, 0) for st, _ in lead_stages]
    else:
        funnel_data = [100, 85, 60, 40, 25]

    # Dynamic Energy trend curve based on capacity
    total_kw = Lead.objects.aggregate(s=Sum('system_size'))['s'] or 50.0
    total_mw = float(total_kw) / 1000.0
    months = ['Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May']
    seasonal_factors = [0.85, 0.90, 0.95, 1.05, 1.10, 1.00, 0.95, 0.92, 0.88, 0.94, 1.02, 1.08]
    base_mwh = max(total_mw * 4.5 * 30, 12.0)
    chart_energy_data = [round(base_mwh * f, 1) for f in seasonal_factors]
    chart_capacity_data = [round(base_mwh * 1.15, 1)] * len(months)
    chart_labels = months

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
        'chart_labels': json.dumps(chart_labels),
        'chart_energy_data': json.dumps(chart_energy_data),
        'chart_capacity_data': json.dumps(chart_capacity_data),
        'funnel_labels': json.dumps(funnel_labels),
        'funnel_data': json.dumps(funnel_data),
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

    from apps.masters.models import DesignationMaster
    desig = DesignationMaster.objects.filter(id=employee.role).first()

    return render(request, 'admin/employee-dashboard.html', {
        'employee': employee,
        'projects': projects,
        'designation_name': desig.designation_name if desig else employee.role,
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
            'project_name': p.project_name or p.client_name,
            'client_name': p.client_name,
            'site_name': site.site_name if site else '—',
            'address': site.site_address if site else '—',
            'manager_name': emp_map.get(p.site_manager, '—'),
            'manager_role': 'Site Manager',
            'status': p.status,
            'agreement': p.agreement,
            'agreement_start_date': p.agreement_start_date,
            'agreement_end_date': p.agreement_end_date,
            'billing_frequency': p.billing_frequency,
            'charge_frequency': p.charge_frequency,
            'bill_date': p.bill_date,
            'prepaid': p.prepaid,
            'free_period_check': p.free_period_check,
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

    # Available master activities & forms for Step 3: Add Activity
    master_activities = ActivityMaster.objects.filter(status='active').select_related('form').order_by('activity_title')
    available_forms = DynamicForm.objects.filter(is_active=1).order_by('form_name')
    frequency_choices = [f[0] for f in ActivityMaster.FREQUENCY_CHOICES]

    status_options = ['planning', 'in_progress', 'completed', 'on_hold', 'maintenance']
    reporting_frequencies = ['Hourly', 'Daily', 'Weekly', 'As Required', 'Monthly']

    return render(request, 'admin/operation/addproject.html', {
        'siteManagers': site_managers,
        'fieldStaff': field_staff,
        'stockCategories': stock_categories,
        'sites': sites,
        'documentTypes': document_types,
        'masterActivities': master_activities,
        'availableForms': available_forms,
        'frequencyChoices': frequency_choices,
        'statusOptions': status_options,
        'reportingFrequencies': reporting_frequencies,
    })


@admin_required
def project_store(request):
    if request.method == 'POST':
        client_name = request.POST.get('client_name', '').strip()
        project_name = request.POST.get('project_name', '').strip()
        site_id = request.POST.get('site_id')
        status = request.POST.get('status', 'planning')

        if not client_name or not site_id:
            messages.error(request, 'Client name and site are required.')
            return redirect('admin_projects_create')

        staff_list = [int(x) for x in request.POST.getlist('field_staff[]') if x.isdigit()]

        agreement = request.POST.get('agreement', 'No').strip()
        if agreement == 'Yes':
            agreement_start_date = request.POST.get('agreement_start_date') or None
            agreement_end_date = request.POST.get('agreement_end_date') or None
            billing_frequency = request.POST.get('billing_frequency') or None
            charge_frequency = request.POST.get('charge_frequency') or None
            bill_date = request.POST.get('bill_date') or None
            prepaid = 'No'
            free_period_check = False
            free_period_end_date = None
            agreement_doc = request.FILES.get('agreement_document') or None
        else:
            agreement = 'No'
            agreement_start_date = None
            agreement_end_date = None
            billing_frequency = None
            charge_frequency = None
            bill_date = None
            prepaid = request.POST.get('prepaid', 'No').strip()
            free_period_check = request.POST.get('free_period_check') in ['1', 'on', 'true', 'True', True]
            free_period_end_date = request.POST.get('free_period_end_date') or None
            agreement_doc = None

        project = Project.objects.create(
            company_id=request.session.get('company_id', 1),
            project_name=project_name,
            client_name=client_name,
            site_id=int(site_id),
            site_manager=int(request.POST.get('site_manager')) if request.POST.get('site_manager') else None,
            field_staff=staff_list,
            status=status,
            start_date=request.POST.get('start_date') or None,
            end_date=request.POST.get('end_date') or None,
            reporting_frequency=request.POST.get('reporting_frequency', 'Weekly'),
            agreement=agreement,
            agreement_document=agreement_doc,
            agreement_start_date=agreement_start_date,
            agreement_end_date=agreement_end_date,
            billing_frequency=billing_frequency,
            charge_frequency=charge_frequency,
            bill_date=bill_date,
            prepaid=prepaid,
            free_period_check=free_period_check,
            free_period_end_date=free_period_end_date,
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

        # Handle Project Activities & Automatic Instance Generation (Step 3)
        activity_ids = request.POST.getlist('selected_activities[]')
        activities_data = []
        for a_id in activity_ids:
            if a_id.isdigit():
                form_id = request.POST.get(f'activity_form_{a_id}')
                freq = request.POST.get(f'activity_frequency_{a_id}')
                duration = request.POST.get(f'activity_duration_{a_id}', '')
                activities_data.append({
                    'activity_id': int(a_id),
                    'form_id': int(form_id) if form_id and form_id.isdigit() else None,
                    'frequency': freq,
                    'estimated_duration': duration,
                })

        added_by = request.session.get('name') or ('Admin' if request.session.get('is_admin') == 1 else 'Staff')
        ProjectActivityService.sync_project_activities(project, activities_data, user_name=added_by)

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
        project_name = request.POST.get('project_name', '').strip()
        site_id = request.POST.get('site_id')

        if not client_name or not site_id:
            messages.error(request, 'Client name and site are required.')
            return redirect('admin_projects_edit', id=id)

        staff_list = [int(x) for x in request.POST.getlist('field_staff[]') if x.isdigit()]

        project.project_name = project_name
        project.client_name = client_name
        project.site_id = int(site_id)
        project.site_manager = int(request.POST.get('site_manager')) if request.POST.get('site_manager') else None
        project.field_staff = staff_list
        project.status = request.POST.get('status', project.status)
        project.start_date = request.POST.get('start_date') or None
        project.end_date = request.POST.get('end_date') or None
        project.reporting_frequency = request.POST.get('reporting_frequency', project.reporting_frequency)
        
        agreement = request.POST.get('agreement', 'No').strip()
        project.agreement = agreement
        if agreement == 'Yes':
            project.agreement_start_date = request.POST.get('agreement_start_date') or None
            project.agreement_end_date = request.POST.get('agreement_end_date') or None
            project.billing_frequency = request.POST.get('billing_frequency') or None
            project.charge_frequency = request.POST.get('charge_frequency') or None
            project.bill_date = request.POST.get('bill_date') or None
            project.prepaid = 'No'
            project.free_period_check = False
            project.free_period_end_date = None

            # Handle agreement document upload / replace / remove
            if 'agreement_document' in request.FILES and request.FILES['agreement_document']:
                project.agreement_document = request.FILES['agreement_document']
            elif request.POST.get('remove_agreement_document') == '1':
                project.agreement_document = None
        else:
            project.agreement_start_date = None
            project.agreement_end_date = None
            project.billing_frequency = None
            project.charge_frequency = None
            project.bill_date = None
            project.prepaid = request.POST.get('prepaid', 'No').strip()
            project.free_period_check = request.POST.get('free_period_check') in ['1', 'on', 'true', 'True', True]
            project.free_period_end_date = request.POST.get('free_period_end_date') or None
            project.agreement_document = None

        project.notes = request.POST.get('notes', project.notes)
        project.save()

        # Reconcile project activities instances on date changes
        for pa in project.project_activities.filter(status='active'):
            pa.start_date = project.start_date
            pa.end_date = project.end_date
            pa.save(update_fields=['start_date', 'end_date', 'updated_at'])
            ProjectActivityService.generate_instances_for_activity(pa)

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


# ==========================================
# 5. LEADS MANAGEMENT
# ==========================================
@admin_required
def leads_index(request):
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    qs = Lead.objects.all().order_by('-created_at')
    if search:
        qs = qs.filter(client_name__icontains=search) | qs.filter(location__icontains=search)
    if status_filter:
        qs = qs.filter(status=status_filter)

    total_leads = Lead.objects.count()
    new_leads = Lead.objects.filter(status='new').count()
    in_progress_leads = Lead.objects.filter(status__in=['contacted', 'site_visit_scheduled', 'proposal_sent', 'negotiation']).count()
    converted_leads = Lead.objects.filter(status='won').count()
    lost_leads = Lead.objects.filter(status='lost').count()

    return render(request, 'admin/sales/leads.html', {
        'leads': qs,
        'data': {
            'total_leads': total_leads,
            'new_leads': new_leads,
            'in_progress_leads': in_progress_leads,
            'converted_leads': converted_leads,
            'lost_leads': lost_leads,
        },
        'current_search': search,
        'current_status': status_filter,
    })


@admin_required
def lead_create(request):
    employees = Employee.objects.filter(status='active').order_by('name')
    return render(request, 'admin/sales/addlead.html', {
        'employees': employees,
    })


@admin_required
def lead_store(request):
    if request.method == 'POST':
        client_name = request.POST.get('client_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        source = request.POST.get('source', 'Online')
        location = request.POST.get('location', '').strip()
        system_size = request.POST.get('system_size', 5.0)
        value = request.POST.get('value', 0)
        assigned_to = request.POST.get('assigned_to', 'Admin')
        status = request.POST.get('status', 'new')

        if not client_name or not phone:
            messages.error(request, 'Client Name and Phone are required.')
            return redirect('admin_addlead')

        Lead.objects.create(
            company_id=request.session.get('company_id', 1),
            client_name=client_name,
            location=location or None,
            source=source,
            system_size=float(system_size) if system_size else 0.0,
            value=float(value) if value else 0.0,
            assigned_to=assigned_to,
            status=status,
        )
        messages.success(request, 'Lead created successfully.')
        return redirect('admin_leads_index')
    return redirect('admin_addlead')


@admin_required
def lead_report(request):
    from_date = request.GET.get('from', '')
    to_date = request.GET.get('to', '')

    qs = Lead.objects.all().order_by('-created_at')
    if from_date:
        qs = qs.filter(created_at__date__gte=from_date)
    if to_date:
        qs = qs.filter(created_at__date__lte=to_date)

    lead_stages = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('site_visit_scheduled', 'Visit'),
        ('proposal_sent', 'Proposal'),
        ('won', 'Won')
    ]
    funnel_labels = [label for _, label in lead_stages]
    lead_counts = {item['status']: item['cnt'] for item in qs.values('status').annotate(cnt=Count('id'))}
    total_leads = sum(lead_counts.values())
    if total_leads > 0:
        funnel_data = [lead_counts.get(st, 0) for st, _ in lead_stages]
    else:
        funnel_data = [100, 85, 60, 40, 25]

    return render(request, 'admin/sales/leadreport.html', {
        'leads': qs,
        'from_date': from_date,
        'to_date': to_date,
        'funnel_labels': json.dumps(funnel_labels),
        'funnel_data': json.dumps(funnel_data),
    })


@admin_required
def lead_report_excel(request):
    qs = Lead.objects.all().order_by('-created_at')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads Report"

    ws.append(["ID", "Client Name", "Location", "Source", "System Size (kW)", "Value (INR)", "Assigned To", "Status", "Date"])
    for l in qs:
        ws.append([
            l.id,
            l.client_name,
            l.location or '—',
            l.source or '—',
            float(l.system_size),
            float(l.value),
            l.assigned_to or '—',
            l.status.title(),
            l.created_at.strftime('%Y-%m-%d %H:%M') if l.created_at else '—',
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="leads_report.xlsx"'
    wb.save(response)
    return response


# ==========================================
# 6. STAFF MANAGEMENT
# ==========================================
@admin_required
def staff_index(request):
    company_id = request.session.get('company_id', 1)
    designations_map = {d.id: d.designation_name for d in DesignationMaster.objects.all()}
    
    employees = Employee.objects.filter(company_id=company_id).order_by('-id')
    staff_list = []
    active_count = 0
    inactive_count = 0
    for emp in employees:
        is_active = (emp.status == 'active')
        if is_active:
            active_count += 1
        else:
            inactive_count += 1

        role_name = designations_map.get(emp.role, 'Staff') if emp.role else 'Staff'
        staff_list.append({
            'id': emp.id,
            'name': emp.name,
            'role': emp.role,
            'role_name': role_name,
            'email': emp.email,
            'phone': emp.phone,
            'status': emp.status,
            'created_at': emp.created_at,
        })

    designations = DesignationMaster.objects.all().order_by('designation_name')

    return render(request, 'admin/staffmanagement.html', {
        'staffMembers': staff_list,
        'designations': designations,
        'total_staff': len(staff_list),
        'active_staff': active_count,
        'inactive_staff': inactive_count,
        'total_designations': designations.count(),
    })


@admin_required
def staff_store(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        role = request.POST.get('role')
        app_username = request.POST.get('app_username', '').strip()
        app_password = request.POST.get('app_password', '').strip()
        joining_date = request.POST.get('joining_date')
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()

        if not name or not role or not app_username or not app_password:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('admin_staff_index')

        if Employee.objects.filter(app_username=app_username).exists():
            messages.error(request, 'App username already exists.')
            return redirect('admin_staff_index')

        Employee.objects.create(
            company_id=request.session.get('company_id', 1),
            name=name,
            role=int(role) if role and role.isdigit() else None,
            app_username=app_username,
            app_password=make_password(app_password),
            joining_date=joining_date or None,
            email=email or None,
            phone=phone or None,
            status='active',
        )
        messages.success(request, 'Staff member added successfully.')
        return redirect('admin_staff_index')
    return redirect('admin_staff_index')


@admin_required
def staff_update(request, id):
    if request.method == 'POST':
        emp = get_object_or_404(Employee, id=id)
        emp.name = request.POST.get('name', emp.name).strip()
        role = request.POST.get('role')
        if role and role.isdigit():
            emp.role = int(role)
        emp.email = request.POST.get('email', emp.email).strip() or None
        emp.phone = request.POST.get('phone', emp.phone).strip() or None
        emp.status = request.POST.get('status', emp.status)

        new_password = request.POST.get('app_password', '').strip()
        if new_password:
            emp.app_password = make_password(new_password)

        emp.save()
        messages.success(request, 'Staff member updated successfully.')
        return redirect('admin_staff_index')
    return redirect('admin_staff_index')


@admin_required
def staff_destroy(request, id):
    if request.method == 'POST':
        emp = get_object_or_404(Employee, id=id)
        emp.delete()
        messages.success(request, 'Staff member removed successfully.')
        return redirect('admin_staff_index')
    return redirect('admin_staff_index')


# ==========================================
# 6. PROJECT ACTIVITY MANAGEMENT
# ==========================================
@admin_required
def project_activities_index(request):
    """
    Project Activity Management screen: displays project-specific activities
    and their generated instances, supporting:
    - Search & Filter bar: Search input, Project, Activity, Frequency, Status, Filter button, Reset button
    - Frequency filter: Display activity occurrences according to their frequency (Daily, Weekly, Monthly, Quarterly, Yearly)
    - Ascending sort by scheduled_date (earliest first), secondary by id
    - Server-side pagination (20 per page)
    """
    project_id = request.GET.get('project', '').strip()
    activity_id = request.GET.get('activity', '').strip()
    employee_id = request.GET.get('employee', '').strip()
    frequency = request.GET.get('frequency', '').strip()
    status = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()

    qs = ProjectActivityInstance.objects.select_related(
        'project',
        'activity',
        'project_activity',
        'project_activity__form',
        'assigned_employee',
        'submitted_by'
    ).prefetch_related('photos', 'issues').all()

    # Search and Filter criteria
    if project_id and project_id.isdigit():
        qs = qs.filter(project_id=int(project_id))
    if activity_id and activity_id.isdigit():
        qs = qs.filter(activity_id=int(activity_id))
    if employee_id and employee_id.isdigit():
        qs = qs.filter(assigned_employee_id=int(employee_id))
    if frequency:
        # Match frequency on instance, parent project activity, or activity master
        qs = qs.filter(
            Q(frequency__iexact=frequency) |
            Q(project_activity__frequency__iexact=frequency) |
            Q(activity__default_frequency__iexact=frequency)
        )
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            Q(activity__activity_title__icontains=search) |
            Q(project__client_name__icontains=search) |
            Q(project__project_name__icontains=search) |
            Q(assigned_employee__name__icontains=search)
        )

    # Sort in ascending order by scheduled_date (earliest first), secondary by id
    qs = qs.order_by('scheduled_date', 'id')

    # Server-side pagination (20 per page)
    paginator = Paginator(qs, 20)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Summary metrics
    all_instances = ProjectActivityInstance.objects.all()
    metrics = {
        'total_instances': all_instances.count(),
        'pending': all_instances.filter(status='Pending').count(),
        'in_progress': all_instances.filter(status='In Progress').count(),
        'completed': all_instances.filter(status='Completed').count(),
        'exceptions': all_instances.filter(status__in=['Unable to Complete', 'Exception Reported']).count(),
    }

    projects_list = Project.objects.order_by('project_name', 'client_name')
    activities_list = ActivityMaster.objects.order_by('activity_title')
    employees_list = Employee.objects.filter(status='active').order_by('name')
    frequency_choices = [f[0] for f in ActivityMaster.FREQUENCY_CHOICES]
    status_choices = [s[0] for s in ProjectActivityInstance.STATUS_CHOICES]

    return render(request, 'admin/operation/project_activities.html', {
        'page_obj': page_obj,
        'instances': page_obj.object_list,
        'metrics': metrics,
        'projects': projects_list,
        'activities': activities_list,
        'employees': employees_list,
        'frequencyChoices': frequency_choices,
        'statusChoices': status_choices,
        'filters': {
            'project': project_id,
            'activity': activity_id,
            'employee': employee_id,
            'frequency': frequency,
            'status': status,
            'search': search,
        }
    })


@admin_required
def project_activity_instance_detail(request, instance_id):
    """
    Returns full modal detail HTML or JSON for an individual activity instance:
    Activity information, project info, attached form, submitted form answers,
    before/after photos, employee remarks, and issue/exception details.
    """
    instance = get_object_or_404(
        ProjectActivityInstance.objects.select_related(
            'project',
            'activity',
            'project_activity',
            'project_activity__form',
            'assigned_employee',
            'submitted_by',
            'form_submission'
        ).prefetch_related('photos', 'issues'),
        id=instance_id
    )

    before_photos = [p for p in instance.photos.all() if p.photo_stage == 'Before']
    after_photos = [p for p in instance.photos.all() if p.photo_stage == 'After']
    intermediate_photos = [p for p in instance.photos.all() if p.photo_stage == 'Intermediate']
    issues = list(instance.issues.all().order_by('-created_at'))

    attached_form = instance.project_activity.form

    return render(request, 'admin/operation/project_activity_detail_modal.html', {
        'instance': instance,
        'beforePhotos': before_photos,
        'afterPhotos': after_photos,
        'intermediatePhotos': intermediate_photos,
        'issues': issues,
        'attachedForm': attached_form,
    })


@admin_required
def project_activity_review_issue(request, instance_id):
    """
    Allows Admin to review and update status/remarks on reported activity exceptions.
    """
    instance = get_object_or_404(ProjectActivityInstance, id=instance_id)
    if request.method == 'POST':
        issue_id = request.POST.get('issue_id')
        new_status = request.POST.get('status', 'Under Review')
        admin_remarks = request.POST.get('admin_remarks', '').strip()

        issue = None
        if issue_id and issue_id.isdigit():
            issue = ProjectActivityIssue.objects.filter(id=int(issue_id), instance=instance).first()

        if issue:
            issue.status = new_status
            issue.admin_remarks = admin_remarks
            issue.action_by = request.session.get('name') or 'Admin'
            issue.action_at = timezone.now()
            issue.save()

            if new_status == 'Resolved':
                instance.status = 'Pending'
                instance.save(update_fields=['status', 'updated_at'])
            elif new_status == 'Under Review':
                instance.status = 'Under Review'
                instance.save(update_fields=['status', 'updated_at'])

            messages.success(request, f'Issue #{issue.id} updated successfully.')
        return redirect('admin_project_activities_index')
    return redirect('admin_project_activities_index')

