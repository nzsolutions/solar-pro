import datetime
from django.test import TestCase, Client
from django.utils import timezone
from apps.employees.models import Employee
from apps.operations.models import Project, ProjectActivity, ProjectActivityInstance
from apps.masters.models import ActivityMaster, ActivitySchedule, ActivityTask, LeaveRequest, TaskReassignmentLog
from apps.masters.availability_service import EmployeeAvailabilityService
from apps.masters.reassignment_service import TaskReassignmentService


class UnifiedReassignmentTests(TestCase):
    def setUp(self):
        # Create test employees with unique app_username
        self.emp1 = Employee.objects.create(id=101, name="Rahul Sharma", app_username="rahul101", company_id=1, status='active')
        self.emp2 = Employee.objects.create(id=102, name="Amit Kumar", app_username="amit102", company_id=1, status='active')
        self.emp3 = Employee.objects.create(id=103, name="Priya Singh", app_username="priya103", company_id=1, status='active')
        self.emp_outside = Employee.objects.create(id=104, name="Outside Employee", app_username="outside104", company_id=1, status='active')

        # Create project with site_manager and field_staff
        self.project = Project.objects.create(
            id=10,
            project_name="Solar Park Alpha",
            client_name="Alpha Corp",
            site_manager=self.emp1.id,
            field_staff=[self.emp2.id, self.emp3.id],
            company_id=1,
            status='in_progress'
        )

        # Create activity master
        self.activity = ActivityMaster.objects.create(
            id=5,
            activity_title="Inverter Testing",
            activity_category="Testing",
            company_id=1,
            status='active'
        )

        self.schedule = ActivitySchedule.objects.create(
            id=1,
            title="Weekly Inverter Test",
            activity=self.activity,
            project=self.project,
            assigned_to=self.emp1,
            assigned_staff=[self.emp2.id],
            recurring_type='weekly',
            start_date=timezone.localdate(),
            priority='High',
            company_id=1
        )

    def test_project_team_candidate_resolution(self):
        """Test that replacement candidates are strictly restricted to the project team and exclude current assignee."""
        candidates = EmployeeAvailabilityService.get_project_team_candidates(
            project_id=self.project.id,
            target_date=timezone.localdate(),
            exclude_employee_id=self.emp1.id,
            company_id=1
        )
        cand_ids = [c['employee_id'] for c in candidates]
        self.assertIn(self.emp2.id, cand_ids)
        self.assertIn(self.emp3.id, cand_ids)
        self.assertNotIn(self.emp1.id, cand_ids)
        self.assertNotIn(self.emp_outside.id, cand_ids)

    def test_leave_gate_full_day_blocks_candidate(self):
        """Test that approved full-day leave marks candidate On Leave and non-selectable."""
        t_date = timezone.localdate() + datetime.timedelta(days=2)
        LeaveRequest.objects.create(
            employee=self.emp2,
            project=self.project,
            leave_type="Casual",
            start_date=t_date,
            end_date=t_date,
            days_count=1.0,
            status="approved",
            company_id=1
        )

        candidates = EmployeeAvailabilityService.get_project_team_candidates(
            project_id=self.project.id,
            target_date=t_date,
            exclude_employee_id=self.emp1.id,
            company_id=1
        )
        cand_map = {c['employee_id']: c for c in candidates}
        self.assertEqual(cand_map[self.emp2.id]['classification'], 'On Leave')
        self.assertFalse(cand_map[self.emp2.id]['is_selectable'])

    def test_leave_gate_half_day_warning_selectable(self):
        """Test Policy Option A: approved half-day leave (0.5 day) shows warning badge but remains selectable."""
        t_date = timezone.localdate() + datetime.timedelta(days=3)
        LeaveRequest.objects.create(
            employee=self.emp3,
            project=self.project,
            leave_type="Half-Day",
            start_date=t_date,
            end_date=t_date,
            days_count=0.5,
            status="approved",
            company_id=1
        )

        candidates = EmployeeAvailabilityService.get_project_team_candidates(
            project_id=self.project.id,
            target_date=t_date,
            exclude_employee_id=self.emp1.id,
            company_id=1
        )
        cand_map = {c['employee_id']: c for c in candidates}
        self.assertEqual(cand_map[self.emp3.id]['classification'], 'Half-Day Leave')
        self.assertTrue(cand_map[self.emp3.id]['is_selectable'])

    def test_activity_task_reassignment_success(self):
        """Test atomic reassignment of ActivityTask, handling assigned_staff correctly and creating audit log."""
        task_date = timezone.localdate() + datetime.timedelta(days=1)
        # Create approved leave for emp1 covering task_date
        LeaveRequest.objects.create(
            employee=self.emp1,
            project=self.project,
            leave_type="Casual",
            start_date=task_date,
            end_date=task_date,
            days_count=1.0,
            status="approved",
            company_id=1
        )

        task = ActivityTask.objects.create(
            schedule=self.schedule,
            activity=self.activity,
            project=self.project,
            task_title="Inverter Inspection #1",
            task_date=task_date,
            assigned_to=self.emp1,
            assigned_staff=[self.emp2.id],
            priority="High",
            status="Pending",
            company_id=1
        )

        # Reassign to emp2 (who was in assigned_staff)
        res = TaskReassignmentService.reassign_activity_task(
            task_id=task.id,
            new_employee_id=self.emp2.id,
            admin_user="TestAdmin",
            reason="Emp1 sick leave",
            company_id=1
        )
        self.assertTrue(res['success'])

        task.refresh_from_db()
        self.assertEqual(task.assigned_to_id, self.emp2.id)
        # Verify emp2 removed from assigned_staff to prevent duplicate primary/supporting
        self.assertNotIn(self.emp2.id, task.assigned_staff)
        # Verify emp1 removed because on leave
        self.assertNotIn(self.emp1.id, task.assigned_staff)

        # Verify audit log
        log = TaskReassignmentLog.objects.filter(activity_task=task).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.workflow_type, 'activity_task')
        self.assertEqual(log.previous_employee_id, self.emp1.id)
        self.assertEqual(log.new_employee_id, self.emp2.id)
        self.assertEqual(log.reassigned_by, 'TestAdmin')

    def test_reassignment_rejected_without_approved_leave(self):
        """Test that attempting to reassign a task when assignee is NOT on approved leave is strictly rejected."""
        from django.core.exceptions import ValidationError
        task_date = timezone.localdate() + datetime.timedelta(days=10)
        task = ActivityTask.objects.create(
            schedule=self.schedule,
            activity=self.activity,
            project=self.project,
            task_title="Task Without Leave",
            task_date=task_date,
            assigned_to=self.emp1,
            priority="Medium",
            status="Pending",
            company_id=1
        )

        # Emp1 has no approved leave on task_date -> Reassignment must fail
        with self.assertRaises(ValidationError) as ctx:
            TaskReassignmentService.reassign_activity_task(
                task_id=task.id,
                new_employee_id=self.emp2.id,
                admin_user="TestAdmin",
                company_id=1
            )
        self.assertIn("approved leave", str(ctx.exception).lower())

    def test_project_activity_instance_reassignment_and_inprogress_policy(self):
        """Test ProjectActivityInstance reassignment with In-Progress policy requiring handover remarks."""
        sched_date = timezone.localdate()
        # Create approved leave for emp1 covering sched_date
        LeaveRequest.objects.create(
            employee=self.emp1,
            project=self.project,
            leave_type="Medical",
            start_date=sched_date,
            end_date=sched_date,
            days_count=1.0,
            status="approved",
            company_id=1
        )

        pa = ProjectActivity.objects.create(
            project=self.project,
            activity=self.activity,
            frequency="Daily",
            status="active",
            company_id=1
        )
        inst = ProjectActivityInstance.objects.create(
            project_activity=pa,
            project=self.project,
            activity=self.activity,
            scheduled_date=sched_date,
            assigned_employee=self.emp1,
            status="In Progress",
            actual_start_time=timezone.now(),
            company_id=1
        )

        # Attempting without handover remarks should fail (Policy Option A)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            TaskReassignmentService.reassign_project_activity_instance(
                instance_id=inst.id,
                new_employee_id=self.emp2.id,
                admin_user="TestAdmin",
                reason="Workload shift",
                handover_remarks=None,
                company_id=1
            )

        # Providing handover remarks should succeed
        res = TaskReassignmentService.reassign_project_activity_instance(
            instance_id=inst.id,
            new_employee_id=self.emp2.id,
            admin_user="TestAdmin",
            reason="Workload shift",
            handover_remarks="Completed inverter 1-3, inverter 4 remaining",
            company_id=1
        )
        self.assertTrue(res['success'])

        inst.refresh_from_db()
        self.assertEqual(inst.assigned_employee_id, self.emp2.id)
        self.assertEqual(inst.status, 'In Progress')  # Preserved
        self.assertIsNotNone(inst.actual_start_time)  # Preserved

        # Verify audit log
        log = TaskReassignmentLog.objects.filter(project_activity_instance=inst).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.workflow_type, 'project_activity_instance')
        self.assertEqual(log.handover_remarks, "Completed inverter 1-3, inverter 4 remaining")

    def test_optimistic_concurrency_conflict_activity_task(self):
        """Test that attempting to reassign an ActivityTask with a stale expected_previous_employee_id raises conflict error."""
        from apps.masters.reassignment_service import ConcurrencyConflictError
        task_date = timezone.localdate() + datetime.timedelta(days=1)
        # Leave for emp1
        LeaveRequest.objects.create(
            employee=self.emp1,
            project=self.project,
            leave_type="Casual",
            start_date=task_date,
            end_date=task_date,
            days_count=1.0,
            status="approved",
            company_id=1
        )
        task = ActivityTask.objects.create(
            schedule=self.schedule,
            activity=self.activity,
            project=self.project,
            task_title="Inverter Concurrency Test",
            task_date=task_date,
            assigned_to=self.emp1,
            priority="High",
            status="Pending",
            company_id=1
        )

        # Admin A reassigns task from emp1 to emp2
        res_a = TaskReassignmentService.reassign_activity_task(
            task_id=task.id,
            new_employee_id=self.emp2.id,
            admin_user="Admin_A",
            expected_previous_employee_id=self.emp1.id,
            company_id=1
        )
        self.assertTrue(res_a['success'])

        task.refresh_from_db()
        self.assertEqual(task.assigned_to_id, self.emp2.id)

        # Admin B attempts to reassign using stale expectation (still expects emp1)
        with self.assertRaises(ConcurrencyConflictError):
            TaskReassignmentService.reassign_activity_task(
                task_id=task.id,
                new_employee_id=self.emp3.id,
                admin_user="Admin_B",
                expected_previous_employee_id=self.emp1.id,  # Stale ID! Current DB has emp2
                company_id=1
            )

        # Verify task remains assigned to emp2 and no second log was created
        task.refresh_from_db()
        self.assertEqual(task.assigned_to_id, self.emp2.id)
        self.assertEqual(TaskReassignmentLog.objects.filter(activity_task=task).count(), 1)

    def test_optimistic_concurrency_conflict_project_activity_instance(self):
        """Test that attempting to reassign a ProjectActivityInstance with a stale expected_previous_employee_id raises conflict error."""
        from apps.masters.reassignment_service import ConcurrencyConflictError
        sched_date = timezone.localdate()
        LeaveRequest.objects.create(
            employee=self.emp1,
            project=self.project,
            leave_type="Casual",
            start_date=sched_date,
            end_date=sched_date,
            days_count=1.0,
            status="approved",
            company_id=1
        )
        pa = ProjectActivity.objects.create(
            project=self.project,
            activity=self.activity,
            frequency="Daily",
            status="active",
            company_id=1
        )
        inst = ProjectActivityInstance.objects.create(
            project_activity=pa,
            project=self.project,
            activity=self.activity,
            scheduled_date=sched_date,
            assigned_employee=self.emp1,
            status="Pending",
            company_id=1
        )

        # Admin A reassigns from emp1 to emp2
        res_a = TaskReassignmentService.reassign_project_activity_instance(
            instance_id=inst.id,
            new_employee_id=self.emp2.id,
            admin_user="Admin_A",
            expected_previous_employee_id=self.emp1.id,
            company_id=1
        )
        self.assertTrue(res_a['success'])

        # Admin B attempts stale reassignment expecting emp1
        with self.assertRaises(ConcurrencyConflictError):
            TaskReassignmentService.reassign_project_activity_instance(
                instance_id=inst.id,
                new_employee_id=self.emp3.id,
                admin_user="Admin_B",
                expected_previous_employee_id=self.emp1.id,
                company_id=1
            )

        inst.refresh_from_db()
        self.assertEqual(inst.assigned_employee_id, self.emp2.id)
        self.assertEqual(TaskReassignmentLog.objects.filter(project_activity_instance=inst).count(), 1)

    def test_reassignment_api_authorization_and_concurrency_http(self):
        """Test HTTP responses for unauthenticated, regular employee, Admin, and 409 concurrency conflict."""
        client = Client()

        # 1. Unauthenticated request -> 302 to login
        res_unauth = client.get('/admin/reassignment/candidates?workflow_type=activity_task&task_id=1')
        self.assertEqual(res_unauth.status_code, 302)

        # 2. Authenticated Regular Employee (is_admin = 0) -> 403 Forbidden
        session = client.session
        session['user_id'] = self.emp1.id
        session['name'] = self.emp1.name
        session['is_admin'] = 0
        session['company_id'] = 1
        session.save()

        # Check all 4 endpoints return 403 (with HTTP_X_REQUESTED_WITH or Accept application/json)
        headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest', 'HTTP_ACCEPT': 'application/json'}
        self.assertEqual(client.get('/admin/reassignment/affected-tasks/1', **headers).status_code, 403)
        self.assertEqual(client.get('/admin/reassignment/candidates?workflow_type=activity_task&task_id=1', **headers).status_code, 403)
        self.assertEqual(client.get('/admin/reassignment/history', **headers).status_code, 403)
        res_exec_emp = client.post('/admin/reassignment/execute', {
            'workflow_type': 'activity_task',
            'task_id': 1,
            'new_employee_id': self.emp2.id
        }, **headers)
        self.assertEqual(res_exec_emp.status_code, 403)

        # 3. Authenticated Admin (is_admin = 1) -> Success
        session['is_admin'] = 1
        session['name'] = 'SuperAdmin'
        session.save()

        task_date = timezone.localdate() + datetime.timedelta(days=2)
        LeaveRequest.objects.create(
            employee=self.emp1,
            project=self.project,
            leave_type="Casual",
            start_date=task_date,
            end_date=task_date,
            days_count=1.0,
            status="approved",
            company_id=1
        )
        task = ActivityTask.objects.create(
            schedule=self.schedule,
            activity=self.activity,
            project=self.project,
            task_title="HTTP Concurrency Task",
            task_date=task_date,
            assigned_to=self.emp1,
            status="Pending",
            company_id=1
        )

        # Normal reassignment with matching expected_previous_employee_id -> 200 OK
        res_ok = client.post('/admin/reassignment/execute', {
            'workflow_type': 'activity_task',
            'task_id': task.id,
            'new_employee_id': self.emp2.id,
            'expected_previous_employee_id': self.emp1.id,
            'reason': 'HTTP test reassignment'
        })
        self.assertEqual(res_ok.status_code, 200)
        self.assertTrue(res_ok.json()['success'])

        # Stale reassignment with previous assignee expectation -> 409 Conflict
        res_conflict = client.post('/admin/reassignment/execute', {
            'workflow_type': 'activity_task',
            'task_id': task.id,
            'new_employee_id': self.emp3.id,
            'expected_previous_employee_id': self.emp1.id,  # Stale! Current assignee is emp2
            'reason': 'Stale HTTP request'
        })
        self.assertEqual(res_conflict.status_code, 409)
        self.assertFalse(res_conflict.json()['success'])
        self.assertTrue(res_conflict.json().get('conflict'))

    def test_mobile_activity_visibility_after_reassignment(self):
        """
        Verify that after reassignment, replacement employee sees the task in their Mobile assigned list,
        and the previous employee (even if in project field staff) NO LONGER sees that task as assigned to them.
        """
        import json
        client = Client()
        today = timezone.localdate()

        # emp1 on leave today
        LeaveRequest.objects.create(
            employee=self.emp1,
            project=self.project,
            leave_type="Casual",
            start_date=today,
            end_date=today,
            days_count=1.0,
            status="approved",
            company_id=1
        )

        pa = ProjectActivity.objects.create(
            project=self.project,
            activity=self.activity,
            frequency="Daily",
            status="active",
            company_id=1
        )
        inst = ProjectActivityInstance.objects.create(
            project_activity=pa,
            project=self.project,
            activity=self.activity,
            scheduled_date=today,
            assigned_employee=self.emp1,
            status="Pending",
            company_id=1
        )

        # 1. Before reassignment: emp1 sees task; emp2 does not see task (since it's assigned to emp1)
        res_emp1_before = client.get(f'/api/get-employee-activities?employee_id={self.emp1.id}')
        self.assertEqual(res_emp1_before.status_code, 200)
        task_ids_emp1_before = [item['id'] for item in res_emp1_before.json()['data']]
        self.assertIn(inst.id, task_ids_emp1_before)

        res_emp2_before = client.get(f'/api/get-employee-activities?employee_id={self.emp2.id}')
        self.assertEqual(res_emp2_before.status_code, 200)
        task_ids_emp2_before = [item['id'] for item in res_emp2_before.json()['data']]
        self.assertNotIn(inst.id, task_ids_emp2_before)

        # 2. Reassign task from emp1 to emp2
        reassign_res = TaskReassignmentService.reassign_project_activity_instance(
            instance_id=inst.id,
            new_employee_id=self.emp2.id,
            admin_user="Admin",
            reason="Leave replacement",
            company_id=1
        )
        self.assertTrue(reassign_res['success'])

        # 3. After reassignment: emp2 MUST see task; emp1 MUST NO LONGER see task
        res_emp1_after = client.get(f'/api/get-employee-activities?employee_id={self.emp1.id}')
        self.assertEqual(res_emp1_after.status_code, 200)
        task_ids_emp1_after = [item['id'] for item in res_emp1_after.json()['data']]
        self.assertNotIn(inst.id, task_ids_emp1_after)

        res_emp2_after = client.get(f'/api/get-employee-activities?employee_id={self.emp2.id}')
        self.assertEqual(res_emp2_after.status_code, 200)
        task_ids_emp2_after = [item['id'] for item in res_emp2_after.json()['data']]
        self.assertIn(inst.id, task_ids_emp2_after)


