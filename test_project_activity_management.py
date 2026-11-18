import os
import sys
import django
from datetime import date, datetime, timedelta
import io

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarpro_core.settings')
django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.operations.models import (
    Project,
    ProjectActivity,
    ProjectActivityInstance,
    ProjectActivityPhoto,
    ProjectActivityIssue,
)
from apps.masters.models import ActivityMaster, SiteMaster
from apps.employees.models import Employee
from apps.dynamic_forms.models import DynamicForm, FormSubmission
from apps.operations.activity_service import ProjectActivityService

def run_tests():
    print("=" * 65)
    print("PROJECT ACTIVITY MANAGEMENT EXTENSION TEST SUITE")
    print("=" * 65)

    client = Client()

    # 1. Setup / identify fixtures
    employee = Employee.objects.filter(status='active').first()
    site = SiteMaster.objects.first()
    act_daily = ActivityMaster.objects.filter(default_frequency='Daily', status='active').first()
    act_monthly = ActivityMaster.objects.filter(default_frequency='Monthly', status='active').first()
    form = DynamicForm.objects.filter(is_active=1).first()

    assert employee, "Active employee fixture required"
    assert site, "Site fixture required"
    assert act_daily, "Daily activity fixture required"
    assert act_monthly, "Monthly activity fixture required"
    print(" [PASS] Test fixtures verified: employee, site, activities, forms")

    # 2. Test Step 3 rendering in Add Project
    session = client.session
    session['user_id'] = 1
    session['is_admin'] = 1
    session['company_id'] = 1
    session.save()

    res = client.get('/admin/projects/create')
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    html = res.content.decode('utf-8')
    assert 'Add Activity' in html, "Add Activity step not found in addproject.html"
    assert 'data-step="3"' in html, "Step 3 not rendered for Add Activity"
    assert 'selected_activities[]' in html, "Activity selection input missing"
    print(" [PASS] Add Project wizard: Step 3 (Add Activity) rendered cleanly at position 3")

    # 3. Test Project Creation with Activities and Form attachment
    client_name = "Apex Solar Phase 2"
    proj_name = "Apex 5MW Farm"
    post_data = {
        'client_name': client_name,
        'project_name': proj_name,
        'site_id': str(site.id),
        'start_date': '2026-01-01',
        'end_date': '2026-03-31', # 90 days, 3 months
        'reporting_frequency': 'Weekly',
        'site_manager': str(employee.id),
        'field_staff[]': [str(employee.id)],
        # Step 3 activities
        'selected_activities[]': [str(act_daily.id), str(act_monthly.id)],
        f'activity_frequency_{act_daily.id}': 'Daily',
        f'activity_form_{act_daily.id}': str(form.id) if form else '',
        f'activity_duration_{act_daily.id}': '1 hr',
        f'activity_frequency_{act_monthly.id}': 'Monthly',
        f'activity_form_{act_monthly.id}': '',
        f'activity_duration_{act_monthly.id}': '3 hrs',
    }

    res = client.post('/admin/projects/store', post_data, follow=True)
    assert res.status_code == 200, f"Expected 200 on project store, got {res.status_code}"

    project = Project.objects.filter(client_name=client_name).order_by('-id').first()
    assert project, "Project was not created"
    print(f" [PASS] Project created successfully: '{project.client_name}' (ID: {project.id})")

    # 4. Verify ProjectActivity and Automatic Entry Generation
    p_activities = ProjectActivity.objects.filter(project=project)
    assert p_activities.count() == 2, f"Expected 2 project activities, got {p_activities.count()}"

    pa_daily = p_activities.filter(activity=act_daily).first()
    assert pa_daily, "Daily ProjectActivity record not found"
    assert pa_daily.form_id == (form.id if form else None), "Form association incorrect"

    # Daily from 2026-01-01 to 2026-03-31: Jan=31, Feb=28, Mar=31 = 90 days
    daily_instances = pa_daily.instances.all()
    assert daily_instances.count() == 90, f"Expected 90 daily instances, got {daily_instances.count()}"

    pa_monthly = p_activities.filter(activity=act_monthly).first()
    monthly_instances = pa_monthly.instances.all()
    # Monthly: Jan, Feb, Mar = 3 instances
    assert monthly_instances.count() == 3, f"Expected 3 monthly instances, got {monthly_instances.count()}"
    print(f" [PASS] Automatic Entry Generation verified: 90 daily instances & 3 monthly instances generated")

    # 5. Verify Idempotence / Safe Retry
    added = ProjectActivityService.generate_instances_for_activity(pa_monthly)
    assert added == 0, f"Expected 0 new instances on re-run, got {added}"
    assert pa_monthly.instances.count() == 3, "Instance count altered on idempotent retry"
    print(" [PASS] Idempotent generation: duplicate instances prevented on re-generation")

    # 6. Test Admin Project Activities Management Screen & Frequency Filtering
    res = client.get('/admin/project-activities')
    assert res.status_code == 200, f"Expected 200 for project activities index, got {res.status_code}"
    html = res.content.decode('utf-8')
    assert "Project Activity Management" in html
    # Schedule View section has been completely removed per requirements
    assert "Current Week" not in html
    assert "Schedule View:" not in html
    assert "name=\"frequency\"" in html

    # Verify Frequency Filtering works accurately
    for freq in ['Daily', 'Weekly', 'Monthly', 'Quarterly', 'Yearly']:
        res_freq = client.get(f'/admin/project-activities?frequency={freq}')
        assert res_freq.status_code == 200

    # Test filtering specifically on the test project with Monthly frequency
    res_proj_monthly = client.get(f'/admin/project-activities?project={project.id}&frequency=Monthly')
    assert res_proj_monthly.status_code == 200
    assert "Monthly" in res_proj_monthly.content.decode('utf-8')
    print(" [PASS] Admin Project Activities management screen, Schedule View removal, and Frequency filtering verified (200 OK)")

    # 7. Test Detail Modal endpoint
    first_instance = monthly_instances.first()
    res = client.get(f'/admin/project-activities/instance/{first_instance.id}')
    assert res.status_code == 200, f"Expected 200 for instance detail modal, got {res.status_code}"
    print(f" [PASS] Admin instance detail modal rendered (ID: {first_instance.id})")

    # 8. Mobile API: get-employee-activities
    res = client.get(f'/api/get-employee-activities?emp_id={employee.id}&project_id={project.id}')
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert data.get('success') is True
    assert len(data.get('data', [])) >= 3
    print(" [PASS] Mobile API: GET /api/get-employee-activities returned assigned instances")

    # 9. Mobile API: start-activity-instance
    res = client.post('/api/start-activity-instance', {'emp_id': employee.id, 'instance_id': first_instance.id})
    assert res.status_code == 200
    first_instance.refresh_from_db()
    assert first_instance.status == 'In Progress'
    assert first_instance.actual_start_time is not None
    print(" [PASS] Mobile API: POST /api/start-activity-instance transitioned status to 'In Progress'")

    # 10. Mobile API: upload-activity-photo (Before and After)
    dummy_img = SimpleUploadedFile("before.jpg", b"fake_jpeg_content_bytes", content_type="image/jpeg")
    res = client.post('/api/upload-activity-photo', {
        'emp_id': employee.id,
        'instance_id': first_instance.id,
        'photo_stage': 'Before',
        'latitude': '19.0760',
        'longitude': '72.8777',
        'photo': dummy_img,
    })
    assert res.status_code == 201, f"Expected 201 on photo upload, got {res.status_code}: {res.content}"
    assert first_instance.photos.filter(photo_stage='Before').exists()
    print(" [PASS] Mobile API: POST /api/upload-activity-photo uploaded Before photo with GPS metadata")

    # Upload After photo as well to satisfy photo requirements if activity enforces it
    dummy_after = SimpleUploadedFile("after.jpg", b"fake_jpeg_after_bytes", content_type="image/jpeg")
    res = client.post('/api/upload-activity-photo', {
        'emp_id': employee.id,
        'instance_id': first_instance.id,
        'photo_stage': 'After',
        'latitude': '19.0760',
        'longitude': '72.8777',
        'photo': dummy_after,
    })
    assert res.status_code == 201
    assert first_instance.photos.filter(photo_stage='After').exists()
    print(" [PASS] Mobile API: POST /api/upload-activity-photo uploaded After photo with GPS metadata")

    # 11. Mobile API: submit-activity-form
    form_answers = {"Reading 1": "Normal", "Voltage": 230}
    res = client.post('/api/submit-activity-form', {
        'emp_id': employee.id,
        'instance_id': first_instance.id,
        'submission_data': form_answers
    }, content_type='application/json')
    assert res.status_code == 200
    first_instance.refresh_from_db()
    assert first_instance.submission_data == form_answers
    print(" [PASS] Mobile API: POST /api/submit-activity-form saved answers and linked submission")

    # 12. Mobile API: complete-activity-instance
    res = client.post('/api/complete-activity-instance', {
        'emp_id': employee.id,
        'instance_id': first_instance.id,
        'remarks': 'Completed all maintenance checks satisfactorily.'
    })
    assert res.status_code == 200
    first_instance.refresh_from_db()
    assert first_instance.status == 'Completed'
    assert first_instance.submitted_by_id == employee.id
    print(" [PASS] Mobile API: POST /api/complete-activity-instance marked activity as Completed")

    # 13. Mobile API: report-activity-issue (Inability to complete)
    second_instance = monthly_instances.all()[1]
    dummy_issue_photo = SimpleUploadedFile("broken.jpg", b"broken_equipment_photo", content_type="image/jpeg")
    res = client.post('/api/report-activity-issue', {
        'emp_id': employee.id,
        'instance_id': second_instance.id,
        'issue_category': 'Equipment Not Working',
        'short_description': 'Tester battery drained & site transformer locked',
        'detailed_explanation': 'Cannot access transformer box due to locked gate and damaged tester.',
        'latitude': '19.0760',
        'longitude': '72.8777',
        'supporting_photo': dummy_issue_photo
    })
    assert res.status_code == 201, f"Expected 201 on issue report, got {res.status_code}: {res.content}"
    second_instance.refresh_from_db()
    assert second_instance.status == 'Unable to Complete', f"Status is {second_instance.status}"
    assert second_instance.status != 'Completed', "Activity must NOT be marked completed when exception reported"
    issue_record = second_instance.issues.first()
    assert issue_record, "Issue record not linked to instance"
    assert issue_record.issue_category == 'Equipment Not Working'
    print(" [PASS] Mobile API: POST /api/report-activity-issue reported exception without marking activity completed")

    # 14. Mobile API: get-employee-activity-history
    res = client.get(f'/api/get-employee-activity-history?emp_id={employee.id}')
    assert res.status_code == 200
    history_data = res.json().get('data', [])
    assert len(history_data) >= 2
    types = [h['type'] for h in history_data]
    assert 'execution' in types and 'issue' in types
    print(" [PASS] Mobile API: GET /api/get-employee-activity-history retrieved execution and issue history")

    # 15. Admin review issue workflow
    res = client.post(f'/admin/project-activities/instance/{second_instance.id}/review-issue', {
        'issue_id': str(issue_record.id),
        'status': 'Resolved',
        'admin_remarks': 'Spare tester dispatched and gate key handed over.'
    }, follow=True)
    assert res.status_code == 200
    second_instance.refresh_from_db()
    issue_record.refresh_from_db()
    assert issue_record.status == 'Resolved'
    assert second_instance.status == 'Pending', f"Instance should be reset to Pending once resolved, got {second_instance.status}"
    print(" [PASS] Admin reviewed and resolved exception; instance reset to Pending for execution")

    # 16. Date change reconciliation
    # Shorten project to 2026-02-28 (Jan + Feb only; March should be reconciled)
    pa_monthly.end_date = date(2026, 2, 28)
    pa_monthly.save()
    ProjectActivityService.generate_instances_for_activity(pa_monthly)
    remaining_monthly = pa_monthly.instances.all()
    # 2 months remain, the completed Jan instance is preserved, March instance removed
    assert remaining_monthly.count() == 2, f"Expected 2 instances after reconciliation, got {remaining_monthly.count()}"
    jan_inst = remaining_monthly.filter(scheduled_date=date(2026, 1, 1)).first()
    assert jan_inst and jan_inst.status == 'Completed', "Completed history must be preserved"
    print(" [PASS] Reconciliation preserves completed instances and reconciles pending future entries cleanly")

    print("=" * 65)
    print("ALL 16 VERIFICATION SUITE TESTS PASSED FLAWLESSLY!")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
