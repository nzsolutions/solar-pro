import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import Q, Count
from apps.masters.models import ActivitySchedule, ActivityTask, ActivityMaster
from apps.employees.models import Employee
from apps.operations.models import Project


class ActivityScheduleService:
    """
    Business service handling Activity Scheduling, Recurring Rules,
    Automatic Task Generation, Duplicate Prevention, and Overdue Auditing.
    """

    @classmethod
    def generate_tasks_for_schedule(cls, schedule, horizon_days=60):
        """
        Generates individual task instances for a single schedule up to horizon_days.
        Enforces strict duplicate prevention: never creates more than 1 task for the same schedule on the same date.
        """
        if not schedule.auto_generate_tasks or schedule.status in ['Completed', 'Cancelled']:
            return 0

        today = timezone.localdate()
        start = schedule.start_date
        max_end = schedule.end_date if schedule.end_date else (today + timedelta(days=horizon_days))
        
        # Don't look past the horizon
        limit_date = min(max_end, today + timedelta(days=horizon_days))

        target_dates = []

        if schedule.recurring_type == 'one_time':
            target_dates.append(start)
        elif schedule.recurring_type == 'daily':
            curr = start
            while curr <= limit_date:
                target_dates.append(curr)
                curr += timedelta(days=1)
        elif schedule.recurring_type == 'weekly':
            curr = start
            while curr <= limit_date:
                target_dates.append(curr)
                curr += timedelta(weeks=1)
        elif schedule.recurring_type == 'monthly':
            curr = start
            month_idx = 0
            while True:
                next_date = start + relativedelta(months=month_idx)
                if next_date > limit_date:
                    break
                target_dates.append(next_date)
                month_idx += 1

        created_count = 0

        # Existing task dates for this schedule
        existing_dates = set(
            ActivityTask.objects.filter(schedule=schedule).values_list('task_date', flat=True)
        )

        # Base due time
        time_part = schedule.start_time or datetime.time(10, 0)
        if isinstance(time_part, str):
            try:
                time_part = datetime.time.fromisoformat(time_part)
            except Exception:
                time_part = datetime.time(10, 0)

        for t_date in target_dates:
            if t_date in existing_dates:
                continue

            # Calculate due_datetime
            due_dt = timezone.make_aware(
                datetime.datetime.combine(t_date, time_part)
            ) if timezone.is_naive(datetime.datetime.combine(t_date, time_part)) else datetime.datetime.combine(t_date, time_part)

            # Determine initial task status
            initial_status = 'Pending'
            if t_date == today:
                initial_status = 'Scheduled'
            elif t_date < today:
                initial_status = 'Pending' # Will be identified as overdue

            try:
                task = ActivityTask.objects.create(
                    schedule=schedule,
                    activity=schedule.activity,
                    project=schedule.project,
                    task_title=f"{schedule.activity.activity_title} - {t_date.strftime('%d %b %Y')}",
                    task_date=t_date,
                    due_datetime=due_dt,
                    assigned_to=schedule.assigned_to,
                    assigned_staff=schedule.assigned_staff or [],
                    priority=schedule.priority,
                    status=initial_status,
                    company_id=schedule.company_id,
                )
                existing_dates.add(t_date)
                created_count += 1
            except IntegrityError:
                # Caught by unique_schedule_task_per_date constraint
                pass

        if created_count > 0:
            schedule.last_generated_date = today
            schedule.save(update_fields=['last_generated_date', 'updated_at'])

        return created_count

    @classmethod
    def generate_all_active_schedules(cls, horizon_days=60, company_id=None):
        """
        Batch processor generating tasks across all eligible active schedules.
        Safe for recurring execution / cron triggers.
        """
        qs = ActivitySchedule.objects.filter(
            auto_generate_tasks=True,
            status__in=['Pending', 'Scheduled', 'In Progress']
        )
        if company_id:
            qs = qs.filter(company_id=company_id)

        total_created = 0
        schedules_processed = 0

        for schedule in qs:
            cnt = cls.generate_tasks_for_schedule(schedule, horizon_days=horizon_days)
            total_created += cnt
            schedules_processed += 1

        return {
            'schedules_processed': schedules_processed,
            'tasks_created': total_created,
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    @classmethod
    def sync_schedule_update(cls, schedule):
        """
        Handles schedule updates without generating duplicate tasks.
        Updates pending future tasks to match new priorities, staff, or project,
        and generates new occurrences.
        """
        today = timezone.localdate()
        # Synchronize future pending/scheduled tasks with new attributes
        ActivityTask.objects.filter(
            schedule=schedule,
            status__in=['Pending', 'Scheduled'],
            task_date__gte=today
        ).update(
            activity=schedule.activity,
            project=schedule.project,
            assigned_to=schedule.assigned_to,
            assigned_staff=schedule.assigned_staff or [],
            priority=schedule.priority
        )

        # Generate any missing occurrences
        return cls.generate_tasks_for_schedule(schedule)

    @classmethod
    def get_kpis(cls, company_id=None):
        """
        Computes accurate KPI metrics for schedules and generated tasks.
        """
        today = timezone.localdate()
        now = timezone.now()

        schedules_qs = ActivitySchedule.objects.all()
        tasks_qs = ActivityTask.objects.all()

        if company_id:
            schedules_qs = schedules_qs.filter(company_id=company_id)
            tasks_qs = tasks_qs.filter(company_id=company_id)

        total_schedules = schedules_qs.count()
        scheduled_count = schedules_qs.filter(status='Scheduled').count()
        in_progress_count = schedules_qs.filter(status='In Progress').count()
        completed_count = schedules_qs.filter(status='Completed').count()
        pending_count = schedules_qs.filter(status='Pending').count()
        cancelled_count = schedules_qs.filter(status='Cancelled').count()

        # Overdue schedules: not completed/cancelled, and (deadline past or start_date past)
        overdue_schedules = schedules_qs.filter(
            ~Q(status__in=['Completed', 'Cancelled']),
            Q(deadline__lt=now) | Q(deadline__isnull=True, start_date__lt=today)
        ).count()

        total_tasks = tasks_qs.count()
        completed_tasks = tasks_qs.filter(status='Completed').count()
        in_progress_tasks = tasks_qs.filter(status='In Progress').count()
        pending_tasks = tasks_qs.filter(status='Pending').count()

        # Overdue tasks: not completed/cancelled, and task_date < today
        overdue_tasks = tasks_qs.filter(
            ~Q(status__in=['Completed', 'Cancelled']),
            Q(due_datetime__lt=now) | Q(due_datetime__isnull=True, task_date__lt=today)
        ).count()

        # Tasks scheduled for today
        today_tasks = tasks_qs.filter(task_date=today).count()

        # Upcoming in next 7 days
        next_week = today + timedelta(days=7)
        upcoming_tasks = tasks_qs.filter(
            task_date__gt=today,
            task_date__lte=next_week,
            status__in=['Pending', 'Scheduled']
        ).count()

        return {
            'total_schedules': total_schedules,
            'scheduled_count': scheduled_count,
            'in_progress_count': in_progress_count,
            'completed_count': completed_count,
            'pending_count': pending_count,
            'cancelled_count': cancelled_count,
            'overdue_schedules': overdue_schedules,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'in_progress_tasks': in_progress_tasks,
            'pending_tasks': pending_tasks,
            'overdue_tasks': overdue_tasks,
            'today_tasks': today_tasks,
            'upcoming_tasks': upcoming_tasks,
        }

    @classmethod
    def get_calendar_events(cls, start_date=None, end_date=None, company_id=None, employee_id=None, project_id=None, priority=None, status=None):
        """
        Formats scheduled activities and tasks for Calendar / Weekly / Monthly view.
        """
        tasks_qs = ActivityTask.objects.select_related('activity', 'project', 'assigned_to', 'schedule').all()

        if company_id:
            tasks_qs = tasks_qs.filter(company_id=company_id)
        if start_date:
            tasks_qs = tasks_qs.filter(task_date__gte=start_date)
        if end_date:
            tasks_qs = tasks_qs.filter(task_date__lte=end_date)
        if employee_id:
            tasks_qs = tasks_qs.filter(
                Q(assigned_to_id=employee_id) | Q(assigned_staff__contains=str(employee_id))
            )
        if project_id:
            tasks_qs = tasks_qs.filter(project_id=project_id)
        if priority:
            tasks_qs = tasks_qs.filter(priority=priority)
        if status:
            tasks_qs = tasks_qs.filter(status=status)

        events = []
        today = timezone.localdate()

        priority_colors = {
            'Urgent': {'bg': '#FEE2E2', 'border': '#EF4444', 'text': '#B91C1C'},
            'High': {'bg': '#FEF3E2', 'border': '#FF9F1C', 'text': '#C2410C'},
            'Medium': {'bg': '#EFF6FF', 'border': '#3B82F6', 'text': '#1D4ED8'},
            'Low': {'bg': '#F3F4F6', 'border': '#6B7280', 'text': '#374151'},
        }

        for task in tasks_qs:
            color = priority_colors.get(task.priority, priority_colors['Medium'])
            if task.status == 'Completed':
                color = {'bg': '#ECFDF5', 'border': '#10B981', 'text': '#047857'}
            elif task.is_overdue:
                color = {'bg': '#FEF2F2', 'border': '#DC2626', 'text': '#991B1B'}

            events.append({
                'id': task.id,
                'task_code': task.task_code,
                'title': task.task_title,
                'start': task.task_date.strftime('%Y-%m-%d'),
                'activity_title': task.activity.activity_title if task.activity else 'Activity',
                'project_name': task.project.project_name or task.project.client_name if task.project else 'General',
                'assigned_name': task.assigned_to.name if task.assigned_to else 'Unassigned',
                'date': task.task_date.strftime('%Y-%m-%d'),
                'time': task.due_datetime.strftime('%I:%M %p') if task.due_datetime else 'All Day',
                'priority': task.priority,
                'status': task.status,
                'is_overdue': task.is_overdue,
                'backgroundColor': color['border'],
                'borderColor': color['border'],
                'textColor': '#FFFFFF',
                'bg_color': color['bg'],
                'border_color': color['border'],
                'text_color': color['text'],
                'extendedProps': {
                    'task_code': task.task_code,
                    'status': task.status,
                    'priority': task.priority,
                    'assignee': task.assigned_to.name if task.assigned_to else 'Unassigned',
                    'description': f"Task: {task.task_code}\nActivity: {task.activity.activity_title if task.activity else ''}\nStatus: {task.status}\nPriority: {task.priority}\nAssigned: {task.assigned_to.name if task.assigned_to else 'Unassigned'}"
                }
            })

        return events
