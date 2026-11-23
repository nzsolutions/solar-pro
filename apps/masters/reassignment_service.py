import datetime
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.employees.models import Employee
from apps.operations.models import Project, ProjectActivityInstance
from apps.masters.models import LeaveRequest, ActivityTask, TaskReassignmentLog
from apps.masters.availability_service import EmployeeAvailabilityService, _parse_date


class ConcurrencyConflictError(ValidationError):
    """Raised when an optimistic concurrency conflict is detected."""
    pass


class TaskReassignmentService:
    """
    Handles atomic, safe manual task reassignment for both:
    1. ActivityTask (Admin Activity Scheduling workflow)
    2. ProjectActivityInstance (Operations / Mobile execution workflow)
    Enforces optimistic concurrency checks, project team boundaries, leave verification,
    In-Progress handover policy, and audit logging.
    """

    @classmethod
    def reassign_activity_task(cls, task_id, new_employee_id, admin_user, reason=None, handover_remarks=None, expected_previous_employee_id=None, company_id=1):
        """
        Reassigns an ActivityTask to a new employee.
        Enforces atomic transaction with row locking (select_for_update) and optimistic concurrency check.
        STRICT REQUIREMENT: Can only reassign if current assignee is on approved leave overlapping task_date.
        """
        with transaction.atomic():
            task = ActivityTask.objects.select_for_update().filter(id=task_id, company_id=company_id).first()
            if not task:
                raise ValidationError("Activity Task not found.")

            # Optimistic Concurrency Check: Verify task assignee hasn't changed since client loaded it
            prev_emp = task.assigned_to
            prev_emp_id = prev_emp.id if prev_emp else None
            prev_emp_name = prev_emp.name if prev_emp else 'Unassigned'

            if expected_previous_employee_id is not None and str(expected_previous_employee_id).strip() != '':
                try:
                    exp_id = int(expected_previous_employee_id)
                except (ValueError, TypeError):
                    exp_id = None
                if prev_emp_id != exp_id:
                    raise ConcurrencyConflictError(
                        "Conflict: This task has already been reassigned by another administrator. Please refresh the task and try again."
                    )

            # Rule: Reassignment is ONLY permitted when the assigned employee has approved leave overlapping task_date
            if not prev_emp_id:
                raise ValidationError("Cannot perform leave-based reassignment on an unassigned task.")

            has_approved_leave = LeaveRequest.objects.filter(
                employee_id=prev_emp_id,
                status='approved',
                start_date__lte=task.task_date,
                end_date__gte=task.task_date
            ).exists()
            if not has_approved_leave:
                raise ValidationError(
                    f"Reassignment not allowed: {prev_emp_name} does not have an approved leave covering {task.task_date}. "
                    "Task reassignment is restricted solely to approved leave coverage."
                )

            # Rule: Completed and Cancelled tasks cannot be reassigned
            if task.status in ['Completed', 'Cancelled']:
                raise ValidationError(f"Cannot reassign a task that is already {task.status}.")

            # Rule: In-Progress tasks require handover remark (Policy Option A)
            if task.status == 'In Progress':
                if not handover_remarks or not handover_remarks.strip():
                    raise ValidationError("A handover remark is mandatory when reassigning an In-Progress task.")

            # Validate target project exists
            project = task.project
            if not project:
                raise ValidationError("Task does not have an associated project.")

            # Validate new employee exists and is active
            new_emp = Employee.objects.filter(id=new_employee_id, company_id=company_id, status='active').first()
            if not new_emp:
                raise ValidationError("Selected replacement employee not found or inactive.")

            # Rule: Candidate must belong to the same project team
            team_ids = set()
            if project.site_manager:
                team_ids.add(int(project.site_manager))
            if isinstance(project.field_staff, list):
                for eid in project.field_staff:
                    try:
                        team_ids.add(int(eid))
                    except (ValueError, TypeError):
                        pass

            if new_emp.id not in team_ids:
                raise ValidationError(f"Employee {new_emp.name} is not a member of {project.project_name or 'the project'} team.")

            # Rule: Candidate cannot be on approved full-day leave on task_date
            on_leave = LeaveRequest.objects.filter(
                employee_id=new_emp.id,
                status='approved',
                start_date__lte=task.task_date,
                end_date__gte=task.task_date
            ).first()
            if on_leave:
                days_cnt = float(on_leave.days_count) if on_leave.days_count else 1.0
                if days_cnt > 0.5:
                    raise ValidationError(f"Cannot reassign: {new_emp.name} has approved full-day leave on {task.task_date}.")

            prev_emp = task.assigned_to
            prev_emp_id = prev_emp.id if prev_emp else None
            prev_emp_name = prev_emp.name if prev_emp else 'Unassigned'

            if prev_emp_id == new_emp.id:
                raise ValidationError(f"{new_emp.name} is already assigned as the primary employee for this task.")

            # Handle assigned_staff JSON list:
            # Since reassignment is strictly due to approved leave, the employee on leave is always removed from supporting staff.
            current_staff = list(task.assigned_staff) if isinstance(task.assigned_staff, list) else []
            clean_staff = []
            for s in current_staff:
                try:
                    clean_staff.append(int(s))
                except (ValueError, TypeError):
                    pass

            # 1. Remove new employee from supporting list if present
            if new_emp.id in clean_staff:
                clean_staff.remove(new_emp.id)

            # 2. Remove previous employee on leave from supporting list
            if prev_emp_id and prev_emp_id in clean_staff:
                clean_staff.remove(prev_emp_id)

            # Update ActivityTask
            task.assigned_to = new_emp
            task.assigned_staff = clean_staff
            task.save(update_fields=['assigned_to', 'assigned_staff', 'updated_at'])

            # Create Audit Log
            admin_identifier = str(admin_user) if admin_user else 'Admin'
            log = TaskReassignmentLog.objects.create(
                company_id=company_id,
                workflow_type='activity_task',
                activity_task=task,
                project=project,
                previous_employee=prev_emp,
                previous_employee_name=prev_emp_name,
                new_employee=new_emp,
                new_employee_name=new_emp.name,
                reassigned_by=admin_identifier,
                task_date=task.task_date,
                reason=reason or 'Manual task reassignment by Admin',
                handover_remarks=handover_remarks if task.status == 'In Progress' else None
            )

            return {
                'success': True,
                'message': f"Task {task.task_code or task.id} reassigned from {prev_emp_name} to {new_emp.name}.",
                'task_id': task.id,
                'task_code': task.task_code,
                'previous_employee': prev_emp_name,
                'new_employee': new_emp.name,
                'log_id': log.id
            }

    @classmethod
    def reassign_project_activity_instance(cls, instance_id, new_employee_id, admin_user, reason=None, handover_remarks=None, expected_previous_employee_id=None, company_id=1):
        """
        Reassigns a ProjectActivityInstance to a new employee.
        Preserves all existing photos, form answers, issues, and actual start times.
        Enforces atomic transaction with row locking (select_for_update) and optimistic concurrency check.
        """
        with transaction.atomic():
            inst = ProjectActivityInstance.objects.select_for_update().filter(id=instance_id, company_id=company_id).first()
            if not inst:
                raise ValidationError("Project Activity Instance not found.")

            # Optimistic Concurrency Check: Verify activity instance assignee hasn't changed since client loaded it
            prev_emp = inst.assigned_employee
            prev_emp_id = prev_emp.id if prev_emp else None
            prev_emp_name = prev_emp.name if prev_emp else 'Unassigned'

            if expected_previous_employee_id is not None and str(expected_previous_employee_id).strip() != '':
                try:
                    exp_id = int(expected_previous_employee_id)
                except (ValueError, TypeError):
                    exp_id = None
                if prev_emp_id != exp_id:
                    raise ConcurrencyConflictError(
                        "Conflict: This activity has already been reassigned by another administrator. Please refresh the activity and try again."
                    )

            # Rule: Reassignment is ONLY permitted when the assigned employee has approved leave overlapping scheduled_date
            if not prev_emp_id:
                raise ValidationError("Cannot perform leave-based reassignment on an unassigned activity occurrence.")

            has_approved_leave = LeaveRequest.objects.filter(
                employee_id=prev_emp_id,
                status='approved',
                start_date__lte=inst.scheduled_date,
                end_date__gte=inst.scheduled_date
            ).exists()
            if not has_approved_leave:
                raise ValidationError(
                    f"Reassignment not allowed: {prev_emp_name} does not have an approved leave covering {inst.scheduled_date}. "
                    "Task reassignment is restricted solely to approved leave coverage."
                )

            # Rule: Completed, Under Review, or Cancelled instances cannot be reassigned
            if inst.status in ['Completed', 'Under Review', 'Rejected']:
                raise ValidationError(f"Cannot reassign an activity instance that is {inst.status}.")

            # Rule: In-Progress instances require handover remark (Policy Option A)
            if inst.status == 'In Progress':
                if not handover_remarks or not handover_remarks.strip():
                    raise ValidationError("A handover remark is mandatory when reassigning an In-Progress mobile activity.")

            project = inst.project
            if not project:
                raise ValidationError("Activity instance does not have an associated project.")

            # Validate new employee exists and is active
            new_emp = Employee.objects.filter(id=new_employee_id, company_id=company_id, status='active').first()
            if not new_emp:
                raise ValidationError("Selected replacement employee not found or inactive.")

            # Rule: Candidate must belong to the same project team
            team_ids = set()
            if project.site_manager:
                team_ids.add(int(project.site_manager))
            if isinstance(project.field_staff, list):
                for eid in project.field_staff:
                    try:
                        team_ids.add(int(eid))
                    except (ValueError, TypeError):
                        pass

            if new_emp.id not in team_ids:
                raise ValidationError(f"Employee {new_emp.name} is not a member of {project.project_name or 'the project'} team.")

            # Rule: Candidate cannot be on approved full-day leave on scheduled_date
            on_leave = LeaveRequest.objects.filter(
                employee_id=new_emp.id,
                status='approved',
                start_date__lte=inst.scheduled_date,
                end_date__gte=inst.scheduled_date
            ).first()
            if on_leave:
                days_cnt = float(on_leave.days_count) if on_leave.days_count else 1.0
                if days_cnt > 0.5:
                    raise ValidationError(f"Cannot reassign: {new_emp.name} has approved full-day leave on {inst.scheduled_date}.")

            prev_emp = inst.assigned_employee
            prev_emp_id = prev_emp.id if prev_emp else None
            prev_emp_name = prev_emp.name if prev_emp else 'Unassigned'

            if prev_emp_id == new_emp.id:
                raise ValidationError(f"{new_emp.name} is already assigned to this activity instance.")

            # Update assigned_employee; strictly preserve photos, submissions, issues, and timestamps
            inst.assigned_employee = new_emp
            inst.save(update_fields=['assigned_employee', 'updated_at'])

            # Create Audit Log
            admin_identifier = str(admin_user) if admin_user else 'Admin'
            log = TaskReassignmentLog.objects.create(
                company_id=company_id,
                workflow_type='project_activity_instance',
                project_activity_instance=inst,
                project=project,
                previous_employee=prev_emp,
                previous_employee_name=prev_emp_name,
                new_employee=new_emp,
                new_employee_name=new_emp.name,
                reassigned_by=admin_identifier,
                task_date=inst.scheduled_date,
                reason=reason or 'Manual task reassignment by Admin',
                handover_remarks=handover_remarks if inst.status == 'In Progress' else None
            )

            return {
                'success': True,
                'message': f"Activity instance #{inst.id} reassigned from {prev_emp_name} to {new_emp.name}.",
                'instance_id': inst.id,
                'previous_employee': prev_emp_name,
                'new_employee': new_emp.name,
                'log_id': log.id
            }
