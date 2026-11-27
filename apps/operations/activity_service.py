import calendar
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
from apps.operations.models import (
    Project,
    ProjectActivity,
    ProjectActivityInstance,
    ProjectActivityPhoto,
    ProjectActivityIssue,
)
from apps.masters.models import ActivityMaster
from apps.dynamic_forms.models import DynamicForm, FormSubmission


class ProjectActivityService:
    """
    Core business logic for Project Activities:
    1. Synchronizing selected activities and attached forms for a Project.
    2. Generating activity instances deterministically according to frequency and project dates.
    3. Reconciling future instances when dates/frequencies change without touching completed ones.
    4. Evaluating form validation and business exception rules during submission.
    """

    @classmethod
    def sync_project_activities(cls, project, activities_data, user_name='Admin'):
        """
        Takes project and list of dicts:
        activities_data = [
            {'activity_id': 1, 'form_id': 4, 'frequency': 'Monthly', 'estimated_duration': '2 hrs', 'assigned_employee_id': 5},
            ...
        ]
        Saves ProjectActivity records and triggers instance generation.
        """
        with transaction.atomic():
            company_id = project.company_id
            keep_activity_ids = []

            for item in activities_data:
                act_id = item.get('activity_id')
                if not act_id:
                    continue
                act_id = int(act_id)
                activity = ActivityMaster.objects.filter(id=act_id).first()
                if not activity:
                    continue

                form_id = item.get('form_id')
                form_obj = None
                if form_id and str(form_id).isdigit():
                    form_obj = DynamicForm.objects.filter(id=int(form_id)).first()

                frequency = item.get('frequency') or activity.default_frequency or 'Monthly'
                estimated_duration = item.get('estimated_duration') or activity.estimated_duration or ''

                defaults = {
                    'company_id': company_id,
                    'form': form_obj,
                    'frequency': frequency,
                    'start_date': project.start_date,
                    'end_date': project.end_date,
                    'estimated_duration': estimated_duration,
                    'status': 'active',
                    'added_by': user_name,
                }
                if 'assigned_employee_id' in item:
                    emp_id = item.get('assigned_employee_id')
                    defaults['assigned_employee_id'] = int(emp_id) if emp_id is not None and str(emp_id).isdigit() else None

                proj_act, created = ProjectActivity.objects.update_or_create(
                    project=project,
                    activity=activity,
                    defaults=defaults
                )
                keep_activity_ids.append(act_id)

                # Generate or reconcile instances for this activity
                cls.generate_instances_for_activity(proj_act)

            # Deactivate or remove unselected activities if no completed instances exist
            unselected = ProjectActivity.objects.filter(project=project).exclude(activity_id__in=keep_activity_ids)
            for old_pa in unselected:
                has_completed = old_pa.instances.filter(status__in=['Completed', 'In Progress']).exists()
                if not has_completed:
                    old_pa.delete()
                else:
                    # Keep history, but deactivate and remove unexecuted pending instances
                    old_pa.status = 'inactive'
                    old_pa.save(update_fields=['status', 'updated_at'])
                    old_pa.instances.filter(status='Pending').delete()

    @classmethod
    def generate_instances_for_activity(cls, project_activity):
        """
        Generates occurrences for a ProjectActivity based on start_date, end_date, and frequency.
        Uses the activity-wise assigned employee strictly without overwriting with generic project-level defaults.
        Safe to retry (idempotent). Preserves existing completed, in-progress, and reassigned records.
        """
        project = project_activity.project
        start_date = project_activity.start_date or project.start_date
        end_date = project_activity.end_date or project.end_date

        if not start_date or not end_date:
            return 0

        if start_date > end_date:
            return 0

        frequency = project_activity.frequency or 'Monthly'
        scheduled_dates = cls.compute_scheduled_dates(start_date, end_date, frequency)

        existing_instances = {inst.scheduled_date: inst for inst in project_activity.instances.all()}
        created_count = 0

        # Use only the activity-specific assigned employee; never assign generically to Site Manager or Field Staff
        activity_employee_id = project_activity.assigned_employee_id

        for s_date in scheduled_dates:
            if s_date in existing_instances:
                # Update frequency if pending; preserve existing instance employee assignment
                inst = existing_instances[s_date]
                if inst.status == 'Pending':
                    update_fields = ['frequency', 'updated_at']
                    if not inst.assigned_employee_id and activity_employee_id:
                        inst.assigned_employee_id = activity_employee_id
                        update_fields.append('assigned_employee')
                    inst.frequency = frequency
                    inst.save(update_fields=update_fields)
                continue

            ProjectActivityInstance.objects.create(
                company_id=project_activity.company_id,
                project_activity=project_activity,
                project=project,
                activity=project_activity.activity,
                scheduled_date=s_date,
                due_date=s_date,
                frequency=frequency,
                assigned_employee_id=activity_employee_id,
                status='Pending'
            )
            created_count += 1

        # Reconcile: delete pending instances that fall outside the new scheduled_dates
        for s_date, inst in existing_instances.items():
            if s_date not in scheduled_dates and inst.status == 'Pending':
                inst.delete()

        return created_count

    @staticmethod
    def compute_scheduled_dates(start_date, end_date, frequency):
        """
        Computes the list of scheduled dates in [start_date, end_date] according to frequency.
        Handles string inputs, leap years, month ends, and preserves exact project boundaries.
        """
        if isinstance(start_date, str):
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except Exception:
                start_date = datetime.fromisoformat(start_date).date()
        elif isinstance(start_date, datetime):
            start_date = start_date.date()

        if isinstance(end_date, str):
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except Exception:
                end_date = datetime.fromisoformat(end_date).date()
        elif isinstance(end_date, datetime):
            end_date = end_date.date()

        if not start_date or not end_date or start_date > end_date:
            return []

        # If project is defined as an anniversary term where end_date is the exact anniversary date
        # (e.g., Start Date: 01-01-2026, End Date: 01-01-2027 representing a 1-year project),
        # the operational horizon ends on the final day of the preceding period (e.g., 2026-12-31),
        # yielding exactly 365 daily, 52 weekly, 12 monthly, and 1 yearly occurrences.
        effective_end = end_date
        if (
            end_date.month == start_date.month
            and end_date.day == start_date.day
            and end_date.year > start_date.year
        ):
            effective_end = end_date - timedelta(days=1)

        dates = []
        freq = (frequency or '').strip()

        if freq == 'Daily':
            cur = start_date
            while cur <= effective_end:
                dates.append(cur)
                cur += timedelta(days=1)

        elif freq == 'Weekly':
            # Generate one occurrence for each week in the project date range (e.g. 52 weeks in 365 days)
            total_days = (effective_end - start_date).days + 1
            num_weeks = max(1, total_days // 7)
            for w in range(num_weeks):
                w_date = start_date + timedelta(weeks=w)
                if w_date <= effective_end:
                    dates.append(w_date)

        elif freq == 'Monthly':
            # One entry per calendar month within range.
            # Anchor to start_date.day, clamped to last day of each month.
            target_day = start_date.day
            cur_year = start_date.year
            cur_month = start_date.month

            while True:
                max_day = calendar.monthrange(cur_year, cur_month)[1]
                day = min(target_day, max_day)
                cand_date = date(cur_year, cur_month, day)

                if cand_date < start_date:
                    cand_date = start_date

                if cand_date > effective_end:
                    break

                dates.append(cand_date)

                # Move to next month
                if cur_month == 12:
                    cur_month = 1
                    cur_year += 1
                else:
                    cur_month += 1

                # Check if next month's start is already beyond effective_end
                if date(cur_year, cur_month, 1) > effective_end:
                    break

        elif freq == 'Quarterly':
            cur = start_date
            while cur <= effective_end:
                dates.append(cur)
                cur = cur + relativedelta(months=3)

        elif freq == 'Half-Yearly':
            cur = start_date
            while cur <= effective_end:
                dates.append(cur)
                cur = cur + relativedelta(months=6)

        elif freq == 'Yearly':
            cur = start_date
            while cur <= effective_end:
                dates.append(cur)
                cur = cur + relativedelta(years=1)

        else: # 'As Required' or custom
            # Generate at least one instance on start_date
            dates.append(start_date)

        return sorted(list(set(dates)))
