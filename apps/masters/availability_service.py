import datetime
from django.utils import timezone
from django.db.models import Q, Count
from apps.employees.models import Employee, EmployeeAttendance
from apps.operations.models import Project, ProjectActivityInstance
from apps.masters.models import LeaveRequest, ActivityTask, TaskReassignmentLog


def _parse_date(val):
    if not val:
        return None
    if isinstance(val, datetime.date) and not isinstance(val, datetime.datetime):
        return val
    if isinstance(val, datetime.datetime):
        return val.date()
    if isinstance(val, str):
        val = val.strip().split('T')[0].split(' ')[0]
        try:
            return datetime.date.fromisoformat(val)
        except Exception:
            return None
    return None


class EmployeeAvailabilityService:
    """
    Unified service calculating multi-project employee availability,
    global workload across both ActivityTask and ProjectActivityInstance workflows,
    project team resolution, approved leave gates, and affected task lookups.
    """

    @classmethod
    def get_project_team_candidates(cls, project_id, target_date=None, exclude_employee_id=None, company_id=1):
        """
        Returns eligible replacement candidates strictly restricted to the specified project team.
        Candidate pool = project.site_manager + project.field_staff (JSON list).
        Computes global workload across all projects and checks approved leave on target_date.
        """
        project = Project.objects.filter(id=project_id).first()
        if not project:
            return []

        # Collect project team employee IDs
        team_ids = set()
        if project.site_manager:
            team_ids.add(int(project.site_manager))
        if isinstance(project.field_staff, list):
            for eid in project.field_staff:
                try:
                    team_ids.add(int(eid))
                except (ValueError, TypeError):
                    pass

        if exclude_employee_id:
            team_ids.discard(int(exclude_employee_id))

        if not team_ids:
            return []

        employees = Employee.objects.filter(
            id__in=team_ids,
            company_id=company_id,
            status='active'
        ).order_by('name')

        t_date = _parse_date(target_date) or timezone.localdate()

        candidates = []
        for emp in employees:
            avail_info = cls.calculate_employee_availability(
                employee_id=emp.id,
                target_date=t_date,
                company_id=company_id
            )

            # Determine project-specific role title
            project_roles = []
            if project.site_manager == emp.id:
                project_roles.append('Site Manager')
            if isinstance(project.field_staff, list) and (emp.id in project.field_staff or str(emp.id) in [str(x) for x in project.field_staff]):
                project_roles.append('Field Staff')

            role_label = ', '.join(project_roles) if project_roles else 'Team Member'

            candidates.append({
                'employee_id': emp.id,
                'employee_name': emp.name,
                'employee_code': f"EMP-{emp.id:04d}",
                'phone': emp.phone or '',
                'email': emp.email or '',
                'project_role': role_label,
                'is_site_manager': project.site_manager == emp.id,
                **avail_info
            })

        # Sorting logic:
        # 1. Selectable first (Available -> Warning/Busy -> On Leave)
        # 2. Fewer tasks on target date first
        # 3. Lower global pending workload first
        def sort_key(c):
            # Status ranking: Available (0), Busy (1), Half-Day Warning (2), On Leave (3)
            status_rank = 0
            if c['classification'] == 'Available':
                status_rank = 0
            elif c['classification'] == 'Busy':
                status_rank = 1
            elif c['classification'] == 'Half-Day Leave':
                status_rank = 2
            else:
                status_rank = 3

            return (
                0 if c['is_selectable'] else 1,
                status_rank,
                c['target_date_tasks_count'],
                c['global_workload']['total_pending_all']
            )

        candidates.sort(key=sort_key)
        return candidates

    @classmethod
    def calculate_employee_availability(cls, employee_id, target_date, company_id=1):
        """
        Calculates availability status, leave gate, attendance signal,
        and global workload across both workflows for a given employee on target_date.
        """
        t_date = _parse_date(target_date) or timezone.localdate()
        today = timezone.localdate()

        # 1. Check Approved Leave (Employee-Wide across all projects)
        active_leave = LeaveRequest.objects.filter(
            employee_id=employee_id,
            status='approved',
            start_date__lte=t_date,
            end_date__gte=t_date
        ).first()

        leave_status = 'None'
        days_count = 0.0
        is_on_leave = False
        is_half_day = False
        leave_reason = ''

        if active_leave:
            days_count = float(active_leave.days_count) if active_leave.days_count else 1.0
            leave_reason = active_leave.reason or ''
            if days_count <= 0.5:
                is_half_day = True
                leave_status = 'Half-Day'
            else:
                is_on_leave = True
                leave_status = 'Full-Day'

        # Also check pending leave for advisory warning
        has_pending_leave = False
        if not active_leave:
            pending_leave = LeaveRequest.objects.filter(
                employee_id=employee_id,
                status='pending',
                start_date__lte=t_date,
                end_date__gte=t_date
            ).first()
            if pending_leave:
                has_pending_leave = True

        # 2. Global Workload Calculation across ALL projects
        workload = cls.get_global_employee_workload(employee_id=employee_id, target_date=t_date)

        target_date_tasks_count = workload['activity_tasks']['date_count'] + workload['mobile_activities']['date_count']
        has_inprogress_today = (workload['activity_tasks']['date_inprogress'] + workload['mobile_activities']['date_inprogress']) > 0

        # 3. Attendance Signal (Supporting info)
        attendance_info = {
            'is_applicable': (t_date == today),
            'punched_in': False,
            'punch_in_time': None,
            'status_label': 'Not Applicable (Future Date)' if t_date > today else ('Past Date' if t_date < today else 'Not Punched In Today')
        }
        if t_date == today:
            att = EmployeeAttendance.objects.filter(
                employee_id=employee_id,
                punch_in__date=today
            ).order_by('-punch_in').first()
            if att:
                attendance_info['punched_in'] = True
                attendance_info['punch_in_time'] = att.punch_in.strftime('%H:%M') if att.punch_in else None
                attendance_info['status_label'] = f"Punched In at {attendance_info['punch_in_time']}"

        # 4. Classification & Selectability (Option A Policy: Half-Day warning, Full-day blocked)
        if is_on_leave:
            classification = 'On Leave'
            is_selectable = False
            availability_badge = {'label': 'On Leave', 'color': 'danger', 'desc': f'Full-day approved leave ({t_date})'}
        elif is_half_day:
            classification = 'Half-Day Leave'
            is_selectable = True  # Policy Option A: Admin can decide with amber warning
            availability_badge = {'label': 'Half-Day Leave', 'color': 'warning', 'desc': 'Approved 0.5 day leave on this date'}
        elif target_date_tasks_count > 0:
            classification = 'Busy'
            is_selectable = True
            availability_badge = {'label': f'Busy ({target_date_tasks_count} tasks)', 'color': 'warning', 'desc': f'{target_date_tasks_count} task(s) scheduled on this date'}
        else:
            classification = 'Available'
            is_selectable = True
            availability_badge = {'label': 'Available', 'color': 'success', 'desc': 'No conflicting tasks or leave on this date'}

        return {
            'target_date': str(t_date),
            'leave_status': leave_status,
            'is_on_leave': is_on_leave,
            'is_half_day': is_half_day,
            'has_pending_leave': has_pending_leave,
            'leave_reason': leave_reason,
            'classification': classification,
            'is_selectable': is_selectable,
            'availability_badge': availability_badge,
            'target_date_tasks_count': target_date_tasks_count,
            'has_inprogress_today': has_inprogress_today,
            'attendance': attendance_info,
            'global_workload': workload
        }

    @classmethod
    def get_global_employee_workload(cls, employee_id, target_date=None):
        """
        Calculates global workload across ALL projects, clearly separating:
        1. ActivityTask (Admin Activity Scheduling workflow)
        2. ProjectActivityInstance (Operations / Mobile form execution workflow)
        Avoids double-counting for employees in both primary and supporting roles.
        """
        t_date = _parse_date(target_date)

        # --- Workflow 1: ActivityTask ---
        # Query tasks where employee is primary assignee OR in assigned_staff JSON list
        at_base = ActivityTask.objects.filter(
            Q(assigned_to_id=employee_id) | Q(assigned_staff__contains=str(employee_id))
        ).distinct()

        at_pending = at_base.filter(status__in=['Pending', 'Scheduled']).count()
        at_inprogress = at_base.filter(status='In Progress').count()
        at_total_open = at_pending + at_inprogress

        at_date_count = 0
        at_date_inprogress = 0
        if t_date:
            at_date_qs = at_base.filter(task_date=t_date, status__in=['Pending', 'Scheduled', 'In Progress'])
            at_date_count = at_date_qs.count()
            at_date_inprogress = at_date_qs.filter(status='In Progress').count()

        # Project-wise breakdown for ActivityTasks
        at_projects = list(
            at_base.filter(status__in=['Pending', 'Scheduled', 'In Progress'])
            .values('project_id', 'project__project_name')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
        )

        # --- Workflow 2: ProjectActivityInstance ---
        pai_base = ProjectActivityInstance.objects.filter(assigned_employee_id=employee_id)

        pai_pending = pai_base.filter(status__in=['Pending', 'Unable to Complete']).count()
        pai_inprogress = pai_base.filter(status__in=['In Progress', 'Under Review']).count()
        pai_total_open = pai_pending + pai_inprogress

        pai_date_count = 0
        pai_date_inprogress = 0
        if t_date:
            pai_date_qs = pai_base.filter(scheduled_date=t_date, status__in=['Pending', 'In Progress', 'Under Review', 'Unable to Complete'])
            pai_date_count = pai_date_qs.count()
            pai_date_inprogress = pai_date_qs.filter(status__in=['In Progress', 'Under Review']).count()

        # Project-wise breakdown for ProjectActivityInstances
        pai_projects = list(
            pai_base.filter(status__in=['Pending', 'In Progress', 'Under Review', 'Unable to Complete'])
            .values('project_id', 'project__project_name')
            .annotate(cnt=Count('id'))
            .order_by('-cnt')
        )

        return {
            'activity_tasks': {
                'pending': at_pending,
                'inprogress': at_inprogress,
                'total_open': at_total_open,
                'date_count': at_date_count,
                'date_inprogress': at_date_inprogress,
                'projects': at_projects
            },
            'mobile_activities': {
                'pending': pai_pending,
                'inprogress': pai_inprogress,
                'total_open': pai_total_open,
                'date_count': pai_date_count,
                'date_inprogress': pai_date_inprogress,
                'projects': pai_projects
            },
            'total_pending_all': at_total_open + pai_total_open
        }

    @classmethod
    def get_affected_tasks_for_leave(cls, leave_request):
        """
        Discovers all tasks scheduled during the approved leave window for the employee.
        Searches both ActivityTask and ProjectActivityInstance workflows.
        Does NOT modify any task assignment. Read-only discovery.
        """
        emp_id = leave_request.employee_id
        s_date = leave_request.start_date
        e_date = leave_request.end_date

        if not s_date or not e_date or not emp_id:
            return {'activity_tasks': [], 'project_activity_instances': [], 'total_affected': 0}

        # 1. ActivityTasks overlapping leave period (primary assignee on leave)
        at_qs = ActivityTask.objects.filter(
            company_id=leave_request.company_id,
            assigned_to_id=emp_id,
            task_date__gte=s_date,
            task_date__lte=e_date,
            status__in=['Pending', 'Scheduled', 'In Progress']
        ).select_related('project', 'activity', 'assigned_to').order_by('task_date', 'id')

        at_items = []
        for t in at_qs:
            at_items.append({
                'id': t.id,
                'workflow_type': 'activity_task',
                'task_code': t.task_code or f"TSK-{t.id}",
                'title': t.task_title,
                'activity_title': t.activity.activity_title if t.activity else 'Activity',
                'project_id': t.project_id,
                'project_name': (t.project.project_name or t.project.client_name) if t.project else 'General',
                'task_date': str(t.task_date),
                'due_datetime': t.due_datetime.strftime('%d %b, %H:%M') if t.due_datetime else '—',
                'status': t.status,
                'priority': t.priority,
                'is_primary': True,
                'assigned_to_id': t.assigned_to_id,
                'assigned_to_name': t.assigned_to.name if t.assigned_to else 'Unassigned'
            })

        # 2. ProjectActivityInstances overlapping leave period
        pai_qs = ProjectActivityInstance.objects.filter(
            company_id=leave_request.company_id,
            assigned_employee_id=emp_id,
            scheduled_date__gte=s_date,
            scheduled_date__lte=e_date,
            status__in=['Pending', 'In Progress', 'Unable to Complete']
        ).select_related('project', 'activity', 'assigned_employee').order_by('scheduled_date', 'id')

        pai_items = []
        for inst in pai_qs:
            pai_items.append({
                'id': inst.id,
                'workflow_type': 'project_activity_instance',
                'task_code': f"ACT-{inst.id:04d}",
                'title': inst.activity.activity_title if inst.activity else 'Operational Activity',
                'activity_title': inst.activity.activity_title if inst.activity else 'Operational Activity',
                'project_id': inst.project_id,
                'project_name': (inst.project.project_name or inst.project.client_name) if inst.project else 'General',
                'task_date': str(inst.scheduled_date),
                'due_datetime': str(inst.due_date) if inst.due_date else '—',
                'status': inst.status,
                'photos_count': inst.photos.count(),
                'has_issues': inst.issues.exists(),
                'actual_start_time': inst.actual_start_time.strftime('%d %b, %H:%M') if inst.actual_start_time else None,
                'assigned_to_id': inst.assigned_employee_id,
                'assigned_to_name': inst.assigned_employee.name if inst.assigned_employee else 'Unassigned'
            })

        return {
            'activity_tasks': at_items,
            'project_activity_instances': pai_items,
            'total_affected': len(at_items) + len(pai_items),
            'employee_name': leave_request.employee.name if leave_request.employee else 'Employee',
            'start_date': str(s_date),
            'end_date': str(e_date),
            'days_count': str(leave_request.days_count)
        }

    @classmethod
    def get_approved_leaves_reassignment_data(cls, company_id=1, search='', employee_id='', project_id='', date_from='', date_to=''):
        """
        Automatically fetches all approved leaves for the company and resolves:
        1. Employees with approved leaves (pending/rejected/cancelled excluded).
        2. Active tasks overlapping each approved leave window that still require reassignment.
        3. Tasks already reassigned during each approved leave window (from TaskReassignmentLog).
        """
        leaves_qs = LeaveRequest.objects.filter(
            company_id=company_id,
            status='approved'
        ).select_related('employee', 'project').order_by('-start_date', '-id')

        if employee_id and str(employee_id).isdigit():
            leaves_qs = leaves_qs.filter(employee_id=int(employee_id))

        d_from = _parse_date(date_from)
        d_to = _parse_date(date_to)
        if d_from:
            leaves_qs = leaves_qs.filter(end_date__gte=d_from)
        if d_to:
            leaves_qs = leaves_qs.filter(start_date__lte=d_to)

        approved_leaves = []
        pending_tasks = []
        reassigned_tasks = []

        search_low = (search or '').strip().lower()
        proj_filter_id = int(project_id) if project_id and str(project_id).isdigit() else None

        for leave in leaves_qs:
            emp = leave.employee
            if not emp:
                continue

            affected = cls.get_affected_tasks_for_leave(leave)
            combined_pending = []
            for t in affected['activity_tasks']:
                if proj_filter_id and t.get('project_id') != proj_filter_id:
                    continue
                combined_pending.append({
                    'leave_id': leave.id,
                    'leave_employee_id': emp.id,
                    'leave_employee_name': emp.name,
                    'leave_employee_code': f"EMP-{emp.id:04d}",
                    'leave_type': leave.leave_type,
                    'leave_start_date': str(leave.start_date),
                    'leave_end_date': str(leave.end_date),
                    'leave_days_count': str(leave.days_count),
                    'workflow_type': 'activity_task',
                    'workflow_label': 'Scheduled Task',
                    'task_id': t['id'],
                    'task_code': t['task_code'],
                    'project_id': t['project_id'],
                    'project_name': t['project_name'],
                    'activity_title': t['activity_title'],
                    'scheduled_date': t['task_date'],
                    'status': t['status'],
                    'assigned_employee_id': t['assigned_to_id'],
                    'assigned_employee_name': t['assigned_to_name'],
                })

            for inst in affected['project_activity_instances']:
                if proj_filter_id and inst.get('project_id') != proj_filter_id:
                    continue
                combined_pending.append({
                    'leave_id': leave.id,
                    'leave_employee_id': emp.id,
                    'leave_employee_name': emp.name,
                    'leave_employee_code': f"EMP-{emp.id:04d}",
                    'leave_type': leave.leave_type,
                    'leave_start_date': str(leave.start_date),
                    'leave_end_date': str(leave.end_date),
                    'leave_days_count': str(leave.days_count),
                    'workflow_type': 'project_activity_instance',
                    'workflow_label': 'Mobile Activity',
                    'task_id': inst['id'],
                    'task_code': inst['task_code'],
                    'project_id': inst['project_id'],
                    'project_name': inst['project_name'],
                    'activity_title': inst['activity_title'],
                    'scheduled_date': inst['task_date'],
                    'status': inst['status'],
                    'assigned_employee_id': inst['assigned_to_id'],
                    'assigned_employee_name': inst['assigned_to_name'],
                })

            # Already reassigned tasks for this employee during this leave window
            logs_qs = TaskReassignmentLog.objects.filter(
                company_id=company_id,
                previous_employee_id=emp.id,
                task_date__gte=leave.start_date,
                task_date__lte=leave.end_date,
            ).select_related(
                'project',
                'activity_task',
                'activity_task__activity',
                'activity_task__assigned_to',
                'project_activity_instance',
                'project_activity_instance__activity',
                'project_activity_instance__assigned_employee',
                'new_employee',
            ).order_by('-reassigned_at', '-id')

            if proj_filter_id:
                logs_qs = logs_qs.filter(project_id=proj_filter_id)

            seen_reassigned_keys = set()
            leave_reassigned = []
            for log in logs_qs:
                if log.workflow_type == 'activity_task' and log.activity_task:
                    task_obj = log.activity_task
                    t_key = ('activity_task', task_obj.id)
                    if t_key in seen_reassigned_keys:
                        continue
                    # Only treat as reassigned if current assignee is no longer the employee on leave
                    if task_obj.assigned_to_id == emp.id:
                        continue
                    seen_reassigned_keys.add(t_key)
                    t_code = task_obj.task_code or f"TSK-{task_obj.id}"
                    act_title = task_obj.activity.activity_title if task_obj.activity else task_obj.task_title
                    curr_emp_name = task_obj.assigned_to.name if task_obj.assigned_to else (log.new_employee_name or '—')
                    curr_status = task_obj.status
                    wf_label = 'Scheduled Task'
                    t_id = task_obj.id
                elif log.workflow_type == 'project_activity_instance' and log.project_activity_instance:
                    inst_obj = log.project_activity_instance
                    t_key = ('project_activity_instance', inst_obj.id)
                    if t_key in seen_reassigned_keys:
                        continue
                    if inst_obj.assigned_employee_id == emp.id:
                        continue
                    seen_reassigned_keys.add(t_key)
                    t_code = f"ACT-{inst_obj.id:04d}"
                    act_title = inst_obj.activity.activity_title if inst_obj.activity else 'Operational Activity'
                    curr_emp_name = inst_obj.assigned_employee.name if inst_obj.assigned_employee else (log.new_employee_name or '—')
                    curr_status = inst_obj.status
                    wf_label = 'Mobile Activity'
                    t_id = inst_obj.id
                else:
                    continue

                proj_name = (log.project.project_name or log.project.client_name) if log.project else 'General'
                leave_reassigned.append({
                    'leave_id': leave.id,
                    'leave_employee_id': emp.id,
                    'leave_employee_name': emp.name,
                    'leave_employee_code': f"EMP-{emp.id:04d}",
                    'leave_start_date': str(leave.start_date),
                    'leave_end_date': str(leave.end_date),
                    'leave_days_count': str(leave.days_count),
                    'workflow_type': log.workflow_type,
                    'workflow_label': wf_label,
                    'task_id': t_id,
                    'task_code': t_code,
                    'project_name': proj_name,
                    'activity_title': act_title,
                    'scheduled_date': str(log.task_date),
                    'previous_employee_name': log.previous_employee_name or emp.name,
                    'new_employee_name': curr_emp_name,
                    'task_status': curr_status,
                    'reassigned_by': log.reassigned_by,
                    'reassigned_at': log.reassigned_at.strftime('%d %b %Y, %H:%M') if log.reassigned_at else '—',
                    'reason': log.reason or '',
                })

            if search_low:
                emp_match = search_low in emp.name.lower() or search_low in f"emp-{emp.id:04d}"
                if not emp_match:
                    combined_pending = [
                        row for row in combined_pending
                        if search_low in row['task_code'].lower()
                        or search_low in row['project_name'].lower()
                        or search_low in row['activity_title'].lower()
                        or search_low in row['assigned_employee_name'].lower()
                    ]
                    leave_reassigned = [
                        row for row in leave_reassigned
                        if search_low in row['task_code'].lower()
                        or search_low in row['project_name'].lower()
                        or search_low in row['activity_title'].lower()
                        or search_low in row['new_employee_name'].lower()
                    ]
                    if not combined_pending and not leave_reassigned:
                        continue

            pending_tasks.extend(combined_pending)
            reassigned_tasks.extend(leave_reassigned)

            leave_proj_name = 'Not Assigned'
            if leave.project:
                leave_proj_name = leave.project.project_name or leave.project.client_name or f"Project #{leave.project.id}"

            approved_leaves.append({
                'leave_id': leave.id,
                'employee_id': emp.id,
                'employee_name': emp.name,
                'employee_code': f"EMP-{emp.id:04d}",
                'leave_type': leave.leave_type,
                'project_name': leave_proj_name,
                'start_date': leave.start_date,
                'end_date': leave.end_date,
                'start_date_str': str(leave.start_date),
                'end_date_str': str(leave.end_date),
                'days_count': str(leave.days_count),
                'status': leave.status,
                'pending_count': len(combined_pending),
                'reassigned_count': len(leave_reassigned),
                'total_affected': len(combined_pending) + len(leave_reassigned),
            })

        pending_tasks.sort(key=lambda x: (x['scheduled_date'], x['task_code']))

        return {
            'approved_leaves': approved_leaves,
            'pending_tasks': pending_tasks,
            'reassigned_tasks': reassigned_tasks,
            'approved_leaves_count': len(approved_leaves),
            'pending_count': len(pending_tasks),
            'reassigned_count': len(reassigned_tasks),
        }
