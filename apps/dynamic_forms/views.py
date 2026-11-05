import json
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from apps.authentication.decorators import admin_required
from apps.dynamic_forms.models import DynamicForm, FormSubmission, DashboardConfig, DynamicDashboardSectionMaster
from apps.operations.models import Project
from apps.employees.models import Employee


# ==========================================
# 1. DYNAMIC FORMS CRUD
# ==========================================
@admin_required
def forms_index(request):
    company_id = request.session.get('company_id', 1)
    projects_map = {p.id: p.client_name for p in Project.objects.all()}

    forms_qs = DynamicForm.objects.filter(company_id=company_id).order_by('-created_at')
    forms = []
    for f in forms_qs:
        p_ids = f.project_ids if isinstance(f.project_ids, list) else []
        proj_names = [projects_map.get(int(pid), f"Project #{pid}") for pid in p_ids if str(pid).isdigit()]
        forms.append({
            'id': f.id,
            'form_name': f.form_name,
            'description': f.description,
            'project_names': ", ".join(proj_names),
            'created_at': f.created_at,
            'is_active': f.is_active,
        })

    return render(request, 'admin/forms/index.html', {'forms': forms})


@admin_required
def forms_create(request):
    projects = Project.objects.order_by('client_name')
    return render(request, 'admin/forms/builder.html', {
        'projects': projects,
        'form': None,
        'schema': {'columns': [], 'sections': []},
        'selectedProjectIds': [],
    })


@admin_required
def forms_store(request):
    if request.method == 'POST':
        form_name = request.POST.get('form_name', '').strip()
        description = request.POST.get('description', '')
        schema_raw = request.POST.get('form_schema', '{}')
        project_ids_raw = request.POST.getlist('project_ids[]')

        try:
            schema_json = json.loads(schema_raw) if isinstance(schema_raw, str) else schema_raw
        except Exception:
            schema_json = {'columns': [], 'sections': []}

        p_ids = [int(x) for x in project_ids_raw if x.isdigit()]

        DynamicForm.objects.create(
            company_id=request.session.get('company_id', 1),
            form_name=form_name,
            description=description,
            form_schema=schema_json,
            project_ids=p_ids,
            is_active=1,
        )

        messages.success(request, f'Form "{form_name}" created successfully.')
        return redirect('admin_forms_index')
    return redirect('admin_forms_create')


@admin_required
def forms_show(request, id):
    form = get_object_or_404(DynamicForm, id=id)
    schema = form.form_schema if isinstance(form.form_schema, dict) else json.loads(form.form_schema or '{}')

    # Pull latest submission if exists to show sample values
    latest_sub = FormSubmission.objects.filter(form_id=id).order_by('-created_at').first()
    if latest_sub:
        answers = latest_sub.submission_data if isinstance(latest_sub.submission_data, dict) else json.loads(latest_sub.submission_data or '{}')
        columns = answers.get('columns') or schema.get('columns', [])
        merged_sections = []
        for saved_sec in answers.get('sections', []):
            merged_rows = []
            for saved_row in saved_sec.get('rows', []):
                saved_answers = saved_row.get('answers') or saved_row.get('values', {})
                vals = {col: saved_answers.get(col, '') for col in columns}
                merged_rows.append({
                    'name': saved_row.get('name', ''),
                    'type': saved_row.get('type', 'text'),
                    'unit': saved_row.get('unit', ''),
                    'values': vals,
                })
            merged_sections.append({
                'name': saved_sec.get('name', ''),
                'rows': merged_rows,
            })
        if merged_sections:
            schema = {'columns': columns, 'sections': merged_sections}

    return render(request, 'admin/forms/show.html', {
        'form': form,
        'schema': schema,
    })


@admin_required
def forms_edit(request, id):
    form = get_object_or_404(DynamicForm, id=id)
    projects = Project.objects.order_by('client_name')
    schema = form.form_schema if isinstance(form.form_schema, dict) else json.loads(form.form_schema or '{}')
    selected_pids = form.project_ids if isinstance(form.project_ids, list) else []

    return render(request, 'admin/forms/builder.html', {
        'form': form,
        'schema': schema,
        'projects': projects,
        'selectedProjectIds': selected_pids,
    })


@admin_required
def forms_update(request, id):
    form = get_object_or_404(DynamicForm, id=id)
    if request.method == 'POST':
        form_name = request.POST.get('form_name', '').strip()
        description = request.POST.get('description', '')
        schema_raw = request.POST.get('form_schema', '{}')
        project_ids_raw = request.POST.getlist('project_ids[]')

        try:
            schema_json = json.loads(schema_raw) if isinstance(schema_raw, str) else schema_raw
        except Exception:
            schema_json = form.form_schema

        p_ids = [int(x) for x in project_ids_raw if x.isdigit()]

        form.form_name = form_name
        form.description = description
        form.form_schema = schema_json
        form.project_ids = p_ids
        form.save()

        messages.success(request, f'Form "{form_name}" updated successfully.')
        return redirect('admin_forms_index')
    return redirect('admin_forms_edit', id=id)


@admin_required
def forms_destroy(request, id):
    form = get_object_or_404(DynamicForm, id=id)
    name = form.form_name
    form.delete()
    messages.success(request, f'Form "{name}" deleted successfully.')
    return redirect('admin_forms_index')


# ==========================================
# 2. FORM SUBMISSIONS
# ==========================================
@admin_required
def form_submissions_index(request):
    company_id = request.session.get('company_id', 1)
    subs_qs = FormSubmission.objects.filter(company_id=company_id).order_by('-created_at')

    # Filters
    emp_search = request.GET.get('employee_name', '').strip().lower()
    proj_filter = request.GET.get('project_id')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if proj_filter and proj_filter.isdigit():
        subs_qs = subs_qs.filter(project_id=int(proj_filter))
    if date_from:
        subs_qs = subs_qs.filter(created_at__date__gte=date_from)
    if date_to:
        subs_qs = subs_qs.filter(created_at__date__lte=date_to)

    forms_map = {f.id: f.form_name for f in DynamicForm.objects.all()}
    emps_map = {e.id: e.name for e in Employee.objects.all()}
    projs_map = {p.id: p.client_name for p in Project.objects.all()}

    submissions = []
    for sub in subs_qs:
        emp_name = emps_map.get(sub.emp_id, '—')
        if emp_search and emp_search not in emp_name.lower():
            continue
        submissions.append({
            'id': sub.id,
            'form_id': sub.form_id,
            'form_name': forms_map.get(sub.form_id, f"Form #{sub.form_id}"),
            'employee_name': emp_name,
            'project_name': projs_map.get(sub.project_id, '—'),
            'created_at': sub.created_at,
        })

    projects = Project.objects.order_by('client_name')

    return render(request, 'admin/forms/submissions.html', {
        'submissions': submissions,
        'projects': projects,
    })


@admin_required
def form_submissions_edit(request, id):
    submission = get_object_or_404(FormSubmission, id=id)
    form = get_object_or_404(DynamicForm, id=submission.form_id)
    employee = Employee.objects.filter(id=submission.emp_id).first()
    project = Project.objects.filter(id=submission.project_id).first()

    schema = form.form_schema if isinstance(form.form_schema, dict) else json.loads(form.form_schema or '{}')
    answers = submission.submission_data if isinstance(submission.submission_data, dict) else json.loads(submission.submission_data or '{}')

    return render(request, 'admin/forms/submission-edit.html', {
        'submission': submission,
        'form': form,
        'employee_name': employee.name if employee else '—',
        'project_name': project.client_name if project else '—',
        'schema': schema,
        'answers': answers,
    })


@admin_required
def form_submissions_update(request, id):
    submission = get_object_or_404(FormSubmission, id=id)
    if request.method == 'POST':
        sub_raw = request.POST.get('submission_data', '{}')
        try:
            sub_json = json.loads(sub_raw) if isinstance(sub_raw, str) else sub_raw
        except Exception:
            sub_json = submission.submission_data

        submission.submission_data = sub_json
        submission.save()
        messages.success(request, 'Submission updated successfully.')
        return redirect('admin_form_submissions_index')
    return redirect('admin_form_submissions_edit', id=id)


# ==========================================
# 3. DYNAMIC DASHBOARD & CONFIG
# ==========================================
@admin_required
def dashboard_config_index(request):
    company_id = request.session.get('company_id', 1)
    forms = DynamicForm.objects.filter(company_id=company_id)
    sections = DynamicDashboardSectionMaster.objects.filter(company_id=company_id).order_by('created_at')
    cfg = DashboardConfig.objects.filter(company_id=company_id).first()
    saved_config = cfg.config_json if cfg else '[]'

    sections_list = [{'id': s.id, 'section_name': s.section_name} for s in sections]

    return render(request, 'admin/dynamic-dashboard/dashboard-config.html', {
        'forms': forms,
        'savedConfig': saved_config,
        'sections': json.dumps(sections_list),
    })


@admin_required
def dashboard_config_save(request):
    if request.method == 'POST':
        company_id = request.session.get('company_id', 1)
        cfg_json = request.POST.get('config_json', '[]')

        DashboardConfig.objects.update_or_create(
            company_id=company_id,
            defaults={'config_json': cfg_json}
        )
        messages.success(request, 'Dashboard Configuration Saved!')
    return redirect('admin_dashboard_config')


@admin_required
def dashboard_section_store(request):
    """AJAX: Create a new dashboard section."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = {}
        section_name = (data.get('section_name') or '').strip()
        if not section_name:
            return JsonResponse({'success': False, 'message': 'Section name is required.'}, status=422)

        company_id = request.session.get('company_id', 1)
        sec = DynamicDashboardSectionMaster.objects.create(
            company_id=company_id,
            section_name=section_name,
        )
        return JsonResponse({'success': True, 'section': {'id': sec.id, 'section_name': sec.section_name}})
    return JsonResponse({'success': False}, status=405)


@admin_required
def dashboard_section_delete(request, section_id):
    """AJAX: Delete a dashboard section."""
    if request.method == 'DELETE':
        sec = DynamicDashboardSectionMaster.objects.filter(id=section_id).first()
        if not sec:
            return JsonResponse({'success': False, 'message': 'Section not found.'}, status=404)
        sec.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)


@admin_required
def get_form_fields(request, formId):
    form = DynamicForm.objects.filter(id=formId).first()
    if not form:
        return JsonResponse([], safe=False)

    schema = form.form_schema if isinstance(form.form_schema, dict) else json.loads(form.form_schema or '{}')
    fields = []

    for sec in schema.get('sections', []):
        for row in sec.get('rows', []):
            if row.get('type') == 'number':
                for col in schema.get('columns', []):
                    fields.append({
                        'id': f"{row.get('name')}|{col}",
                        'label': f"{sec.get('name')} -> {row.get('name')} ({col})"
                    })

    return JsonResponse(fields, safe=False)


@admin_required
def dynamic_dashboard(request):
    company_id = request.session.get('company_id', 1)
    filter_mode = request.GET.get('filter', 'daily')
    project_id = request.GET.get('project_id')

    projects = Project.objects.filter(company_id=company_id)
    sections_qs = DynamicDashboardSectionMaster.objects.filter(company_id=company_id).order_by('created_at')
    cfg = DashboardConfig.objects.filter(company_id=company_id).first()
    try:
        graphs = json.loads(cfg.config_json) if cfg and cfg.config_json else []
        if not isinstance(graphs, list):
            graphs = []
    except Exception:
        graphs = []

    subs_qs = FormSubmission.objects.filter(company_id=company_id)
    if project_id and project_id.isdigit():
        subs_qs = subs_qs.filter(project_id=int(project_id))
    submissions = list(subs_qs.order_by('created_at'))

    chart_data = []

    for graph in graphs:
        form_id = graph.get('form_id')
        field_str = graph.get('field', '')
        parts = field_str.split('|')
        if len(parts) != 2:
            continue
        row_name, col_name = parts[0], parts[1]

        grouped = {}
        min_val = None
        max_val = None

        for sub in submissions:
            if str(sub.form_id) != str(form_id):
                continue

            dt = sub.created_at
            if filter_mode == 'weekly':
                start_of_week = dt.date() - timedelta(days=dt.weekday())
                date_key = start_of_week.strftime('%d %b %Y')
            elif filter_mode == 'monthly':
                date_key = dt.strftime('%b %Y')
            else:
                date_key = dt.strftime('%d %b %Y')

            s_data = sub.submission_data if isinstance(sub.submission_data, dict) else json.loads(sub.submission_data or '{}')

            val = None
            for sec in s_data.get('sections', []):
                for r in sec.get('rows', []):
                    if r.get('name') == row_name:
                        ans = r.get('answers') or r.get('values', {})
                        val = ans.get(col_name)
                        break
                if val is not None:
                    break

            try:
                num_val = float(val)
            except (ValueError, TypeError):
                continue

            if date_key not in grouped:
                grouped[date_key] = {'sum': 0.0, 'count': 0}
            grouped[date_key]['sum'] += num_val
            grouped[date_key]['count'] += 1

            if min_val is None or num_val < min_val:
                min_val = num_val
            if max_val is None or num_val > max_val:
                max_val = num_val

        labels = []
        vals = []
        for k, st in grouped.items():
            labels.append(k)
            vals.append(round(st['sum'] / st['count'], 2))

        chart_data.append({
            'config': graph,
            'labels': labels,
            'values': vals,
            'min': max(0, min_val - (min_val * 0.1)) if min_val is not None else 0,
            'max': (max_val + (max_val * 0.1)) if max_val is not None else 100,
        })

    # Group chart_data by section
    section_map = {str(s.id): s.section_name for s in sections_qs}
    grouped_by_section = {}
    for idx, item in enumerate(chart_data):
        sid = str(item['config'].get('section_id', ''))
        sec_name = section_map.get(sid, 'Other')
        if sec_name not in grouped_by_section:
            grouped_by_section[sec_name] = []
        grouped_by_section[sec_name].append({'index': idx, 'data': item})

    # Build ordered sections list (ordered sections first, then 'Other')
    ordered_sections = []
    for s in sections_qs:
        if s.section_name in grouped_by_section:
            ordered_sections.append({'name': s.section_name, 'items': grouped_by_section[s.section_name]})
    if 'Other' in grouped_by_section:
        ordered_sections.append({'name': 'Other', 'items': grouped_by_section['Other']})

    return render(request, 'admin/dynamic-dashboard/dynamic-dashboard.html', {
        'chartData': chart_data,
        'orderedSections': ordered_sections,
        'projects': projects,
        'filterMode': filter_mode,
        'projectId': project_id or '',
    })


# ==========================================
# 4. BACKUP (TEST) DYNAMIC DASHBOARD & CONFIG
# ==========================================
@admin_required
def dashboard_config_backup_index(request):
    company_id = request.session.get('company_id', 1)
    forms_qs = DynamicForm.objects.filter(company_id=company_id)
    cfg = DashboardConfig.objects.filter(company_id=company_id).first()
    saved_config = cfg.config_json if cfg and cfg.config_json else '[]'

    sections_qs = DynamicDashboardSectionMaster.objects.filter(company_id=company_id).order_by('id')
    sections_list = [{'id': s.id, 'section_name': s.section_name} for s in sections_qs]
    forms_list = [{'id': f.id, 'form_name': f.form_name} for f in forms_qs]

    return render(request, 'admin/dynamic-dashboard/dashboard-config-backup.html', {
        'forms': forms_qs,
        'forms_json': json.dumps(forms_list),
        'savedConfig': saved_config,
        'sections': sections_qs,
        'sections_json': json.dumps(sections_list),
    })


@admin_required
def dashboard_config_backup_save(request):
    if request.method == 'POST':
        company_id = request.session.get('company_id', 1)
        cfg_json = request.POST.get('config_json', '[]')
        DashboardConfig.objects.update_or_create(
            company_id=company_id,
            defaults={'config_json': cfg_json}
        )
        messages.success(request, 'Dashboard Configuration Saved!')
    return redirect('admin_dashboard_config_backup')


@admin_required
def dashboard_backup_section_store(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = request.POST
        name = (data.get('section_name') or '').strip()
        if not name:
            return JsonResponse({'success': False, 'message': 'Please enter a section name'}, status=422)
        company_id = request.session.get('company_id', 1)
        sec = DynamicDashboardSectionMaster.objects.create(
            company_id=company_id,
            section_name=name
        )
        return JsonResponse({'success': True, 'section': {'id': sec.id, 'section_name': sec.section_name}})
    return JsonResponse({'success': False}, status=405)


@admin_required
def dashboard_backup_section_delete(request, section_id):
    if request.method in ('DELETE', 'POST'):
        sec = DynamicDashboardSectionMaster.objects.filter(id=section_id).first()
        if not sec:
            return JsonResponse({'success': False, 'message': 'Could not delete section'}, status=404)
        sec.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=405)


@admin_required
def dynamic_dashboard_backup(request):
    company_id = request.session.get('company_id', 1)
    filter_mode = request.GET.get('filter', 'daily')
    project_id = request.GET.get('project_id')

    projects = Project.objects.filter(company_id=company_id)
    sections_qs = DynamicDashboardSectionMaster.objects.filter(company_id=company_id).order_by('id')
    cfg = DashboardConfig.objects.filter(company_id=company_id).first()
    try:
        graphs = json.loads(cfg.config_json) if cfg and cfg.config_json else []
        if not isinstance(graphs, list):
            graphs = []
    except Exception:
        graphs = []

    subs_qs = FormSubmission.objects.filter(company_id=company_id)
    if project_id and project_id.isdigit():
        subs_qs = subs_qs.filter(project_id=int(project_id))
    submissions = list(subs_qs.order_by('created_at'))

    chart_data = []

    for graph in graphs:
        form_id = graph.get('form_id')
        field_str = graph.get('field', '')
        parts = field_str.split('|')
        if len(parts) != 2:
            continue
        row_name, col_name = parts[0], parts[1]

        grouped = {}
        min_val = None
        max_val = None

        for sub in submissions:
            if str(sub.form_id) != str(form_id):
                continue

            dt = sub.created_at
            if filter_mode == 'weekly':
                start_of_week = dt.date() - timedelta(days=dt.weekday())
                date_key = start_of_week.strftime('%d %b %Y')
            elif filter_mode == 'monthly':
                date_key = dt.strftime('%b %Y')
            else:
                date_key = dt.strftime('%d %b %Y')

            s_data = sub.submission_data if isinstance(sub.submission_data, dict) else json.loads(sub.submission_data or '{}')

            val = None
            for sec in s_data.get('sections', []):
                for r in sec.get('rows', []):
                    if r.get('name') == row_name:
                        ans = r.get('answers') or r.get('values', {})
                        val = ans.get(col_name)
                        break
                if val is not None:
                    break

            try:
                num_val = float(val)
            except (ValueError, TypeError):
                continue

            if date_key not in grouped:
                grouped[date_key] = {'sum': 0.0, 'count': 0}
            grouped[date_key]['sum'] += num_val
            grouped[date_key]['count'] += 1

            if min_val is None or num_val < min_val:
                min_val = num_val
            if max_val is None or num_val > max_val:
                max_val = num_val

        labels = []
        vals = []
        for k, st in grouped.items():
            labels.append(k)
            vals.append(round(st['sum'] / st['count'], 2))

        chart_data.append({
            'config': graph,
            'labels': labels,
            'values': vals,
            'min': max(0, min_val - (min_val * 0.1)) if min_val is not None else 0,
            'max': (max_val + (max_val * 0.1)) if max_val is not None else 100,
        })

    # Group chart_data by section exactly matching Laravel DynamicDashboardBackupController
    grouped_by_sec = {}
    for idx, d in enumerate(chart_data):
        sid = str(d['config'].get('section_id') or '')
        if sid not in grouped_by_sec:
            grouped_by_sec[sid] = []
        grouped_by_sec[sid].append({'index': idx, 'data': d})

    ordered = []
    known_ids = set()
    for s in sections_qs:
        s_id_str = str(s.id)
        known_ids.add(s_id_str)
        if s_id_str in grouped_by_sec:
            ordered.append({'name': s.section_name, 'items': grouped_by_sec[s_id_str]})

    others = []
    for sid, items in grouped_by_sec.items():
        if sid not in known_ids:
            others.extend(items)
    if others:
        ordered.append({'name': 'Other', 'items': others})

    return render(request, 'admin/dynamic-dashboard/dynamic-dashboard-backup.html', {
        'chartData': chart_data,
        'chartData_json': json.dumps(chart_data),
        'ordered': ordered,
        'projects': projects,
        'filterMode': filter_mode,
        'projectId': project_id or '',
        'sections': sections_qs,
    })
