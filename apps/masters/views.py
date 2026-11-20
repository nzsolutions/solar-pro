from apps.dynamic_forms.models import DynamicForm
from django.db.models import Q
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from apps.authentication.decorators import admin_required
from apps.masters.models import (
    DepartmentMaster, DesignationMaster, DocumentTypeMaster,
    SiteMaster, AttendanceMaster, SMTPConfiguration, AccessControl, ActivityMaster,
    ActivityFormConfiguration, ActivityFormField, ActivityFormFieldOption,
    ActivityFormPhotoSetting, ActivityFormValidationRule,
    LeaveRequest, ActivitySchedule, ActivityTask
)
from apps.employees.models import Employee
from django.utils import timezone
from apps.masters.form_builder_service import ActivityFormService
from apps.masters.schedule_service import ActivityScheduleService
from apps.employees.models import Employee
from apps.operations.models import Project

# ==========================================
# 1. DEPARTMENT MASTER
# ==========================================
@admin_required
def departments_index(request):
    search = request.GET.get('search', '').strip()
    qs = DepartmentMaster.objects.all()
    if search:
        qs = qs.filter(department_name__icontains=search)
    departments = qs.order_by('-id')
    return render(request, 'admin/master/department.html', {'departments': departments})


@admin_required
def department_store(request):
    if request.method == 'POST':
        name = request.POST.get('department_name', '').strip()
        if not name:
            messages.error(request, 'Department name is required.')
            return redirect('admin_departments_index')

        if DepartmentMaster.objects.filter(department_name__iexact=name).exists():
            messages.error(request, 'This department name already exists.')
            return redirect('admin_departments_index')

        DepartmentMaster.objects.create(
            department_name=name,
            company_id=request.session.get('company_id', 1),
            added_by='Admin'
        )
        messages.success(request, 'Department added successfully.')
    return redirect('admin_departments_index')


@admin_required
def department_update(request, id):
    department = get_object_or_404(DepartmentMaster, id=id)
    if request.method == 'POST':
        name = request.POST.get('department_name', '').strip()
        if not name:
            messages.error(request, 'Department name is required.')
            return redirect('admin_departments_index')

        if DepartmentMaster.objects.filter(department_name__iexact=name).exclude(id=id).exists():
            messages.error(request, 'This department name already exists.')
            return redirect('admin_departments_index')

        department.department_name = name
        department.save()
        messages.success(request, 'Department updated successfully.')
    return redirect('admin_departments_index')


@admin_required
def department_destroy(request, id):
    department = get_object_or_404(DepartmentMaster, id=id)
    department.delete()
    messages.success(request, 'Department deleted successfully.')
    return redirect('admin_departments_index')


# ==========================================
# 2. DESIGNATION MASTER
# ==========================================
@admin_required
def designations_index(request):
    search = request.GET.get('search', '').strip()
    qs = DesignationMaster.objects.all()
    if search:
        qs = qs.filter(designation_name__icontains=search)

    departments_map = {d.id: d.department_name for d in DepartmentMaster.objects.all()}
    designations = []
    for d in qs.order_by('-id'):
        designations.append({
            'id': d.id,
            'department_id': d.department_id,
            'department_name': departments_map.get(d.department_id, '—'),
            'designation_name': d.designation_name,
            'added_by': d.added_by,
            'created_at': d.created_at,
        })

    departments = DepartmentMaster.objects.order_by('department_name')
    return render(request, 'admin/master/designation.html', {
        'designations': designations,
        'departments': departments,
    })


@admin_required
def designation_store(request):
    if request.method == 'POST':
        department_id = request.POST.get('department_id')
        name = request.POST.get('designation_name', '').strip()

        if not department_id or not name:
            messages.error(request, 'Department and designation name are required.')
            return redirect('admin_designations_index')

        if DesignationMaster.objects.filter(department_id=department_id, designation_name__iexact=name).exists():
            messages.error(request, 'This designation already exists under the selected department.')
            return redirect('admin_designations_index')

        DesignationMaster.objects.create(
            department_id=int(department_id),
            designation_name=name,
            company_id=request.session.get('company_id', 1),
            added_by='Admin'
        )
        messages.success(request, 'Designation added successfully.')
    return redirect('admin_designations_index')


@admin_required
def designation_update(request, id):
    designation = get_object_or_404(DesignationMaster, id=id)
    if request.method == 'POST':
        department_id = request.POST.get('department_id')
        name = request.POST.get('designation_name', '').strip()

        if not department_id or not name:
            messages.error(request, 'Department and designation name are required.')
            return redirect('admin_designations_index')

        if DesignationMaster.objects.filter(department_id=department_id, designation_name__iexact=name).exclude(id=id).exists():
            messages.error(request, 'This designation already exists under the selected department.')
            return redirect('admin_designations_index')

        designation.department_id = int(department_id)
        designation.designation_name = name
        designation.save()
        messages.success(request, 'Designation updated successfully.')
    return redirect('admin_designations_index')


@admin_required
def designation_destroy(request, id):
    designation = get_object_or_404(DesignationMaster, id=id)
    designation.delete()
    messages.success(request, 'Designation deleted successfully.')
    return redirect('admin_designations_index')


# ==========================================
# 3. DOCUMENT TYPE MASTER
# ==========================================
@admin_required
def document_types_index(request):
    company_id = request.session.get('company_id', 1)
    doc_types = DocumentTypeMaster.objects.filter(company_id=company_id).order_by('-id')
    return render(request, 'admin/master/documenttypemaster.html', {'doc_types': doc_types})


@admin_required
def document_type_store(request):
    if request.method == 'POST':
        name = request.POST.get('type_name', '').strip()
        status = request.POST.get('status', 'active')
        if not name:
            messages.error(request, 'Document type name is required.')
            return redirect('admin_document_types_index')

        DocumentTypeMaster.objects.create(
            type_name=name,
            status=status,
            company_id=request.session.get('company_id', 1)
        )
        messages.success(request, 'Document type added successfully.')
    return redirect('admin_document_types_index')


@admin_required
def document_type_update(request, id):
    doc_type = get_object_or_404(DocumentTypeMaster, id=id)
    if request.method == 'POST':
        name = request.POST.get('type_name', '').strip()
        status = request.POST.get('status', 'active')
        if name:
            doc_type.type_name = name
            doc_type.status = status
            doc_type.save()
            messages.success(request, 'Document type updated successfully.')
    return redirect('admin_document_types_index')


@admin_required
def document_type_destroy(request, id):
    doc_type = get_object_or_404(DocumentTypeMaster, id=id)
    doc_type.delete()
    messages.success(request, 'Document type deleted successfully.')
    return redirect('admin_document_types_index')


# ==========================================
# 4. SITE MASTER
# ==========================================
@admin_required
def sites_index(request):
    company_id = request.session.get('company_id', 1)
    sites = SiteMaster.objects.filter(company_id=company_id).order_by('-id')
    return render(request, 'admin/master/sitemaster.html', {'sites': sites})


@admin_required
def site_store(request):
    if request.method == 'POST':
        SiteMaster.objects.create(
            company_id=request.session.get('company_id', 1),
            site_name=request.POST.get('site_name', '').strip(),
            site_address=request.POST.get('site_address', '').strip(),
            longitude=request.POST.get('longitude') or 0.0,
            latitude=request.POST.get('latitude') or 0.0,
            radius=request.POST.get('radius') or 500.00,
            contact_number=request.POST.get('contact_number', '').strip(),
        )
        messages.success(request, 'Site added successfully.')
    return redirect('admin_sites_index')


@admin_required
def site_update(request, id):
    site = get_object_or_404(SiteMaster, id=id)
    if request.method == 'POST':
        site.site_name = request.POST.get('site_name', '').strip()
        site.site_address = request.POST.get('site_address', '').strip()
        site.longitude = request.POST.get('longitude') or 0.0
        site.latitude = request.POST.get('latitude') or 0.0
        site.radius = request.POST.get('radius') or 500.00
        site.contact_number = request.POST.get('contact_number', '').strip()
        site.save()
        messages.success(request, 'Site updated successfully.')
    return redirect('admin_sites_index')


@admin_required
def site_destroy(request, id):
    site = get_object_or_404(SiteMaster, id=id)
    site.delete()
    messages.success(request, 'Site deleted successfully.')
    return redirect('admin_sites_index')


# ==========================================
# 5. ATTENDANCE MASTER
# ==========================================
@admin_required
def attendance_master_create(request):
    attendance_masters = AttendanceMaster.objects.order_by('-id')
    return render(request, 'admin/master/attendancemaster.html', {'attendance_masters': attendance_masters})


@admin_required
def attendance_master_store(request):
    if request.method == 'POST':
        AttendanceMaster.objects.create(
            company_id=request.session.get('company_id', 1),
            working_hours=request.POST.get('working_hours', '9'),
            latitude=request.POST.get('latitude', 0.0),
            longitude=request.POST.get('longitude', 0.0),
        )
        messages.success(request, 'Attendance master entry was added successfully.')
    return redirect('admin_attendance_master_create')


# ==========================================
# 6. SMTP CONFIGURATION
# ==========================================
@admin_required
def smtp_index(request):
    company_id = request.session.get('company_id', 1)
    configs = SMTPConfiguration.objects.filter(company_id=company_id).order_by('-id')
    return render(request, 'admin/master/smtpconfiguration.html', {'configs': configs})


@admin_required
def smtp_store(request):
    if request.method == 'POST':
        SMTPConfiguration.objects.create(
            company_id=request.session.get('company_id', 1),
            config_name=request.POST.get('config_name', 'Primary SMTP'),
            smtp_host=request.POST.get('smtp_host', '').strip(),
            smtp_port=int(request.POST.get('smtp_port') or 587),
            smtp_user=request.POST.get('smtp_user', '').strip(),
            smtp_pass=request.POST.get('smtp_pass', '').strip(),
            smtp_crypto=request.POST.get('smtp_crypto', 'tls'),
            from_email=request.POST.get('from_email', '').strip(),
            from_name=request.POST.get('from_name', 'SolarPro'),
        )
        messages.success(request, 'SMTP Configuration saved.')
    return redirect('admin_smtp_index')


@admin_required
def smtp_edit(request, id):
    config = get_object_or_404(SMTPConfiguration, id=id)
    return render(request, 'admin/master/editsmtpconfig.html', {'config': config})


@admin_required
def smtp_update(request, id):
    config = get_object_or_404(SMTPConfiguration, id=id)
    if request.method == 'POST':
        config.config_name = request.POST.get('config_name', config.config_name)
        config.smtp_host = request.POST.get('smtp_host', config.smtp_host)
        config.smtp_port = int(request.POST.get('smtp_port') or config.smtp_port)
        config.smtp_user = request.POST.get('smtp_user', config.smtp_user)
        if request.POST.get('smtp_pass'):
            config.smtp_pass = request.POST.get('smtp_pass')
        config.smtp_crypto = request.POST.get('smtp_crypto', config.smtp_crypto)
        config.from_email = request.POST.get('from_email', config.from_email)
        config.from_name = request.POST.get('from_name', config.from_name)
        config.save()
        messages.success(request, 'SMTP Configuration updated successfully.')
    return redirect('admin_smtp_index')


@admin_required
def smtp_destroy(request, id):
    config = get_object_or_404(SMTPConfiguration, id=id)
    config.delete()
    messages.success(request, 'SMTP Configuration deleted successfully.')
    return redirect('admin_smtp_index')


@admin_required
def smtp_test_mail(request):
    if request.method == 'POST':
        test_email = request.POST.get('test_email')
        smtp_id = request.POST.get('smtp_id')

        config = SMTPConfiguration.objects.filter(id=smtp_id).first() if smtp_id else SMTPConfiguration.objects.first()
        if not config:
            return JsonResponse({'success': False, 'message': 'No SMTP config found.'})

        try:
            msg = MIMEMultipart()
            msg['From'] = f"{config.from_name} <{config.from_email}>"
            msg['To'] = test_email
            msg['Subject'] = "SolarPro SMTP Test Mail"
            msg.attach(MIMEText("This is a test email verifying that your SolarPro SMTP configuration is operational.", 'plain'))

            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)
            if config.smtp_crypto == 'tls':
                server.starttls()
            server.login(config.smtp_user, config.smtp_pass)
            server.send_message(msg)
            server.quit()
            return JsonResponse({'success': True, 'message': f'Test mail successfully sent to {test_email}!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'SMTP Error: {str(e)}'})

    return JsonResponse({'success': False, 'message': 'Invalid request'})


# ==========================================
# 7. ACCESS CONTROL (RBAC)
# ==========================================
MODULE_TREE = {
    'Overview': {
        'common-dashboard': 'Dashboard',
    },
    'Master': {
        'department-master': 'Department Master',
        'designation-master': 'Designation Master',
        'employee-master': 'Employee Master',
        'access-control': 'Access Control',
        'smtp-config': 'SMTP Config',
        'expense-category-master': 'Expense Category Master',
        'stock-category-master': 'Stock Category Master',
        'site-master': 'Site Master',
        'document-type-master': 'Document Type Master',
        'attendance-master': 'Attendance Master',
        'activity-master': 'Activity Master',
        'leave-management': 'Leave Management',
        'activity-scheduling': 'Activity Scheduling',
    },
    'Reports': {
        'project-reports': 'Project Reports',
        'maintenance-reports': 'Maintenance Reports',
        'attendance-report': 'Attendance Report',
        'stock-report': 'Stock Report',
        'expense-report': 'Expense Report',
    },
    'Operations': {
        'all-projects': 'All Projects',
        'project-activities': 'Project Activities',
        'add-project': 'Add Project',
        'maintenance-charts': 'Maintenance Charts',
    },
    'Expenses': {
        'employee-expenses': 'Employee Expenses',
    },
    'Forms': {
        'add-form': 'Add Form',
        'all-forms': 'All Forms',
        'form-submissions': 'Form Submissions',
        'dashboard-config': 'Dashboard Config',
        'dynamic-dashboard': 'Dynamic Dashboard',
    },
    'Stock': {
        'stock-dashboard': 'Stock Dashboard',
        'opening-stock': 'Opening Stock',
        'assign-stock': 'Assign Stock',
    },
}


@admin_required
def access_control_index(request):
    roles = DesignationMaster.objects.values('id', 'designation_name').order_by('designation_name')
    return render(request, 'admin/master/accesscontrol.html', {
        'roles': [{'id': r['id'], 'name': r['designation_name']} for r in roles],
        'modules': MODULE_TREE,
    })


@admin_required
def access_control_permissions(request, role_id):
    try:
        keys = list(AccessControl.objects.filter(role_id=role_id).values_list('menu_key', flat=True))
        return JsonResponse({'success': True, 'permissions': keys})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@admin_required
def access_control_save(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.body else request.POST
            role_id = data.get('role_id')
            permissions = data.get('permissions', [])

            if not role_id:
                return JsonResponse({'success': False, 'message': 'Role ID is required'}, status=400)

            AccessControl.objects.filter(role_id=role_id).delete()
            objs = [AccessControl(role_id=role_id, menu_key=key) for key in set(permissions)]
            AccessControl.objects.bulk_create(objs)

            return JsonResponse({'success': True, 'message': 'Permissions updated successfully.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)



# ==========================================
# 8. ACTIVITY MASTER
# ==========================================
@admin_required
def activities_index(request):
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    category_filter = request.GET.get('category', '').strip()

    qs = ActivityMaster.objects.select_related('form').all()
    if search:
        qs = qs.filter(
            Q(activity_title__icontains=search) |
            Q(description__icontains=search) |
            Q(activity_category__icontains=search)
        )
    if status_filter in ['active', 'inactive']:
        qs = qs.filter(status=status_filter)
    if category_filter:
        qs = qs.filter(activity_category=category_filter)

    activities = qs.order_by('-id')
    forms = DynamicForm.objects.filter(is_active=1).order_by('form_name')

    return render(request, 'admin/master/activitymaster.html', {
        'activities': activities,
        'forms': forms,
        'categories': [c[0] for c in ActivityMaster.CATEGORY_CHOICES],
        'frequencies': [f[0] for f in ActivityMaster.FREQUENCY_CHOICES],
        'search': search,
        'status_filter': status_filter,
        'category_filter': category_filter,
    })


@admin_required
def activity_store(request):
    if request.method == 'POST':
        title = request.POST.get('activity_title', '').strip()
        category = request.POST.get('activity_category', '').strip() or 'Maintenance'
        description = request.POST.get('description', '').strip()
        default_frequency = request.POST.get('default_frequency', '').strip() or 'Monthly'
        estimated_duration = request.POST.get('estimated_duration', '').strip()
        form_id = request.POST.get('form_id', '').strip()
        photo_required = True if request.POST.get('photo_required') in ['1', 'true', 'on'] else False
        status = request.POST.get('status', 'active').strip() or 'active'

        if not title:
            messages.error(request, 'Activity Title is required.')
            return redirect('admin_activities_index')

        if ActivityMaster.objects.filter(activity_title__iexact=title).exists():
            messages.error(request, f'An activity with the title "{title}" already exists.')
            return redirect('admin_activities_index')

        form_obj = None
        if form_id and form_id.isdigit():
            form_obj = DynamicForm.objects.filter(id=int(form_id)).first()

        added_by = request.session.get('name') or ('Admin' if request.session.get('is_admin') == 1 else 'Staff')

        ActivityMaster.objects.create(
            activity_title=title,
            activity_category=category,
            description=description,
            default_frequency=default_frequency,
            estimated_duration=estimated_duration,
            form=form_obj,
            photo_required=photo_required,
            status=status,
            company_id=request.session.get('company_id', 1),
            added_by=added_by
        )
        messages.success(request, f'Activity "{title}" created successfully.')
    return redirect('admin_activities_index')


@admin_required
def activity_update(request, id):
    activity = get_object_or_404(ActivityMaster, id=id)
    if request.method == 'POST':
        title = request.POST.get('activity_title', '').strip()
        category = request.POST.get('activity_category', '').strip() or 'Maintenance'
        description = request.POST.get('description', '').strip()
        default_frequency = request.POST.get('default_frequency', '').strip() or 'Monthly'
        estimated_duration = request.POST.get('estimated_duration', '').strip()
        form_id = request.POST.get('form_id', '').strip()
        photo_required = True if request.POST.get('photo_required') in ['1', 'true', 'on'] else False
        status = request.POST.get('status', activity.status).strip() or activity.status

        if not title:
            messages.error(request, 'Activity Title is required.')
            return redirect('admin_activities_index')

        if ActivityMaster.objects.filter(activity_title__iexact=title).exclude(id=activity.id).exists():
            messages.error(request, f'Another activity with the title "{title}" already exists.')
            return redirect('admin_activities_index')

        form_obj = None
        if form_id and form_id.isdigit():
            form_obj = DynamicForm.objects.filter(id=int(form_id)).first()

        activity.activity_title = title
        activity.activity_category = category
        activity.description = description
        activity.default_frequency = default_frequency
        activity.estimated_duration = estimated_duration
        activity.form = form_obj
        activity.photo_required = photo_required
        activity.status = status
        activity.save()

        messages.success(request, f'Activity "{title}" updated successfully.')
    return redirect('admin_activities_index')


@admin_required
def activity_toggle_status(request, id):
    activity = get_object_or_404(ActivityMaster, id=id)
    if request.method == 'POST':
        new_status = 'inactive' if activity.status == 'active' else 'active'
        activity.status = new_status
        activity.save()
        action_verb = 'activated' if new_status == 'active' else 'deactivated'
        messages.success(request, f'Activity "{activity.activity_title}" has been {action_verb}.')
    return redirect('admin_activities_index')


# ==========================================
# 9. DYNAMIC ACTIVITY FORM BUILDER
# ==========================================
@admin_required
def activity_form_builder(request, activity_id):
    """
    Renders the Dynamic Form Builder for a specific Activity Master record.
    Allows configuring checklist fields, validation rules, expected values,
    business exception rules, and photo evidence requirements.
    """
    activity = get_object_or_404(ActivityMaster, id=activity_id)
    form_config = ActivityFormService.get_or_create_form_config(activity)
    form_dict = ActivityFormService.form_to_dict(form_config)
    prebuilt_templates = ActivityFormService.get_prebuilt_templates()

    field_type_choices = [
        {'type': 'short_text', 'label': 'Short Text', 'icon': 'bi-input-cursor-text', 'desc': 'Single line text input'},
        {'type': 'long_text', 'label': 'Long Text', 'icon': 'bi-textarea-t', 'desc': 'Multi-line notes and remarks'},
        {'type': 'number', 'label': 'Number', 'icon': 'bi-123', 'desc': 'Numeric reading with min/max, unit & tolerance'},
        {'type': 'yes_no', 'label': 'Yes / No', 'icon': 'bi-toggles', 'desc': 'Binary confirmation with expected state'},
        {'type': 'dropdown', 'label': 'Dropdown', 'icon': 'bi-menu-button-wide', 'desc': 'Single select option list'},
        {'type': 'multiple_choice', 'label': 'Multiple Choice', 'icon': 'bi-check2-square', 'desc': 'Multi-select options'},
        {'type': 'date', 'label': 'Date', 'icon': 'bi-calendar-event', 'desc': 'Calendar date selector'},
        {'type': 'time', 'label': 'Time', 'icon': 'bi-clock', 'desc': 'Time picker'},
        {'type': 'photo_capture', 'label': 'Photo Evidence', 'icon': 'bi-camera', 'desc': 'Camera-only verification photo'},
    ]

    all_activities = ActivityMaster.objects.filter(company_id=activity.company_id).exclude(id=activity.id).order_by('activity_title')

    return render(request, 'admin/master/activity_form_builder.html', {
        'activity': activity,
        'form_config': form_config,
        'form_json': json.dumps(form_dict),
        'prebuilt_templates_json': json.dumps(prebuilt_templates),
        'field_type_choices': field_type_choices,
        'all_activities': all_activities,
    })


@admin_required
def activity_form_builder_standalone(request):
    """
    Redirects to the first available activity or shows an activity selection screen.
    """
    first_activity = ActivityMaster.objects.order_by('id').first()
    if first_activity:
        return redirect('admin_activity_form_builder', activity_id=first_activity.id)
    messages.warning(request, 'Please create an Activity in Activity Master first.')
    return redirect('admin_activities_index')


@admin_required
def activity_form_get_json(request, activity_id):
    """
    API endpoint returning the structured form JSON for an activity.
    """
    activity = get_object_or_404(ActivityMaster, id=activity_id)
    form_config = ActivityFormService.get_or_create_form_config(activity)
    form_dict = ActivityFormService.form_to_dict(form_config)
    return JsonResponse({
        'success': True,
        'activity_id': activity.id,
        'activity_title': activity.activity_title,
        'form_data': form_dict
    })


@admin_required
def activity_form_builder_save(request, activity_id):
    """
    Saves the form configuration for an activity.
    Accepts application/json or POST body payload.
    """
    activity = get_object_or_404(ActivityMaster, id=activity_id)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST method required.'}, status=405)

    try:
        if request.content_type == 'application/json':
            payload = json.loads(request.body.decode('utf-8'))
        else:
            raw_payload = request.POST.get('form_payload', '{}')
            payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload

        form_config = ActivityFormService.save_form_from_dict(activity, payload)
        messages.success(request, f'Form configuration for "{activity.activity_title}" saved successfully.')
        return JsonResponse({
            'success': True,
            'message': f'Form configuration for "{activity.activity_title}" saved successfully.',
            'form_config_id': form_config.id,
            'fields_count': form_config.fields.count()
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error saving form configuration: {str(e)}'
        }, status=400)


@admin_required
def activity_form_evaluate_preview(request):
    """
    Interactive test evaluation endpoint for the Form Builder preview mode.
    Tests user input against both standard validation and business exception rules,
    as well as mandatory photo evidence.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST method required.'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        fields_config = data.get('fields', [])
        submitted_values = data.get('values', {})
        photo_settings = data.get('photo_settings')
        photo_data = data.get('photo_data')
        result = ActivityFormService.evaluate_submission(
            fields_config,
            submitted_values,
            photo_settings=photo_settings,
            photo_data=photo_data
        )
        return JsonResponse({
            'success': True,
            **result
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Evaluation error: {str(e)}'
        }, status=400)


@admin_required
def activity_form_submit_test(request, activity_id):
    """
    Submits a real form test from the Form Builder's Live Mobile Preview.
    Uploads and saves all Before & After photos, field photos, GPS coordinates,
    timestamps, and field data into Django file storage and MySQL database.
    """
    activity = get_object_or_404(ActivityMaster, id=activity_id)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST method required.'}, status=405)

    try:
        from apps.employees.models import Employee
        from apps.operations.models import Project

        # 1. Parse payload (JSON or multipart form-data)
        if request.content_type and 'application/json' in request.content_type:
            payload = json.loads(request.body.decode('utf-8'))
            field_answers = payload.get('values', {})
            photo_data = payload.get('photo_data', {})
            before_photos = photo_data.get('before_photos', [])
            after_photos = photo_data.get('after_photos', [])
            field_photos = photo_data.get('field_photos', {})
            gps_coordinates = payload.get('gps_coordinates', {})
            timestamps = payload.get('timestamps', {})
            inspection_details = payload.get('inspection_details', {})
        else:
            raw_payload = request.POST.get('payload', '{}')
            payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
            field_answers = payload.get('values', {})
            photo_data = payload.get('photo_data', {})
            before_photos = photo_data.get('before_photos', [])
            after_photos = photo_data.get('after_photos', [])
            field_photos = photo_data.get('field_photos', {})
            gps_coordinates = payload.get('gps_coordinates', {})
            timestamps = payload.get('timestamps', {})
            inspection_details = payload.get('inspection_details', {})

            # Also pull files from request.FILES if present
            if 'before_photos' in request.FILES:
                before_photos.extend(request.FILES.getlist('before_photos'))
            if 'after_photos' in request.FILES:
                after_photos.extend(request.FILES.getlist('after_photos'))
            for key in request.FILES:
                if key.startswith('field_photo_') or key.startswith('field_'):
                    f_id = key.split('_')[-1]
                    field_photos.setdefault(f_id, []).extend(request.FILES.getlist(key))

        # 2. Check form config & photo settings
        form_config = ActivityFormService.get_or_create_form_config(activity)
        photo_setting = getattr(form_config, 'photo_settings', None)

        # 3. Mandatory photo enforcement
        if photo_setting and photo_setting.enable_photo_capture:
            if photo_setting.before_photo_required and not before_photos:
                return JsonResponse({
                    'success': False,
                    'message': 'Before Maintenance photo is required. Please capture or upload evidence before maintenance.',
                    'errors': {'before_photos': 'Before Maintenance photo is mandatory.'}
                }, status=422)

            if photo_setting.after_photo_required and not after_photos:
                return JsonResponse({
                    'success': False,
                    'message': 'After Maintenance photo is required. Please capture or upload evidence after maintenance.',
                    'errors': {'after_photos': 'After Maintenance photo is mandatory.'}
                }, status=422)

        # 4. Resolve Employee and Project
        admin_emp = Employee.objects.filter(company_id=activity.company_id).first()
        emp_id = admin_emp.id if admin_emp else 1
        proj = Project.objects.filter(company_id=activity.company_id).first()
        project_id = proj.id if proj else None

        # 5. Ensure DynamicForm exists and is updated for this activity
        dynamic_form = activity.form
        if not dynamic_form:
            dynamic_form = DynamicForm.objects.create(
                company_id=activity.company_id,
                form_name=form_config.form_title,
                description=form_config.description,
                form_schema=ActivityFormService.build_dynamic_form_schema(form_config),
                is_active=1
            )
            activity.form = dynamic_form
            activity.save(update_fields=['form'])
        else:
            dynamic_form.form_name = form_config.form_title
            dynamic_form.description = form_config.description
            dynamic_form.form_schema = ActivityFormService.build_dynamic_form_schema(form_config)
            dynamic_form.save()

        # 6. Save Form Submission with all photos, GPS, and timestamps
        submission = ActivityFormService.save_form_submission(
            form_id=dynamic_form.id,
            emp_id=emp_id,
            project_id=project_id,
            field_answers=field_answers,
            before_photos=before_photos,
            after_photos=after_photos,
            field_photos=field_photos,
            gps_coordinates=gps_coordinates,
            timestamps=timestamps,
            inspection_details=inspection_details
        )

        return JsonResponse({
            'success': True,
            'message': f'Form submission #{submission.id} created successfully with photo evidence!',
            'submission_id': submission.id,
            'view_url': f'/admin/form-submissions/{submission.id}/edit'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Submission failed: {str(e)}'
        }, status=400)


# ==============================================================================
# 9. ACTIVITY SCHEDULING & AUTOMATIC TASK GENERATION
# ==============================================================================

def _parse_date(val):
    if not val:
        return None
    import datetime
    if isinstance(val, datetime.date) and not isinstance(val, datetime.datetime):
        return val
    if isinstance(val, datetime.datetime):
        return val.date()
    try:
        val_clean = str(val).strip().split('T')[0].split(' ')[0]
        return datetime.date.fromisoformat(val_clean)
    except Exception:
        return None


@admin_required
def activity_schedules_index(request):
    """
    Main listing, calendar, and task management dashboard for Activity Scheduling.
    Supports filtering by search query, status, priority, frequency, employee, and project.
    """
    company_id = request.session.get('company_id', 1)
    
    # Query parameters
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    priority_filter = request.GET.get('priority', '').strip()
    freq_filter = request.GET.get('frequency', '').strip()
    emp_filter = request.GET.get('employee_id', '').strip()
    proj_filter = request.GET.get('project_id', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    active_tab = request.GET.get('tab', 'schedules').strip()

    # Base querysets
    schedules_qs = ActivitySchedule.objects.filter(
        company_id=company_id
    ).select_related('activity', 'project', 'assigned_to').order_by('-id')

    tasks_qs = ActivityTask.objects.filter(
        company_id=company_id
    ).select_related('schedule', 'activity', 'project', 'assigned_to').order_by('-task_date', '-id')

    # Apply filters to Schedules
    if search:
        schedules_qs = schedules_qs.filter(
            Q(title__icontains=search) |
            Q(schedule_code__icontains=search) |
            Q(activity__activity_title__icontains=search) |
            Q(project__project_name__icontains=search) |
            Q(assigned_to__name__icontains=search)
        )
        tasks_qs = tasks_qs.filter(
            Q(task_title__icontains=search) |
            Q(task_code__icontains=search) |
            Q(activity__activity_title__icontains=search) |
            Q(project__project_name__icontains=search) |
            Q(assigned_to__name__icontains=search)
        )

    if status_filter:
        schedules_qs = schedules_qs.filter(status=status_filter)
        tasks_qs = tasks_qs.filter(status=status_filter)

    if priority_filter:
        schedules_qs = schedules_qs.filter(priority=priority_filter)
        tasks_qs = tasks_qs.filter(priority=priority_filter)

    if freq_filter:
        schedules_qs = schedules_qs.filter(recurring_type=freq_filter)

    if emp_filter and emp_filter.isdigit():
        schedules_qs = schedules_qs.filter(assigned_to_id=int(emp_filter))
        tasks_qs = tasks_qs.filter(assigned_to_id=int(emp_filter))

    if proj_filter and proj_filter.isdigit():
        schedules_qs = schedules_qs.filter(project_id=int(proj_filter))
        tasks_qs = tasks_qs.filter(project_id=int(proj_filter))

    if date_from:
        schedules_qs = schedules_qs.filter(start_date__gte=date_from)
        tasks_qs = tasks_qs.filter(task_date__gte=date_from)

    if date_to:
        schedules_qs = schedules_qs.filter(start_date__lte=date_to)
        tasks_qs = tasks_qs.filter(task_date__lte=date_to)

    # Calculate KPIs using service
    kpis = ActivityScheduleService.get_kpis(company_id=company_id)

    # Master options for dropdowns & modals
    activities = ActivityMaster.objects.filter(
        company_id=company_id, status='active'
    ).order_by('activity_title')
    projects = Project.objects.filter(company_id=company_id).order_by('project_name')
    employees = Employee.objects.filter(company_id=company_id, status='active').order_by('name')

    context = {
        'schedules': schedules_qs,
        'tasks': tasks_qs[:100],  # Limit to 100 recent for performance
        'activities': activities,
        'projects': projects,
        'employees': employees,
        'kpis': kpis,
        'active_tab': active_tab,
        'filters': {
            'search': search,
            'status': status_filter,
            'priority': priority_filter,
            'frequency': freq_filter,
            'employee_id': emp_filter,
            'project_id': proj_filter,
            'date_from': date_from,
            'date_to': date_to,
        },
        'priority_choices': ActivitySchedule.PRIORITY_CHOICES,
        'recurring_choices': ActivitySchedule.RECURRING_CHOICES,
        'status_choices': ActivitySchedule.STATUS_CHOICES,
        'task_status_choices': ActivityTask.STATUS_CHOICES,
    }
    return render(request, 'admin/master/activity_schedules.html', context)


@admin_required
def activity_schedule_store(request):
    """
    Store a new activity schedule and automatically generate tasks according to schedule recurrence.
    """
    if request.method != 'POST':
        return redirect('admin_activity_schedules_index')

    company_id = request.session.get('company_id', 1)
    
    title = request.POST.get('title', '').strip()
    activity_id = request.POST.get('activity_id')
    project_id = request.POST.get('project_id') or None
    assigned_to_id = request.POST.get('assigned_to_id') or None
    assigned_staff_raw = request.POST.getlist('assigned_staff')
    priority = request.POST.get('priority', 'Medium')
    recurring_type = request.POST.get('recurring_type', 'one_time')
    start_date = request.POST.get('start_date')
    start_time = request.POST.get('start_time') or None
    end_date = request.POST.get('end_date') or None
    deadline = request.POST.get('deadline') or None
    status = request.POST.get('status', 'Scheduled')
    auto_generate = request.POST.get('auto_generate_tasks') in ['1', 'on', 'true', True]
    remind_upcoming = request.POST.get('remind_upcoming') in ['1', 'on', 'true', True]
    notes = request.POST.get('notes', '').strip()

    if not title:
        messages.error(request, 'Schedule Title is required.')
        return redirect('admin_activity_schedules_index')

    if not activity_id:
        messages.error(request, 'Please select an Activity.')
        return redirect('admin_activity_schedules_index')

    if not start_date:
        messages.error(request, 'Start Date is required.')
        return redirect('admin_activity_schedules_index')

    activity = get_object_or_404(ActivityMaster, id=activity_id)

    # Process assigned staff IDs
    assigned_staff = []
    for s in assigned_staff_raw:
        if s and str(s).isdigit():
            assigned_staff.append(int(s))

    start_date_parsed = _parse_date(start_date)
    if not start_date_parsed:
        messages.error(request, 'Valid Start Date is required (YYYY-MM-DD).')
        return redirect('admin_activity_schedules_index')

    end_date_parsed = _parse_date(end_date)
    deadline_parsed = _parse_date(deadline)

    schedule = ActivitySchedule.objects.create(
        company_id=company_id,
        title=title,
        activity=activity,
        project_id=project_id,
        assigned_to_id=assigned_to_id,
        assigned_staff=assigned_staff,
        priority=priority,
        recurring_type=recurring_type,
        start_date=start_date_parsed,
        start_time=start_time if start_time else None,
        end_date=end_date_parsed,
        deadline=deadline_parsed,
        status=status,
        auto_generate_tasks=auto_generate,
        remind_upcoming=remind_upcoming,
        notes=notes,
        created_by='Admin'
    )
    schedule.refresh_from_db()

    # Automatic Task Generation
    created_tasks_count = 0
    if auto_generate and schedule.status in ['Scheduled', 'Pending', 'In Progress']:
        created_tasks_count = ActivityScheduleService.generate_tasks_for_schedule(schedule, horizon_days=60)

    # Send Notification to Primary Assignee if configured
    if assigned_to_id:
        try:
            from apps.expenses.views import send_fcm_notification
            emp = Employee.objects.filter(id=assigned_to_id).first()
            if emp and emp.fcm_token:
                send_fcm_notification(
                    emp.fcm_token,
                    f"New Activity Scheduled: {schedule.title}",
                    f"Priority: {schedule.priority} | Scheduled for: {schedule.start_date}"
                )
        except Exception:
            pass

    messages.success(
        request,
        f'Activity Schedule "{schedule.title}" created successfully! Generated {created_tasks_count} automatic task(s).'
    )
    return redirect('admin_activity_schedules_index')


@admin_required
def activity_schedule_update(request, id):
    """
    Update an existing activity schedule and synchronize pending future tasks.
    """
    if request.method != 'POST':
        return redirect('admin_activity_schedules_index')

    company_id = request.session.get('company_id', 1)
    schedule = get_object_or_404(ActivitySchedule, id=id, company_id=company_id)

    title = request.POST.get('title', '').strip()
    activity_id = request.POST.get('activity_id')
    project_id = request.POST.get('project_id') or None
    assigned_to_id = request.POST.get('assigned_to_id') or None
    assigned_staff_raw = request.POST.getlist('assigned_staff')
    priority = request.POST.get('priority', schedule.priority)
    recurring_type = request.POST.get('recurring_type', schedule.recurring_type)
    start_date = request.POST.get('start_date', str(schedule.start_date))
    start_time = request.POST.get('start_time') or None
    end_date = request.POST.get('end_date') or None
    deadline = request.POST.get('deadline') or None
    status = request.POST.get('status', schedule.status)
    auto_generate = request.POST.get('auto_generate_tasks') in ['1', 'on', 'true', True]
    remind_upcoming = request.POST.get('remind_upcoming') in ['1', 'on', 'true', True]
    notes = request.POST.get('notes', '').strip()

    if not title:
        messages.error(request, 'Schedule Title cannot be empty.')
        return redirect('admin_activity_schedules_index')

    if activity_id:
        schedule.activity_id = activity_id

    # Process assigned staff IDs
    assigned_staff = []
    for s in assigned_staff_raw:
        if s and str(s).isdigit():
            assigned_staff.append(int(s))

    schedule.title = title
    schedule.project_id = project_id
    schedule.assigned_to_id = assigned_to_id
    schedule.assigned_staff = assigned_staff
    schedule.priority = priority
    schedule.recurring_type = recurring_type
    schedule.start_date = _parse_date(start_date) or schedule.start_date
    schedule.start_time = start_time if start_time else None
    schedule.end_date = _parse_date(end_date)
    schedule.deadline = _parse_date(deadline)
    schedule.status = status
    schedule.auto_generate_tasks = auto_generate
    schedule.remind_upcoming = remind_upcoming
    schedule.notes = notes
    schedule.save()
    schedule.refresh_from_db()

    # Synchronize future pending tasks
    ActivityScheduleService.sync_schedule_update(schedule)

    messages.success(request, f'Schedule "{schedule.schedule_code}" updated successfully!')
    return redirect('admin_activity_schedules_index')


@admin_required
def activity_schedule_destroy(request, id):
    """
    Delete an activity schedule and all its associated tasks.
    """
    company_id = request.session.get('company_id', 1)
    schedule = get_object_or_404(ActivitySchedule, id=id, company_id=company_id)
    title = schedule.title
    code = schedule.schedule_code
    schedule.delete()

    messages.success(request, f'Schedule "{code} - {title}" and its generated tasks deleted successfully.')
    return redirect('admin_activity_schedules_index')


@admin_required
def activity_schedule_generate_tasks(request):
    """
    Manual trigger to run automatic task generation across all active recurring schedules.
    """
    company_id = request.session.get('company_id', 1)
    horizon_days = int(request.GET.get('days', 60))

    result = ActivityScheduleService.generate_all_active_schedules(
        horizon_days=horizon_days, company_id=company_id
    )

    tasks_created = result.get('tasks_created', 0)
    schedules_processed = result.get('schedules_processed', 0)

    messages.success(
        request,
        f'Automatic Task Generation finished: {tasks_created} new task(s) generated across {schedules_processed} active schedule(s).'
    )
    return redirect(f"{redirect('admin_activity_schedules_index').url}?tab=tasks")


@admin_required
def activity_task_update_status(request, id):
    """
    Update the status and completion remarks of an individual generated ActivityTask.
    Supports both standard form POST and JSON/AJAX requests.
    """
    company_id = request.session.get('company_id', 1)
    task = get_object_or_404(ActivityTask, id=id, company_id=company_id)

    if request.method == 'POST':
        new_status = request.POST.get('status', '').strip()
        remarks = request.POST.get('completion_remarks', '').strip()

        if new_status and new_status in dict(ActivityTask.STATUS_CHOICES):
            task.status = new_status
            if new_status == 'Completed':
                from django.utils import timezone
                task.completed_at = timezone.now()
            else:
                task.completed_at = None

        if remarks:
            task.completion_remarks = remarks

        task.save()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'message': f'Task {task.task_code} updated to {task.status}',
                'task_code': task.task_code,
                'status': task.status
            })

        messages.success(request, f'Task {task.task_code} status updated to "{task.status}".')

    return redirect(f"{redirect('admin_activity_schedules_index').url}?tab=tasks")


@admin_required
def activity_calendar_events_json(request):
    """
    API endpoint that returns FullCalendar / JSON formatted schedule and task events.
    """
    company_id = request.session.get('company_id', 1)
    start_str = request.GET.get('start', '').split('T')[0]
    end_str = request.GET.get('end', '').split('T')[0]
    employee_id = request.GET.get('employee_id')
    project_id = request.GET.get('project_id')
    status = request.GET.get('status')

    events = ActivityScheduleService.get_calendar_events(
        company_id=company_id,
        start_date=start_str or None,
        end_date=end_str or None,
        employee_id=employee_id if employee_id and employee_id.isdigit() else None,
        project_id=project_id if project_id and project_id.isdigit() else None,
        status=status or None
    )

    return JsonResponse(events, safe=False)


# ==========================================
# 10. LEAVE MANAGEMENT (MASTER)
# ==========================================
@admin_required
def leave_management_index(request):
    """
    Admin Leave Management dashboard and review console.
    Provides KPI summary cards, multi-facet filtering, and full request history.
    """
    company_id = request.session.get('company_id', 1)

    employee_filter = request.GET.get('employee', '').strip()
    department_filter = request.GET.get('department', '').strip()
    leave_type_filter = request.GET.get('leave_type', '').strip()
    status_filter = request.GET.get('status', '').strip()
    start_date_filter = request.GET.get('start_date', '').strip()
    end_date_filter = request.GET.get('end_date', '').strip()

    qs = LeaveRequest.objects.select_related('employee').all()

    # Pre-calculate counts before dynamic filters for dashboard KPIs
    total_count = qs.count()
    pending_count = qs.filter(status='pending').count()
    approved_count = qs.filter(status='approved').count()
    rejected_count = qs.filter(status='rejected').count()

    # Apply filters
    if employee_filter and employee_filter.isdigit():
        qs = qs.filter(employee_id=int(employee_filter))

    if leave_type_filter:
        qs = qs.filter(leave_type=leave_type_filter)

    if status_filter in ['pending', 'approved', 'rejected']:
        qs = qs.filter(status=status_filter)

    if start_date_filter:
        qs = qs.filter(start_date__gte=start_date_filter)

    if end_date_filter:
        qs = qs.filter(end_date__lte=end_date_filter)

    # Department filter requires joining employee designation -> department
    desig_map = {d.id: d for d in DesignationMaster.objects.all()}
    dept_map = {d.id: d.department_name for d in DepartmentMaster.objects.all()}

    leaves_list = []
    for leave in qs:
        emp = leave.employee
        desig_obj = desig_map.get(emp.role) if emp and emp.role else None
        desig_name = desig_obj.designation_name if desig_obj else '—'
        dept_id = desig_obj.department_id if desig_obj else None
        dept_name = dept_map.get(dept_id, '—') if dept_id else '—'

        if department_filter and str(dept_id) != str(department_filter):
            continue

        leaves_list.append({
            'id': leave.id,
            'employee_id': emp.id if emp else None,
            'employee_name': emp.name if emp else 'Unknown',
            'employee_code': f"EMP-{emp.id:04d}" if emp else '—',
            'designation': desig_name,
            'department': dept_name,
            'leave_type': leave.leave_type,
            'start_date': leave.start_date,
            'end_date': leave.end_date,
            'days_count': leave.days_count,
            'reason': leave.reason,
            'attachment': leave.attachment,
            'status': leave.status,
            'rejection_reason': leave.rejection_reason,
            'admin_remarks': leave.admin_remarks,
            'action_by': leave.action_by,
            'action_at': leave.action_at,
            'created_at': leave.created_at,
        })

    all_employees = Employee.objects.filter(status='active').order_by('name')
    all_departments = DepartmentMaster.objects.all().order_by('department_name')
    leave_types = [c[0] for c in LeaveRequest.LEAVE_TYPE_CHOICES]

    return render(request, 'admin/master/leavemanagement.html', {
        'leaves': leaves_list,
        'total_count': total_count,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'employees': all_employees,
        'departments': all_departments,
        'leave_types': leave_types,
        'employee_filter': employee_filter,
        'department_filter': department_filter,
        'leave_type_filter': leave_type_filter,
        'status_filter': status_filter,
        'start_date_filter': start_date_filter,
        'end_date_filter': end_date_filter,
    })


@admin_required
def leave_request_detail(request, id):
    """
    JSON detail endpoint for viewing the complete leave request in review modal.
    """
    leave = get_object_or_404(LeaveRequest.objects.select_related('employee'), id=id)
    emp = leave.employee
    desig = DesignationMaster.objects.filter(id=emp.role).first() if emp and emp.role else None
    dept = DepartmentMaster.objects.filter(id=desig.department_id).first() if desig and desig.department_id else None

    return JsonResponse({
        'success': True,
        'data': {
            'id': leave.id,
            'employee_id': emp.id if emp else None,
            'employee_name': emp.name if emp else 'Unknown',
            'employee_code': f"EMP-{emp.id:04d}" if emp else '—',
            'email': emp.email if emp else '',
            'phone': emp.phone if emp else '',
            'designation': desig.designation_name if desig else '—',
            'department': dept.department_name if dept else '—',
            'leave_type': leave.leave_type,
            'start_date': leave.start_date.strftime('%Y-%m-%d'),
            'end_date': leave.end_date.strftime('%Y-%m-%d'),
            'days_count': str(leave.days_count),
            'reason': leave.reason,
            'attachment': leave.attachment,
            'status': leave.status,
            'rejection_reason': leave.rejection_reason or '',
            'admin_remarks': leave.admin_remarks or '',
            'action_by': leave.action_by or '',
            'action_at': leave.action_at.strftime('%Y-%m-%d %H:%M:%S') if leave.action_at else '',
            'created_at': leave.created_at.strftime('%Y-%m-%d %H:%M:%S') if leave.created_at else '',
        }
    })


@admin_required
def leave_request_approve(request, id):
    """
    Admin action to approve a pending leave request.
    Records approver and timestamp, updates status to approved, and notifies employee.
    """
    leave = get_object_or_404(LeaveRequest.objects.select_related('employee'), id=id)
    if request.method == 'POST':
        admin_remarks = request.POST.get('admin_remarks', '').strip()
        approver = request.session.get('name') or ('Admin' if request.session.get('is_admin') == 1 else 'Administrator')

        leave.status = 'approved'
        leave.admin_remarks = admin_remarks
        leave.rejection_reason = None
        leave.action_by = approver
        leave.action_at = timezone.now()
        leave.save()

        # Notify employee via dynamic SMTP / FCM if configured
        emp = leave.employee
        if emp and emp.email:
            try:
                smtp = SMTPConfiguration.objects.first()
                from_name = smtp.from_name if smtp else 'SolarPro Leave Portal'
                subject = f"Leave Request Approved - {leave.leave_type}"
                body = (
                    f"Dear {emp.name},\n\n"
                    f"Your leave application for {leave.leave_type} from {leave.start_date} to {leave.end_date} "
                    f"({leave.days_count} days) has been APPROVED by {approver}.\n\n"
                    f"Remarks: {admin_remarks or 'None'}\n\n"
                    f"Regards,\nSolarPro Management"
                )
                from apps.api.views import send_dynamic_smtp_email
                send_dynamic_smtp_email(emp.email, subject, body)
            except Exception:
                pass

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json':
            return JsonResponse({'success': True, 'message': f'Leave request #{leave.id} approved successfully.'})

        messages.success(request, f'Leave request #{leave.id} for {emp.name} has been approved.')
    return redirect('admin_leave_management_index')


@admin_required
def leave_request_reject(request, id):
    """
    Admin action to reject a leave request.
    Requires mandatory rejection reason, records reviewer and timestamp, and notifies employee.
    """
    leave = get_object_or_404(LeaveRequest.objects.select_related('employee'), id=id)
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '').strip()
        admin_remarks = request.POST.get('admin_remarks', '').strip()
        reviewer = request.session.get('name') or ('Admin' if request.session.get('is_admin') == 1 else 'Administrator')

        if not rejection_reason:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json':
                return JsonResponse({'success': False, 'message': 'Rejection reason is mandatory.'}, status=422)
            messages.error(request, 'Rejection reason is mandatory to reject a leave request.')
            return redirect('admin_leave_management_index')

        leave.status = 'rejected'
        leave.rejection_reason = rejection_reason
        leave.admin_remarks = admin_remarks
        leave.action_by = reviewer
        leave.action_at = timezone.now()
        leave.save()

        # Notify employee
        emp = leave.employee
        if emp and emp.email:
            try:
                smtp = SMTPConfiguration.objects.first()
                from_name = smtp.from_name if smtp else 'SolarPro Leave Portal'
                subject = f"Leave Request Rejected - {leave.leave_type}"
                body = (
                    f"Dear {emp.name},\n\n"
                    f"Your leave application for {leave.leave_type} from {leave.start_date} to {leave.end_date} "
                    f"has been REJECTED by {reviewer}.\n\n"
                    f"Reason for rejection: {rejection_reason}\n"
                    f"Remarks: {admin_remarks or 'None'}\n\n"
                    f"Regards,\nSolarPro Management"
                )
                from apps.api.views import send_dynamic_smtp_email
                send_dynamic_smtp_email(emp.email, subject, body)
            except Exception:
                pass

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json':
            return JsonResponse({'success': True, 'message': f'Leave request #{leave.id} rejected.'})

        messages.success(request, f'Leave request #{leave.id} for {emp.name} has been rejected.')
    return redirect('admin_leave_management_index')


