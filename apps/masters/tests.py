import datetime
from unittest.mock import patch
from django.test import TestCase, Client
from django.utils import timezone
from apps.employees.models import Employee
from apps.operations.models import Project, ProjectActivity, ProjectActivityInstance
from apps.dynamic_forms.models import DynamicForm
from apps.masters.models import (
    ActivityMaster,
    ActivitySchedule,
    ActivityTask,
    LeaveRequest,
    TaskReassignmentLog,
)
from apps.masters.availability_service import EmployeeAvailabilityService


class ActivitySchedulingApprovedLeaveReassignmentTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.today = timezone.localdate()
        self.leave_start = self.today + datetime.timedelta(days=4)
        self.leave_end = self.today + datetime.timedelta(days=5)

        self.emp_leave = Employee.objects.create(
            id=501,
            name="Rahul Sharma",
            app_username="rahul501",
            email="rahul501@test.local",
            company_id=1,
            status='active',
            fcm_token="token_rahul_501"
        )
        self.emp_replacement = Employee.objects.create(
            id=502,
            name="Amit Patel",
            app_username="amit502",
            email="amit502@test.local",
            company_id=1,
            status='active',
            fcm_token="token_amit_502"
        )
        self.emp_inactive = Employee.objects.create(
            id=503,
            name="Inactive Tech",
            app_username="inactive503",
            company_id=1,
            status='inactive',
            fcm_token="token_inactive_503"
        )
        self.emp_unrelated = Employee.objects.create(
            id=504,
            name="Unrelated Staff",
            app_username="unrelated504",
            company_id=1,
            status='active',
            fcm_token="token_unrelated_504"
        )
        self.emp_no_tasks = Employee.objects.create(
            id=505,
            name="Sneha Joshi",
            app_username="sneha505",
            company_id=1,
            status='active',
            fcm_token="token_sneha_505"
        )

        self.project = Project.objects.create(
            id=510,
            project_name="Solar test 2",
            client_name="Solar test 2",
            site_manager=self.emp_leave.id,
            field_staff=[self.emp_replacement.id, self.emp_inactive.id],
            company_id=1,
            status='in_progress'
        )
        self.other_project = Project.objects.create(
            id=511,
            project_name="Unrelated Solar Site",
            client_name="Other Corp",
            site_manager=self.emp_unrelated.id,
            field_staff=[],
            company_id=1,
            status='in_progress'
        )

        self.activity = ActivityMaster.objects.create(
            id=520,
            activity_title="Solar Panel Cleaning",
            activity_category="Cleaning",
            company_id=1,
            status='active'
        )
        self.form = DynamicForm.objects.create(
            id=530,
            company_id=1,
            form_name="Panel Cleaning Checklist",
            form_schema={"sections": []},
            is_active=1
        )
        self.proj_activity = ProjectActivity.objects.create(
            project=self.project,
            activity=self.activity,
            form=self.form,
            frequency="Daily",
            status="active",
            company_id=1
        )

        self.activity_2 = ActivityMaster.objects.create(
            id=521,
            activity_title="Inverter Visual Check",
            activity_category="Inspection",
            company_id=1,
            status='active'
        )
        self.proj_activity_2 = ProjectActivity.objects.create(
            project=self.project,
            activity=self.activity_2,
            form=self.form,
            frequency="Daily",
            status="active",
            company_id=1
        )

        # Two pending mobile project activity instances overlapping leave
        self.inst_1 = ProjectActivityInstance.objects.create(
            id=526,
            project_activity=self.proj_activity,
            project=self.project,
            activity=self.activity,
            scheduled_date=self.leave_start,
            due_date=self.leave_start,
            assigned_employee=self.emp_leave,
            status="Pending",
            company_id=1
        )
        self.inst_2 = ProjectActivityInstance.objects.create(
            id=527,
            project_activity=self.proj_activity,
            project=self.project,
            activity=self.activity,
            scheduled_date=self.leave_end,
            due_date=self.leave_end,
            assigned_employee=self.emp_leave,
            status="Pending",
            company_id=1
        )
        # Completed instance during leave (must NOT appear as requiring reassignment)
        self.inst_completed = ProjectActivityInstance.objects.create(
            id=528,
            project_activity=self.proj_activity_2,
            project=self.project,
            activity=self.activity_2,
            scheduled_date=self.leave_start,
            assigned_employee=self.emp_leave,
            status="Completed",
            company_id=1
        )
        # Future instance outside leave period (must NOT appear)
        self.inst_outside_date = ProjectActivityInstance.objects.create(
            id=529,
            project_activity=self.proj_activity,
            project=self.project,
            activity=self.activity,
            scheduled_date=self.leave_end + datetime.timedelta(days=5),
            assigned_employee=self.emp_leave,
            status="Pending",
            company_id=1
        )
        # Unrelated employee's instance during same dates (must NOT appear)
        self.other_pa = ProjectActivity.objects.create(
            project=self.other_project,
            activity=self.activity,
            frequency="Daily",
            status="active",
            company_id=1
        )
        self.inst_unrelated = ProjectActivityInstance.objects.create(
            id=530,
            project_activity=self.other_pa,
            project=self.other_project,
            activity=self.activity,
            scheduled_date=self.leave_start,
            assigned_employee=self.emp_unrelated,
            status="Pending",
            company_id=1
        )

        # Admin session login
        session = self.client.session
        session['user_id'] = 1
        session['is_admin'] = 1
        session['name'] = 'Admin'
        session['company_id'] = 1
        session.save()

    def test_buttons_removed_and_only_approved_leaves_displayed(self):
        # Create approved, pending, and rejected leaves
        LeaveRequest.objects.create(
            employee=self.emp_leave,
            project=self.project,
            leave_type="Casual Leave",
            start_date=self.leave_start,
            end_date=self.leave_end,
            days_count=2.0,
            reason="Family event",
            status="approved",
            company_id=1
        )
        LeaveRequest.objects.create(
            employee=self.emp_no_tasks,
            project=self.project,
            leave_type="Sick Leave",
            start_date=self.leave_start,
            end_date=self.leave_start,
            days_count=1.0,
            reason="Checkup",
            status="approved",
            company_id=1
        )
        LeaveRequest.objects.create(
            employee=self.emp_unrelated,
            project=self.other_project,
            leave_type="Casual Leave",
            start_date=self.leave_start,
            end_date=self.leave_start,
            days_count=1.0,
            reason="Pending leave should be excluded",
            status="pending",
            company_id=1
        )
        LeaveRequest.objects.create(
            employee=self.emp_replacement,
            project=self.project,
            leave_type="Casual Leave",
            start_date=self.leave_start,
            end_date=self.leave_start,
            days_count=1.0,
            reason="Rejected leave should be excluded",
            status="rejected",
            company_id=1
        )

        resp = self.client.get('/admin/activity-schedules')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')

        # Unnecessary buttons removed
        self.assertNotIn('Generate Tasks Now', html)
        self.assertNotIn('Schedule Activity', html)

        # Context verification: only 2 approved leaves
        self.assertEqual(resp.context['approved_leaves_count'], 2)
        approved_names = [lv['employee_name'] for lv in resp.context['approved_leaves']]
        self.assertIn('Rahul Sharma', approved_names)
        self.assertIn('Sneha Joshi', approved_names)
        self.assertNotIn('Unrelated Staff', approved_names)
        self.assertNotIn('Amit Patel', approved_names)

        # Pending reassignment tasks: strictly inst_1 (526) and inst_2 (527)
        pending_ids = [t['task_id'] for t in resp.context['pending_reassignment_tasks']]
        self.assertEqual(sorted(pending_ids), [self.inst_1.id, self.inst_2.id])
        self.assertNotIn(self.inst_completed.id, pending_ids)
        self.assertNotIn(self.inst_outside_date.id, pending_ids)
        self.assertNotIn(self.inst_unrelated.id, pending_ids)

        # Empty state for employee with no affected tasks
        self.assertIn('No Affected Tasks', html)

    @patch('apps.expenses.views.send_fcm_notification')
    def test_end_to_end_leave_approval_reassignment_notification_and_refresh(self, mock_fcm):
        # 1. Create pending leave and approve it via Admin endpoint
        leave = LeaveRequest.objects.create(
            employee=self.emp_leave,
            project=self.project,
            leave_type="Casual Leave",
            start_date=self.leave_start,
            end_date=self.leave_end,
            days_count=2.0,
            reason="Personal travel",
            status="pending",
            company_id=1
        )
        approve_resp = self.client.post(f'/admin/leave-management/{leave.id}/approve', {'admin_remarks': 'Approved'})
        self.assertEqual(approve_resp.status_code, 302)
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'approved')

        # 2. Open Activity Scheduling manually -> automatically shows approved leave & both tasks
        sched_resp = self.client.get('/admin/activity-schedules')
        self.assertEqual(sched_resp.status_code, 200)
        self.assertEqual(sched_resp.context['pending_reassignment_count'], 2)
        self.assertEqual(sched_resp.context['reassigned_count'], 0)

        # 3. Fetch candidates for inst_1 -> only Amit Patel (project team, active, not on leave)
        cand_resp = self.client.get(
            f'/admin/reassignment/candidates?workflow_type=project_activity_instance&task_id={self.inst_1.id}'
        )
        self.assertEqual(cand_resp.status_code, 200)
        cand_data = cand_resp.json()
        self.assertTrue(cand_data['success'])
        cand_ids = [c['employee_id'] for c in cand_data['candidates']]
        self.assertEqual(cand_ids, [self.emp_replacement.id])
        self.assertNotIn(self.emp_leave.id, cand_ids)
        self.assertNotIn(self.emp_inactive.id, cand_ids)
        self.assertNotIn(self.emp_unrelated.id, cand_ids)

        # 4. Execute reassignment for inst_1
        initial_count = ProjectActivityInstance.objects.count()
        exec_resp = self.client.post('/admin/reassignment/execute', {
            'workflow_type': 'project_activity_instance',
            'task_id': self.inst_1.id,
            'new_employee_id': self.emp_replacement.id,
            'expected_previous_employee_id': self.emp_leave.id,
            'reason': 'Leave coverage'
        })
        self.assertEqual(exec_resp.status_code, 200)
        exec_json = exec_resp.json()
        self.assertTrue(exec_json['success'])
        self.assertTrue(exec_json['notification_sent'])
        self.assertEqual(exec_json['new_employee'], 'Amit Patel')

        # Ensure no duplicate task created and original attributes preserved
        self.assertEqual(ProjectActivityInstance.objects.count(), initial_count)
        self.inst_1.refresh_from_db()
        self.assertEqual(self.inst_1.assigned_employee_id, self.emp_replacement.id)
        self.assertEqual(self.inst_1.project_id, self.project.id)
        self.assertEqual(self.inst_1.activity_id, self.activity.id)
        self.assertEqual(self.inst_1.scheduled_date, self.leave_start)
        self.assertEqual(self.inst_1.project_activity.form_id, self.form.id)

        # Verify FCM notification sent once with project name, activity title, date, reassignment info
        self.assertEqual(mock_fcm.call_count, 1)
        fcm_token, notif_title, notif_body = mock_fcm.call_args[0]
        self.assertEqual(fcm_token, 'token_amit_502')
        self.assertIn('Solar Panel Cleaning', notif_title)
        self.assertIn('Solar test 2', notif_body)
        self.assertIn('Solar Panel Cleaning', notif_body)
        self.assertIn(str(self.leave_start), notif_body)
        self.assertIn('Rahul Sharma', notif_body)

        # 5. Repeated request must fail (409) and NOT trigger duplicate notification
        dup_resp = self.client.post('/admin/reassignment/execute', {
            'workflow_type': 'project_activity_instance',
            'task_id': self.inst_1.id,
            'new_employee_id': self.emp_replacement.id,
            'expected_previous_employee_id': self.emp_leave.id,
            'reason': 'Duplicate click'
        })
        self.assertEqual(dup_resp.status_code, 409)
        self.assertEqual(mock_fcm.call_count, 1)

        # 6. Mobile app visibility: replacement employee sees inst_1; leave employee no longer sees inst_1
        mobile_client = Client()
        mob_new = mobile_client.get(f'/api/get-employee-activities?employee_id={self.emp_replacement.id}').json()
        mob_new_ids = [item['id'] for item in mob_new['data']]
        self.assertIn(self.inst_1.id, mob_new_ids)

        mob_old = mobile_client.get(f'/api/get-employee-activities?employee_id={self.emp_leave.id}').json()
        mob_old_ids = [item['id'] for item in mob_old['data']]
        self.assertNotIn(self.inst_1.id, mob_old_ids)
        self.assertIn(self.inst_2.id, mob_old_ids)

        # Also verify replacement employee can start/execute the reassigned activity in mobile workflow
        start_resp = mobile_client.post('/api/start-activity-instance', {
            'emp_id': self.emp_replacement.id,
            'instance_id': self.inst_1.id,
        })
        self.assertEqual(start_resp.status_code, 200)
        self.inst_1.refresh_from_db()
        self.assertEqual(self.inst_1.status, 'In Progress')

        # 7. Refresh Activity Scheduling: inst_1 moved out of Pending Reassignment into Reassigned; inst_2 still Pending
        refresh_resp = self.client.get('/admin/activity-schedules')
        self.assertEqual(refresh_resp.status_code, 200)
        pending_ids_after = [t['task_id'] for t in refresh_resp.context['pending_reassignment_tasks']]
        reassigned_ids_after = [r['task_id'] for r in refresh_resp.context['reassigned_tasks']]
        self.assertEqual(pending_ids_after, [self.inst_2.id])
        self.assertEqual(reassigned_ids_after, [self.inst_1.id])
        self.assertEqual(refresh_resp.context['reassigned_tasks'][0]['new_employee_name'], 'Amit Patel')
        self.assertEqual(refresh_resp.context['reassigned_tasks'][0]['task_status'], 'In Progress')

        # Unrelated task remains untouched
        self.inst_unrelated.refresh_from_db()
        self.assertEqual(self.inst_unrelated.assigned_employee_id, self.emp_unrelated.id)

    @patch('apps.expenses.views.send_fcm_notification')
    def test_activity_task_overlap_reassignment_and_multiple_leaves(self, mock_fcm):
        # Approved leave for emp_leave AND a second approved leave for emp_unrelated
        LeaveRequest.objects.create(
            employee=self.emp_leave,
            project=self.project,
            leave_type="Casual Leave",
            start_date=self.leave_start,
            end_date=self.leave_end,
            days_count=2.0,
            reason="Leave 1",
            status="approved",
            company_id=1
        )
        LeaveRequest.objects.create(
            employee=self.emp_unrelated,
            project=self.other_project,
            leave_type="Sick Leave",
            start_date=self.leave_start,
            end_date=self.leave_start,
            days_count=1.0,
            reason="Leave 2",
            status="approved",
            company_id=1
        )
        sched = ActivitySchedule.objects.create(
            title="Scheduled Cleaning",
            activity=self.activity,
            project=self.project,
            assigned_to=self.emp_leave,
            recurring_type='one_time',
            start_date=self.leave_start,
            company_id=1
        )
        task = ActivityTask.objects.create(
            schedule=sched,
            activity=self.activity,
            project=self.project,
            task_title="Scheduled Panel Task",
            task_date=self.leave_start,
            assigned_to=self.emp_leave,
            status="Pending",
            company_id=1
        )

        resp = self.client.get('/admin/activity-schedules')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['approved_leaves_count'], 2)
        pending_pairs = {(t['workflow_type'], t['task_id']) for t in resp.context['pending_reassignment_tasks']}
        self.assertIn(('activity_task', task.id), pending_pairs)
        self.assertIn(('project_activity_instance', self.inst_1.id), pending_pairs)
        self.assertIn(('project_activity_instance', self.inst_unrelated.id), pending_pairs)

        # Reassign ActivityTask -> notification sent & moved to reassigned_tasks
        exec_resp = self.client.post('/admin/reassignment/execute', {
            'workflow_type': 'activity_task',
            'task_id': task.id,
            'new_employee_id': self.emp_replacement.id,
            'expected_previous_employee_id': self.emp_leave.id,
            'reason': 'Covering scheduled task'
        })
        self.assertEqual(exec_resp.status_code, 200)
        self.assertTrue(exec_resp.json()['success'])
        self.assertEqual(mock_fcm.call_count, 1)

        refresh_resp = self.client.get('/admin/activity-schedules')
        pending_pairs_after = {(t['workflow_type'], t['task_id']) for t in refresh_resp.context['pending_reassignment_tasks']}
        reassigned_pairs_after = {(r['workflow_type'], r['task_id']) for r in refresh_resp.context['reassigned_tasks']}
        self.assertNotIn(('activity_task', task.id), pending_pairs_after)
        self.assertIn(('activity_task', task.id), reassigned_pairs_after)
