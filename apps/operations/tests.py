import json
from datetime import date
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from apps.dynamic_forms.models import DynamicForm
from apps.employees.models import Employee
from apps.masters.models import ActivityMaster, SiteMaster
from apps.operations.activity_service import ProjectActivityService
from apps.operations.models import (
    Project,
    ProjectActivity,
    ProjectActivityInstance,
)


class ProjectWizardActivityAssignmentTests(TestCase):
    def setUp(self):
        self.client = Client()
        session = self.client.session
        session['user_id'] = 1
        session['is_admin'] = 1
        session['company_id'] = 1
        session['name'] = 'Admin'
        session.save()

        self.site = SiteMaster.objects.create(
            site_name='Test Solar Site',
            site_address='100 Solar Way',
            company_id=1,
        )

        self.emp_manager = Employee.objects.create(
            name='Amit Patel',
            app_username='amit.test',
            app_password='pwd',
            email='amit.test@solarpro.local',
            company_id=1,
            status='active',
        )
        self.emp_staff_1 = Employee.objects.create(
            name='Rahul Sharma',
            app_username='rahul.test',
            app_password='pwd',
            email='rahul.test@solarpro.local',
            company_id=1,
            status='active',
        )
        self.emp_staff_2 = Employee.objects.create(
            name='Poonam Deore',
            app_username='poonam.test',
            app_password='pwd',
            email='poonam.test@solarpro.local',
            company_id=1,
            status='active',
        )
        self.emp_outside = Employee.objects.create(
            name='Outside Employee',
            app_username='outside.test',
            app_password='pwd',
            email='outside.test@solarpro.local',
            company_id=1,
            status='active',
        )

        self.form_1 = DynamicForm.objects.create(
            company_id=1,
            form_name='Cleaning Checklist',
            form_schema={'sections': []},
            is_active=1,
        )
        self.form_2 = DynamicForm.objects.create(
            company_id=1,
            form_name='Inspection Checklist',
            form_schema={'sections': []},
            is_active=1,
        )

        self.act_cleaning = ActivityMaster.objects.create(
            activity_title='Solar Panel Cleaning',
            activity_category='Cleaning',
            default_frequency='Weekly',
            estimated_duration='2 hrs',
            form=self.form_1,
            status='active',
            company_id=1,
        )
        self.act_inverter = ActivityMaster.objects.create(
            activity_title='Inverter Inspection',
            activity_category='Electrical',
            default_frequency='Monthly',
            estimated_duration='1 hr',
            status='active',
            company_id=1,
        )
        self.act_site = ActivityMaster.objects.create(
            activity_title='Site Inspection',
            activity_category='Inspection',
            default_frequency='Daily',
            estimated_duration='30 mins',
            form=self.form_2,
            status='active',
            company_id=1,
        )

    def test_wizard_step_sequence_and_choose_staff_column(self):
        res = self.client.get('/admin/projects/create')
        self.assertEqual(res.status_code, 200)
        html = res.content.decode('utf-8')

        # Verify step indicator labels in exact order 1..7
        step_markers = [
            ('data-step-indicator="1"', 'Client &amp; Site'),
            ('data-step-indicator="2"', 'Schedule &amp; Reporting'),
            ('data-step-indicator="3"', 'Team Assignment'),
            ('data-step-indicator="4"', 'Add Activity'),
            ('data-step-indicator="5"', 'Stock Allocation'),
            ('data-step-indicator="6"', 'Documents'),
            ('data-step-indicator="7"', 'Notes'),
        ]
        prev_idx = -1
        for indicator, label in step_markers:
            ind_pos = html.find(indicator)
            lbl_pos = html.find(label, ind_pos)
            self.assertGreater(ind_pos, prev_idx, f"Indicator {indicator} out of order")
            self.assertGreater(lbl_pos, ind_pos, f"Label {label} not inside {indicator}")
            prev_idx = lbl_pos

        # Verify form-step blocks: Step 3 = Team Assignment, Step 4 = Add Activity
        s3 = html.find('class="form-step" data-step="3"')
        s4 = html.find('class="form-step" data-step="4"')
        s5 = html.find('class="form-step" data-step="5"')
        self.assertTrue(0 < s3 < s4 < s5)

        step3_html = html[s3:s4]
        step4_html = html[s4:s5]

        self.assertIn('id="site_manager"', step3_html)
        self.assertIn('name="field_staff[]"', step3_html)
        self.assertNotIn('id="activitiesTable"', step3_html)

        self.assertIn('id="activitiesTable"', step4_html)
        self.assertNotIn('id="site_manager"', step4_html)

        # Verify Step 4 table columns in exact order
        expected_headers = [
            'Select',
            'Activity Details',
            'Category',
            'Frequency',
            'Attached Form',
            'Choose Staff',
            'Est. Duration',
        ]
        thead_start = step4_html.find('<thead')
        thead_end = step4_html.find('</thead>')
        thead_html = step4_html[thead_start:thead_end]
        header_pos = -1
        for header in expected_headers:
            idx = thead_html.find(header)
            self.assertGreater(idx, header_pos, f"Header '{header}' missing or out of order")
            header_pos = idx

        # Verify per-activity Choose Staff select element exists and starts without static options
        staff_sel_marker = f'name="activity_staff_{self.act_cleaning.id}"'
        self.assertIn(staff_sel_marker, step4_html)
        self.assertIn('Choose Staff', step4_html)

    def test_store_rejects_selected_activity_without_staff(self):
        initial_count = Project.objects.count()
        post_data = {
            'client_name': 'Missing Staff Client',
            'project_name': 'Missing Staff Project',
            'site_id': str(self.site.id),
            'start_date': '2026-01-01',
            'end_date': '2026-01-31',
            'reporting_frequency': 'Weekly',
            'site_manager': str(self.emp_manager.id),
            'field_staff[]': [str(self.emp_staff_1.id)],
            'selected_activities[]': [str(self.act_cleaning.id)],
            f'activity_frequency_{self.act_cleaning.id}': 'Weekly',
            f'activity_form_{self.act_cleaning.id}': str(self.form_1.id),
            f'activity_duration_{self.act_cleaning.id}': '2 hrs',
            # Intentionally omit activity_staff_<id>
        }
        res = self.client.post('/admin/projects/store', post_data, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Project.objects.count(), initial_count)
        msgs = [str(m) for m in res.context['messages']]
        self.assertTrue(any('staff' in m.lower() for m in msgs), f"Expected validation message, got {msgs}")

    def test_store_rejects_staff_outside_selected_project_team(self):
        initial_count = Project.objects.count()
        post_data = {
            'client_name': 'Outside Staff Client',
            'project_name': 'Outside Staff Project',
            'site_id': str(self.site.id),
            'start_date': '2026-01-01',
            'end_date': '2026-01-31',
            'reporting_frequency': 'Weekly',
            'site_manager': str(self.emp_manager.id),
            'field_staff[]': [str(self.emp_staff_1.id)],
            'selected_activities[]': [str(self.act_cleaning.id)],
            f'activity_frequency_{self.act_cleaning.id}': 'Weekly',
            f'activity_form_{self.act_cleaning.id}': str(self.form_1.id),
            f'activity_staff_{self.act_cleaning.id}': str(self.emp_outside.id),
            f'activity_duration_{self.act_cleaning.id}': '2 hrs',
        }
        res = self.client.post('/admin/projects/store', post_data, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Project.objects.count(), initial_count)
        msgs = [str(m) for m in res.context['messages']]
        self.assertTrue(any('project team' in m.lower() for m in msgs), f"Expected team validation error, got {msgs}")

    def test_activity_wise_assignment_persistence_generation_and_mobile_workflow(self):
        post_data = {
            'client_name': 'Activity Wise Solar Client',
            'project_name': 'Activity Wise 10MW Plant',
            'site_id': str(self.site.id),
            'start_date': '2026-01-01',
            'end_date': '2026-01-31',
            'reporting_frequency': 'Weekly',
            'site_manager': str(self.emp_manager.id),
            'field_staff[]': [str(self.emp_staff_1.id), str(self.emp_staff_2.id)],
            'selected_activities[]': [
                str(self.act_cleaning.id),
                str(self.act_inverter.id),
                str(self.act_site.id),
            ],
            # Cleaning -> Field Staff 1 (Rahul)
            f'activity_frequency_{self.act_cleaning.id}': 'Weekly',
            f'activity_form_{self.act_cleaning.id}': str(self.form_1.id),
            f'activity_staff_{self.act_cleaning.id}': str(self.emp_staff_1.id),
            f'activity_duration_{self.act_cleaning.id}': '2 hrs',
            # Inverter Inspection -> Site Manager (Amit)
            f'activity_frequency_{self.act_inverter.id}': 'Monthly',
            f'activity_form_{self.act_inverter.id}': '',
            f'activity_staff_{self.act_inverter.id}': str(self.emp_manager.id),
            f'activity_duration_{self.act_inverter.id}': '1.5 hrs',
            # Site Inspection -> Field Staff 2 (Poonam)
            f'activity_frequency_{self.act_site.id}': 'Daily',
            f'activity_form_{self.act_site.id}': str(self.form_2.id),
            f'activity_staff_{self.act_site.id}': str(self.emp_staff_2.id),
            f'activity_duration_{self.act_site.id}': '45 mins',
        }

        res = self.client.post('/admin/projects/store', post_data, follow=True)
        self.assertEqual(res.status_code, 200)

        project = Project.objects.get(client_name='Activity Wise Solar Client')
        self.assertEqual(project.site_manager, self.emp_manager.id)
        self.assertEqual(sorted(project.field_staff), sorted([self.emp_staff_1.id, self.emp_staff_2.id]))

        pa_clean = ProjectActivity.objects.get(project=project, activity=self.act_cleaning)
        pa_inv = ProjectActivity.objects.get(project=project, activity=self.act_inverter)
        pa_site = ProjectActivity.objects.get(project=project, activity=self.act_site)

        # Activity-wise employee assignments and settings preserved
        self.assertEqual(pa_clean.assigned_employee_id, self.emp_staff_1.id)
        self.assertEqual(pa_clean.frequency, 'Weekly')
        self.assertEqual(pa_clean.form_id, self.form_1.id)
        self.assertEqual(pa_clean.estimated_duration, '2 hrs')

        self.assertEqual(pa_inv.assigned_employee_id, self.emp_manager.id)
        self.assertEqual(pa_inv.frequency, 'Monthly')
        self.assertIsNone(pa_inv.form_id)
        self.assertEqual(pa_inv.estimated_duration, '1.5 hrs')

        self.assertEqual(pa_site.assigned_employee_id, self.emp_staff_2.id)
        self.assertEqual(pa_site.frequency, 'Daily')
        self.assertEqual(pa_site.form_id, self.form_2.id)
        self.assertEqual(pa_site.estimated_duration, '45 mins')

        # Generated instances use the exact activity-selected employee (not Site Manager generically)
        clean_insts = list(pa_clean.instances.all())
        inv_insts = list(pa_inv.instances.all())
        site_insts = list(pa_site.instances.all())

        self.assertGreater(len(clean_insts), 0)
        self.assertEqual(len(inv_insts), 1)
        self.assertEqual(len(site_insts), 31)

        self.assertTrue(all(i.assigned_employee_id == self.emp_staff_1.id for i in clean_insts))
        self.assertTrue(all(i.assigned_employee_id == self.emp_manager.id for i in inv_insts))
        self.assertTrue(all(i.assigned_employee_id == self.emp_staff_2.id for i in site_insts))

        # Test project_update date extension preserves existing assignments and assigns new occurrences to activity's employee
        # First simulate a manual reassignment on one instance to ensure it is NOT overwritten
        reassigned_inst = clean_insts[0]
        reassigned_inst.assigned_employee = self.emp_staff_2
        reassigned_inst.save(update_fields=['assigned_employee'])

        update_res = self.client.post(f'/admin/projects/{project.id}/update', {
            'client_name': project.client_name,
            'project_name': project.project_name,
            'site_id': str(self.site.id),
            'site_manager': str(self.emp_manager.id),
            'field_staff[]': [str(self.emp_staff_1.id), str(self.emp_staff_2.id)],
            'status': 'in_progress',
            'start_date': '2026-01-01',
            'end_date': '2026-02-28',
            'reporting_frequency': 'Weekly',
            'agreement': 'No',
        }, follow=True)
        self.assertEqual(update_res.status_code, 200)

        reassigned_inst.refresh_from_db()
        self.assertEqual(reassigned_inst.assigned_employee_id, self.emp_staff_2.id)

        feb_inv_inst = ProjectActivityInstance.objects.get(
            project_activity=pa_inv,
            scheduled_date=date(2026, 2, 1),
        )
        self.assertEqual(feb_inv_inst.assigned_employee_id, self.emp_manager.id)
        feb_clean_insts = pa_clean.instances.filter(scheduled_date__gte=date(2026, 2, 1))
        self.assertTrue(feb_clean_insts.exists())
        self.assertTrue(all(i.assigned_employee_id == self.emp_staff_1.id for i in feb_clean_insts))

        # Mobile API checks: each employee receives ONLY their assigned activities
        api_client = Client()

        res_rahul = api_client.get(f'/api/get-employee-activities?emp_id={self.emp_staff_1.id}&project_id={project.id}')
        self.assertEqual(res_rahul.status_code, 200)
        rahul_act_ids = {item['activity_id'] for item in res_rahul.json()['data']}
        self.assertEqual(rahul_act_ids, {self.act_cleaning.id})

        res_amit = api_client.get(f'/api/get-employee-activities?emp_id={self.emp_manager.id}&project_id={project.id}')
        self.assertEqual(res_amit.status_code, 200)
        amit_act_ids = {item['activity_id'] for item in res_amit.json()['data']}
        self.assertEqual(amit_act_ids, {self.act_inverter.id})

        res_poonam = api_client.get(f'/api/get-employee-activities?emp_id={self.emp_staff_2.id}&project_id={project.id}')
        self.assertEqual(res_poonam.status_code, 200)
        poonam_act_ids = {item['activity_id'] for item in res_poonam.json()['data']}
        # Poonam has Site Inspection + the manually reassigned Cleaning instance
        self.assertIn(self.act_site.id, poonam_act_ids)
        self.assertNotIn(self.act_inverter.id, poonam_act_ids)

        # Complete full mobile workflow on one of Rahul's Cleaning instances
        target_inst_id = res_rahul.json()['data'][0]['id']
        start_res = api_client.post('/api/start-activity-instance', {
            'emp_id': self.emp_staff_1.id,
            'instance_id': target_inst_id,
        })
        self.assertEqual(start_res.status_code, 200)

        photo_file = SimpleUploadedFile('before.jpg', b'jpegdata', content_type='image/jpeg')
        photo_res = api_client.post('/api/upload-activity-photo', {
            'emp_id': self.emp_staff_1.id,
            'instance_id': target_inst_id,
            'photo_stage': 'Before',
            'photo': photo_file,
        })
        self.assertEqual(photo_res.status_code, 201)

        form_res = api_client.post(
            '/api/submit-activity-form',
            json.dumps({
                'emp_id': self.emp_staff_1.id,
                'instance_id': target_inst_id,
                'submission_data': {'Status': 'Clean'},
            }),
            content_type='application/json',
        )
        self.assertEqual(form_res.status_code, 200)

        comp_res = api_client.post('/api/complete-activity-instance', {
            'emp_id': self.emp_staff_1.id,
            'instance_id': target_inst_id,
            'remarks': 'Done cleanly',
        })
        self.assertEqual(comp_res.status_code, 200)

        completed_inst = ProjectActivityInstance.objects.get(id=target_inst_id)
        self.assertEqual(completed_inst.status, 'Completed')
        self.assertEqual(completed_inst.assigned_employee_id, self.emp_staff_1.id)
        self.assertEqual(completed_inst.submitted_by_id, self.emp_staff_1.id)

    def test_legacy_project_activity_without_assigned_employee_preserves_existing_instances(self):
        legacy_proj = Project.objects.create(
            project_name='Legacy Project',
            client_name='Legacy Client',
            site_id=self.site.id,
            site_manager=self.emp_manager.id,
            field_staff=[self.emp_staff_1.id],
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
            company_id=1,
        )
        legacy_pa = ProjectActivity.objects.create(
            project=legacy_proj,
            activity=self.act_inverter,
            frequency='Monthly',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
            assigned_employee=None,
            company_id=1,
        )
        existing_inst = ProjectActivityInstance.objects.create(
            project_activity=legacy_pa,
            project=legacy_proj,
            activity=self.act_inverter,
            scheduled_date=date(2026, 1, 1),
            due_date=date(2026, 1, 1),
            frequency='Monthly',
            assigned_employee=self.emp_staff_1,
            status='Pending',
            company_id=1,
        )

        ProjectActivityService.generate_instances_for_activity(legacy_pa)

        existing_inst.refresh_from_db()
        self.assertEqual(existing_inst.assigned_employee_id, self.emp_staff_1.id)
        feb_inst = ProjectActivityInstance.objects.get(
            project_activity=legacy_pa,
            scheduled_date=date(2026, 2, 1),
        )
        # Does NOT automatically assign to site_manager
        self.assertIsNone(feb_inst.assigned_employee_id)

    def test_project_creation_without_activities_remains_supported(self):
        res = self.client.post('/admin/projects/store', {
            'client_name': 'No Activity Client',
            'project_name': 'No Activity Project',
            'site_id': str(self.site.id),
            'start_date': '2026-01-01',
            'end_date': '2026-01-31',
            'reporting_frequency': 'Weekly',
            'site_manager': str(self.emp_manager.id),
        }, follow=True)
        self.assertEqual(res.status_code, 200)
        proj = Project.objects.get(client_name='No Activity Client')
        self.assertEqual(proj.project_activities.count(), 0)
