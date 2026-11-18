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
    ActivityFormPhotoSetting, ActivityFormValidationRule, LeaveRequest
)
from apps.employees.models import Employee
from django.utils import timezone
from apps.masters.form_builder_service import ActivityFormService

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
    Tests user input against both standard validation and business exception rules.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST method required.'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        fields_config = data.get('fields', [])
        submitted_values = data.get('values', {})
        result = ActivityFormService.evaluate_submission(fields_config, submitted_values)
        return JsonResponse({
            'success': True,
            **result
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Evaluation error: {str(e)}'
        }, status=400)


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


