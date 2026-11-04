import csv
from datetime import datetime, time
from django.shortcuts import render
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from apps.authentication.decorators import admin_required
from apps.operations.models import Project
from apps.employees.models import Employee, EmployeeAttendance
from apps.masters.models import SiteMaster
from apps.inventory.models import OpeningStock, StockCategory, AssignedStock
from apps.dynamic_forms.models import DynamicForm, FormSubmission


def _parse_date_bounds(from_date, to_date):
    """
    Parses date strings (YYYY-MM-DD) into timezone-aware datetime boundaries.
    Avoids MySQL CONVERT_TZ failure on systems without mysql.time_zone_name.
    """
    tz = timezone.get_current_timezone()
    dt_from = None
    dt_to = None
    if from_date:
        try:
            d_from = datetime.strptime(str(from_date).strip(), '%Y-%m-%d')
            dt_from = timezone.make_aware(d_from, tz)
        except Exception:
            pass
    if to_date:
        try:
            d_to = datetime.strptime(str(to_date).strip(), '%Y-%m-%d')
            dt_to = timezone.make_aware(datetime.combine(d_to, time.max), tz)
        except Exception:
            pass
    return dt_from, dt_to


class Echo:
    """An object that implements just the write method of the file-like interface."""
    def write(self, value):
        return value


# ==========================================
# 1. PROJECT REPORT
# ==========================================
def get_filtered_projects(request, from_date, to_date):
    qs = Project.objects.all()

    dt_from, dt_to = _parse_date_bounds(from_date, to_date)
    if dt_from:
        qs = qs.filter(created_at__gte=dt_from)
    if dt_to:
        qs = qs.filter(created_at__lte=dt_to)

    client = request.GET.get('client')
    code = request.GET.get('code')
    search = request.GET.get('search', '').strip().lower()

    if client:
        qs = qs.filter(client_name=client)
    if code:
        digits = ''.join(c for c in code if c.isdigit())
        if digits:
            qs = qs.filter(id=int(digits))

    emp_map = {e.id: e.name for e in Employee.objects.all()}

    projects = []
    for p in qs.order_by('-created_at'):
        mgr_name = emp_map.get(p.site_manager, '—')
        if search and (search not in p.client_name.lower() and search not in mgr_name.lower()):
            continue
        projects.append({
            'id': p.id,
            'code': f"SP-{str(p.id).zfill(4)}",
            'client_name': p.client_name,
            'manager_name': mgr_name,
            'start_date': p.start_date.strftime('%Y-%m-%d') if p.start_date else '—',
            'end_date': p.end_date.strftime('%Y-%m-%d') if p.end_date else '—',
            'system_size': 0,
            'status': p.status,
            'status_display': p.status.replace('_', ' ').title(),
        })
    return projects


@admin_required
def project_report(request):
    from_date = request.GET.get('from', '2026-01-01')
    to_date = request.GET.get('to', timezone.localdate().strftime('%Y-%m-%d'))

    projects = get_filtered_projects(request, from_date, to_date)
    clients = list(Project.objects.values_list('client_name', flat=True).distinct().order_by('client_name'))

    return render(request, 'admin/reports/projectreport.html', {
        'projects': projects,
        'from': from_date,
        'to': to_date,
        'clients': clients,
    })


@admin_required
def project_report_export_excel(request):
    from_date = request.GET.get('from', '2026-01-01')
    to_date = request.GET.get('to', timezone.localdate().strftime('%Y-%m-%d'))
    projects = get_filtered_projects(request, from_date, to_date)

    rows = [['Code', 'Client', 'Manager', 'Start Date', 'End Date', 'System Size (kW)', 'Status']]
    for p in projects:
        rows.append([p['code'], p['client_name'], p['manager_name'], p['start_date'], p['end_date'], p['system_size'], p['status_display']])

    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    response = StreamingHttpResponse((writer.writerow(r) for r in rows), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="project_report_{timezone.now().strftime("%Y-%m-%d_%H%M%S")}.csv"'
    return response


@admin_required
def project_report_export_pdf(request):
    from_date = request.GET.get('from', '2026-01-01')
    to_date = request.GET.get('to', timezone.localdate().strftime('%Y-%m-%d'))
    projects = get_filtered_projects(request, from_date, to_date)

    rows_html = "".join([f"<tr><td>{p['code']}</td><td>{p['client_name']}</td><td>{p['manager_name']}</td><td>{p['start_date']}</td><td>{p['end_date']}</td><td>{p['system_size']} kW</td><td>{p['status_display']}</td></tr>" for p in projects])
    if not rows_html:
        rows_html = '<tr><td colspan="7" style="text-align:center;">No projects found.</td></tr>'

    html = f"""<!DOCTYPE html><html><head><title>Project Report</title><style>
        body {{ font-family: Arial, sans-serif; padding: 30px; color: #111827; }}
        h2 {{ margin-bottom: 0.25rem; }}
        .meta {{ color: #6B7280; margin-bottom: 1.5rem; font-size: 0.9rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px 10px; border-bottom: 1px solid #E5E7EB; text-align: left; font-size: 0.9rem; }}
        th {{ background: #F9FAFB; font-weight: 700; }}
    </style></head>
    <body onload="window.print()">
        <h2>Project Report</h2>
        <div class="meta">Period: {from_date} to {to_date}</div>
        <table>
            <thead><tr><th>Code</th><th>Client</th><th>Manager</th><th>Start</th><th>End</th><th>Size</th><th>Status</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </body></html>"""
    return HttpResponse(html, content_type='text/html')


# ==========================================
# 2. MAINTENANCE REPORT
# ==========================================
@admin_required
def maintenance_report(request):
    company_id = request.session.get('company_id', 1)
    subs_qs = FormSubmission.objects.filter(company_id=company_id)

    site_id = request.GET.get('site_id')
    emp_name = request.GET.get('employee_name', '').strip().lower()
    project_id = request.GET.get('project_id')
    form_id = request.GET.get('form_id')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if project_id and project_id.isdigit():
        subs_qs = subs_qs.filter(project_id=int(project_id))
    if form_id and form_id.isdigit():
        subs_qs = subs_qs.filter(form_id=int(form_id))
    dt_from, dt_to = _parse_date_bounds(date_from, date_to)
    if dt_from:
        subs_qs = subs_qs.filter(created_at__gte=dt_from)
    if dt_to:
        subs_qs = subs_qs.filter(created_at__lte=dt_to)

    forms_map = {f.id: f.form_name for f in DynamicForm.objects.all()}
    emps_map = {e.id: e.name for e in Employee.objects.all()}
    projs_map = {p.id: p for p in Project.objects.all()}
    sites_map = {s.id: s.site_name for s in SiteMaster.objects.all()}

    submissions = []
    for sub in subs_qs.order_by('-created_at'):
        e_name = emps_map.get(sub.emp_id, '—')
        if emp_name and emp_name not in e_name.lower():
            continue

        proj = projs_map.get(sub.project_id)
        proj_name = proj.client_name if proj else '—'
        s_id = proj.site_id if proj else None
        s_name = sites_map.get(s_id, '—') if s_id else '—'

        if site_id and str(s_id) != str(site_id):
            continue

        submissions.append({
            'id': sub.id,
            'form_id': sub.form_id,
            'form_name': forms_map.get(sub.form_id, f"Form #{sub.form_id}"),
            'employee_name': e_name,
            'project_name': proj_name,
            'site_name': s_name,
            'created_at': sub.created_at,
        })

    sites = SiteMaster.objects.order_by('site_name')
    projects = Project.objects.order_by('client_name')
    employees = Employee.objects.filter(company_id=company_id).order_by('name')
    forms = DynamicForm.objects.filter(company_id=company_id).order_by('form_name')

    return render(request, 'admin/reports/maintenancereport.html', {
        'submissions': submissions,
        'sites': sites,
        'projects': projects,
        'employees': employees,
        'forms': forms,
    })


@admin_required
def maintenance_report_export_excel(request):
    company_id = request.session.get('company_id', 1)
    subs_qs = FormSubmission.objects.filter(company_id=company_id)
    forms_map = {f.id: f.form_name for f in DynamicForm.objects.all()}
    emps_map = {e.id: e.name for e in Employee.objects.all()}
    projs_map = {p.id: p.client_name for p in Project.objects.all()}

    rows = [['ID', 'Form Name', 'Employee', 'Project', 'Date']]
    for s in subs_qs.order_by('-created_at'):
        rows.append([s.id, forms_map.get(s.form_id, '—'), emps_map.get(s.emp_id, '—'), projs_map.get(s.project_id, '—'), s.created_at.strftime('%Y-%m-%d %H:%M')])

    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    response = StreamingHttpResponse((writer.writerow(r) for r in rows), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="maintenance_report_{timezone.now().strftime("%Y-%m-%d_%H%M%S")}.csv"'
    return response


@admin_required
def maintenance_report_export_pdf(request):
    company_id = request.session.get('company_id', 1)
    subs_qs = FormSubmission.objects.filter(company_id=company_id)
    forms_map = {f.id: f.form_name for f in DynamicForm.objects.all()}
    emps_map = {e.id: e.name for e in Employee.objects.all()}
    projs_map = {p.id: p.client_name for p in Project.objects.all()}

    rows_html = "".join([f"<tr><td>{s.id}</td><td>{forms_map.get(s.form_id, '—')}</td><td>{emps_map.get(s.emp_id, '—')}</td><td>{projs_map.get(s.project_id, '—')}</td><td>{s.created_at.strftime('%Y-%m-%d')}</td></tr>" for s in subs_qs.order_by('-created_at')])
    if not rows_html:
        rows_html = '<tr><td colspan="5" style="text-align:center;">No records found.</td></tr>'

    html = f"""<!DOCTYPE html><html><head><title>Maintenance Report</title><style>
        body {{ font-family: Arial, sans-serif; padding: 30px; color: #111827; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px 10px; border-bottom: 1px solid #E5E7EB; text-align: left; font-size: 0.9rem; }}
        th {{ background: #F9FAFB; font-weight: 700; }}
    </style></head>
    <body onload="window.print()">
        <h2>Maintenance Report</h2>
        <table>
            <thead><tr><th>ID</th><th>Form</th><th>Employee</th><th>Project</th><th>Date</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </body></html>"""
    return HttpResponse(html, content_type='text/html')


# ==========================================
# 3. ATTENDANCE REPORT
# ==========================================
def get_attendance_logs(request, from_date, to_date):
    qs = EmployeeAttendance.objects.all()
    dt_from, dt_to = _parse_date_bounds(from_date, to_date)
    if dt_from:
        qs = qs.filter(punch_in__gte=dt_from)
    if dt_to:
        qs = qs.filter(punch_in__lte=dt_to)

    emp_filter = request.GET.get('employee')
    proj_filter = request.GET.get('project')
    search = request.GET.get('search', '').strip().lower()

    emps_map = {e.id: e.name for e in Employee.objects.all()}
    projs_map = {p.id: p.client_name for p in Project.objects.all()}

    # Map employee ID to project name based on assignments
    emp_proj_map = {}
    for p in Project.objects.all():
        if p.site_manager:
            emp_proj_map[p.site_manager] = p.client_name
        if p.field_staff and isinstance(p.field_staff, list):
            for fs_id in p.field_staff:
                try:
                    emp_proj_map[int(fs_id)] = p.client_name
                except (ValueError, TypeError):
                    pass

    logs = []
    for att in qs.order_by('-punch_in'):
        staff_name = emps_map.get(att.employee_id, '—')
        proj_id = getattr(att, 'project_id', None)
        proj_name = projs_map.get(proj_id) if proj_id else emp_proj_map.get(att.employee_id, '—')
        if not proj_name:
            proj_name = '—'

        if emp_filter and staff_name != emp_filter:
            continue
        if proj_filter and proj_name != proj_filter:
            continue
        if search and (search not in staff_name.lower() and search not in proj_name.lower()):
            continue

        hours = 0.0
        time_out_str = '-'
        if att.punch_out:
            time_out_str = att.punch_out.strftime('%H:%M')
            diff_mins = (att.punch_out - att.punch_in).total_seconds() / 60.0
            hours = round(diff_mins / 60.0, 1)

        logs.append({
            'id': att.id,
            'staff': staff_name,
            'project_name': proj_name,
            'date': att.punch_in.strftime('%Y-%m-%d'),
            'time_in': att.punch_in.strftime('%H:%M'),
            'time_out': time_out_str,
            'hours': hours,
        })
    return logs


@admin_required
def attendance_report(request):
    today = timezone.localdate()
    from_date = request.GET.get('from', today.replace(day=1).strftime('%Y-%m-%d'))
    to_date = request.GET.get('to', today.strftime('%Y-%m-%d'))

    attendance_logs = get_attendance_logs(request, from_date, to_date)
    employees = Employee.objects.order_by('name').values_list('name', flat=True)
    projects = Project.objects.order_by('client_name').values_list('client_name', flat=True)

    return render(request, 'admin/reports/attendancereport.html', {
        'attendanceLogs': attendance_logs,
        'employees': employees,
        'projects': projects,
        'from': from_date,
        'to': to_date,
    })


@admin_required
def attendance_report_export_excel(request):
    today = timezone.localdate()
    from_date = request.GET.get('from', today.replace(day=1).strftime('%Y-%m-%d'))
    to_date = request.GET.get('to', today.strftime('%Y-%m-%d'))
    logs = get_attendance_logs(request, from_date, to_date)

    rows = [['Staff', 'Date', 'Time In', 'Time Out', 'Hours', 'Project']]
    for l in logs:
        rows.append([l['staff'], l['date'], l['time_in'], l['time_out'], l['hours'], l['project_name']])

    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    response = StreamingHttpResponse((writer.writerow(r) for r in rows), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_report_{timezone.now().strftime("%Y-%m-%d_%H%M%S")}.csv"'
    return response


@admin_required
def attendance_report_export_pdf(request):
    today = timezone.localdate()
    from_date = request.GET.get('from', today.replace(day=1).strftime('%Y-%m-%d'))
    to_date = request.GET.get('to', today.strftime('%Y-%m-%d'))
    logs = get_attendance_logs(request, from_date, to_date)

    rows_html = "".join([f"<tr><td>{l['staff']}</td><td>{l['date']}</td><td>{l['time_in']}</td><td>{l['time_out']}</td><td>{l['hours']}</td><td>{l['project_name']}</td></tr>" for l in logs])
    if not rows_html:
        rows_html = '<tr><td colspan="6" style="text-align:center;">No attendance records found.</td></tr>'

    html = f"""<!DOCTYPE html><html><head><title>Attendance Report</title><style>
        body {{ font-family: Arial, sans-serif; padding: 30px; color: #111827; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px 10px; border-bottom: 1px solid #E5E7EB; text-align: left; font-size: 0.9rem; }}
        th {{ background: #F9FAFB; font-weight: 700; }}
    </style></head>
    <body onload="window.print()">
        <h2>Attendance Report</h2>
        <div style="color:#6B7280;margin-bottom:1.5rem;">Period: {from_date} to {to_date}</div>
        <table>
            <thead><tr><th>Staff</th><th>Date</th><th>Time In</th><th>Time Out</th><th>Hours</th><th>Project</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </body></html>"""
    return HttpResponse(html, content_type='text/html')


# ==========================================
# 4. STOCK REPORT
# ==========================================
@admin_required
def stock_report(request):
    from_date = request.GET.get('from', '2026-01-01')
    to_date = request.GET.get('to', timezone.localdate().strftime('%Y-%m-%d'))
    search = request.GET.get('search', '').strip().lower()

    items = OpeningStock.objects.order_by('item_name')
    cats_map = {c.id: c.category_name for c in StockCategory.objects.all()}

    # Calculate consumed stock within date range from AssignedStock
    assigned_qs = AssignedStock.objects.all()
    dt_from, dt_to = _parse_date_bounds(from_date, to_date)
    if dt_from:
        assigned_qs = assigned_qs.filter(created_at__gte=dt_from)
    if dt_to:
        assigned_qs = assigned_qs.filter(created_at__lte=dt_to)
    consumed_map = {}
    for ast in assigned_qs:
        consumed_map[ast.item_id] = consumed_map.get(ast.item_id, 0.0) + float(ast.qty)

    report_list = []
    for item in items:
        cat_name = cats_map.get(item.category, 'General')
        if search and (search not in item.item_name.lower() and search not in cat_name.lower()):
            continue

        opening = float(item.quantity)
        grn = 0.0
        consumed = consumed_map.get(item.id, 0.0)
        closing = opening + grn - consumed

        report_list.append({
            'id': item.id,
            'name': item.item_name,
            'category': cat_name,
            'unit': item.unit,
            'rate': float(item.rate),
            'opening': opening,
            'grn': grn,
            'consumed': consumed,
            'closing': closing,
        })

    return render(request, 'admin/stock/stockreport.html', {
        'stockReport': report_list,
        'from': from_date,
        'to': to_date,
    })


@admin_required
def stock_report_export_excel(request):
    from_date = request.GET.get('from', '2026-01-01')
    to_date = request.GET.get('to', timezone.localdate().strftime('%Y-%m-%d'))

    items = OpeningStock.objects.order_by('item_name')
    cats_map = {c.id: c.category_name for c in StockCategory.objects.all()}
    assigned_qs = AssignedStock.objects.all()
    dt_from, dt_to = _parse_date_bounds(from_date, to_date)
    if dt_from:
        assigned_qs = assigned_qs.filter(created_at__gte=dt_from)
    if dt_to:
        assigned_qs = assigned_qs.filter(created_at__lte=dt_to)
    consumed_map = {}
    for ast in assigned_qs:
        consumed_map[ast.item_id] = consumed_map.get(ast.item_id, 0.0) + float(ast.qty)

    rows = [['Item Name', 'Category', 'Unit', 'Rate', 'Opening', 'GRN', 'Consumed', 'Closing']]
    for item in items:
        cat_name = cats_map.get(item.category, 'General')
        opening = float(item.quantity)
        consumed = consumed_map.get(item.id, 0.0)
        closing = opening - consumed
        rows.append([item.item_name, cat_name, item.unit, float(item.rate), opening, 0, consumed, closing])

    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    response = StreamingHttpResponse((writer.writerow(r) for r in rows), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="stock_report_{timezone.now().strftime("%Y-%m-%d_%H%M%S")}.csv"'
    return response


@admin_required
def stock_report_export_pdf(request):
    from_date = request.GET.get('from', '2026-01-01')
    to_date = request.GET.get('to', timezone.localdate().strftime('%Y-%m-%d'))

    items = OpeningStock.objects.order_by('item_name')
    cats_map = {c.id: c.category_name for c in StockCategory.objects.all()}
    assigned_qs = AssignedStock.objects.all()
    dt_from, dt_to = _parse_date_bounds(from_date, to_date)
    if dt_from:
        assigned_qs = assigned_qs.filter(created_at__gte=dt_from)
    if dt_to:
        assigned_qs = assigned_qs.filter(created_at__lte=dt_to)
    consumed_map = {}
    for ast in assigned_qs:
        consumed_map[ast.item_id] = consumed_map.get(ast.item_id, 0.0) + float(ast.qty)

    rows_html = "".join([f"<tr><td>{item.item_name}</td><td>{cats_map.get(item.category, 'General')}</td><td>{item.unit}</td><td>₹{item.rate}</td><td>{item.quantity}</td><td>0</td><td>{consumed_map.get(item.id, 0)}</td><td>{float(item.quantity) - consumed_map.get(item.id, 0)}</td></tr>" for item in items])
    if not rows_html:
        rows_html = '<tr><td colspan="8" style="text-align:center;">No stock items found.</td></tr>'

    html = f"""<!DOCTYPE html><html><head><title>Stock Report</title><style>
        body {{ font-family: Arial, sans-serif; padding: 30px; color: #111827; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px 10px; border-bottom: 1px solid #E5E7EB; text-align: left; font-size: 0.9rem; }}
        th {{ background: #F9FAFB; font-weight: 700; }}
    </style></head>
    <body onload="window.print()">
        <h2>Stock Report</h2>
        <div style="color:#6B7280;margin-bottom:1.5rem;">Period: {from_date} to {to_date}</div>
        <table>
            <thead><tr><th>Item</th><th>Category</th><th>Unit</th><th>Rate</th><th>Opening</th><th>GRN</th><th>Consumed</th><th>Closing</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </body></html>"""
    return HttpResponse(html, content_type='text/html')
