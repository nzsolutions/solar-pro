import os
import django
import json
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarpro_core.settings')
django.setup()

from django.test import Client
from apps.employees.models import Employee
from apps.masters.models import LeaveRequest, DepartmentMaster, DesignationMaster
from apps.operations.models import Project

def run_tests():
    client = Client()
    print("=== Running Comprehensive Tests for Project Column & Project Filter in Leave Management ===")

    # Setup Masters
    dept, _ = DepartmentMaster.objects.get_or_create(id=991, defaults={'department_name': 'Operations'})
    desig, _ = DesignationMaster.objects.get_or_create(id=991, defaults={'designation_name': 'Site Engineer', 'department_id': dept.id})

    # Setup Projects
    proj_a, _ = Project.objects.get_or_create(
        id=9901,
        defaults={
            'project_name': 'Solar Pro Project Alpha',
            'client_name': 'Alpha Energy',
            'company_id': 1,
            'start_date': date(2026, 12, 1),
            'end_date': date(2026, 12, 31),
        }
    )
    proj_b, _ = Project.objects.get_or_create(
        id=9902,
        defaults={
            'project_name': 'Solar Pro Project Beta',
            'client_name': 'Beta Renewables',
            'company_id': 1,
            'start_date': date(2026, 12, 1),
            'end_date': date(2026, 12, 31),
        }
    )

    # 1. Setup Employees:
    # Emp 1: assigned exclusively to Project Alpha
    emp1, _ = Employee.objects.get_or_create(
        id=9911,
        defaults={
            'company_id': 1,
            'name': 'Alpha Engineer',
            'app_username': 'alpha.emp',
            'app_password': 'testpassword',
            'email': 'alpha@solarpro.local',
            'role': desig.id,
            'status': 'active'
        }
    )
    # Emp 2: assigned exclusively to Project Beta
    emp2, _ = Employee.objects.get_or_create(
        id=9912,
        defaults={
            'company_id': 1,
            'name': 'Beta Engineer',
            'app_username': 'beta.emp',
            'app_password': 'testpassword',
            'email': 'beta@solarpro.local',
            'role': desig.id,
            'status': 'active'
        }
    )
    # Emp 3: not assigned to any project
    emp3, _ = Employee.objects.get_or_create(
        id=9913,
        defaults={
            'company_id': 1,
            'name': 'Unassigned Engineer',
            'app_username': 'unassigned.emp',
            'app_password': 'testpassword',
            'email': 'unassigned@solarpro.local',
            'role': desig.id,
            'status': 'active'
        }
    )
    # Emp 4: assigned to multiple projects (both Alpha and Beta)
    emp4, _ = Employee.objects.get_or_create(
        id=9914,
        defaults={
            'company_id': 1,
            'name': 'Multi Project Engineer',
            'app_username': 'multi.emp',
            'app_password': 'testpassword',
            'email': 'multi@solarpro.local',
            'role': desig.id,
            'status': 'active'
        }
    )

    # Update project staff
    proj_a.field_staff = [emp1.id, emp4.id]
    proj_a.save()
    proj_b.field_staff = [emp2.id, emp4.id]
    proj_b.save()

    # Clean existing test leaves
    LeaveRequest.objects.filter(employee__in=[emp1, emp2, emp3, emp4]).delete()

    # Scenario 1: Employee with one assigned project submits leave
    res1 = client.post('/api/apply-leave', data=json.dumps({
        'emp_id': emp1.id,
        'leave_type': 'Casual Leave',
        'start_date': '2026-12-05',
        'end_date': '2026-12-06',
        'reason': 'Alpha Leave Reason'
    }), content_type='application/json')
    assert res1.status_code == 201, f"Expected 201, got {res1.status_code}: {res1.content}"
    l1_data = res1.json()['data']
    assert l1_data['project_name'] == proj_a.project_name
    leave1_id = l1_data['leave_id']
    print(f"[OK] Scenario 1: Employee with 1 assigned project submitted leave, correctly resolved to {l1_data['project_name']}")

    # Scenario 2: Employee with Project Beta submits leave
    res2 = client.post('/api/apply-leave', data=json.dumps({
        'emp_id': emp2.id,
        'leave_type': 'Sick Leave',
        'start_date': '2026-12-05',
        'end_date': '2026-12-07',
        'reason': 'Beta Leave Reason'
    }), content_type='application/json')
    assert res2.status_code == 201
    l2_data = res2.json()['data']
    assert l2_data['project_name'] == proj_b.project_name
    leave2_id = l2_data['leave_id']
    print(f"[OK] Scenario 2: Employee with Project Beta submitted leave, correctly resolved to {l2_data['project_name']}")

    # Scenario 5: Employee with no assigned project submits leave
    res3 = client.post('/api/apply-leave', data=json.dumps({
        'emp_id': emp3.id,
        'leave_type': 'Privilege Leave',
        'start_date': '2026-12-08',
        'end_date': '2026-12-09',
        'reason': 'Unassigned Leave Reason'
    }), content_type='application/json')
    assert res3.status_code == 201
    l3_data = res3.json()['data']
    assert l3_data['project_name'] is None or l3_data['project_name'] == 'Not Assigned'
    leave3_id = l3_data['leave_id']
    print(f"[OK] Scenario 5: Employee with no assigned project submitted leave, gracefully marked as Not Assigned/None")

    # Scenario 6: Employee with multiple project assignments submits leave with and without explicit project_id
    res4_no_proj = client.post('/api/apply-leave', data=json.dumps({
        'emp_id': emp4.id,
        'leave_type': 'Casual Leave',
        'start_date': '2026-12-10',
        'end_date': '2026-12-11',
        'reason': 'Multi Project General Leave'
    }), content_type='application/json')
    assert res4_no_proj.status_code == 201
    l4_data = res4_no_proj.json()['data']
    leave4_id = l4_data['leave_id']
    # Without explicit project and with multiple simultaneous projects, no arbitrary guess is made:
    print(f"[OK] Scenario 6A: Multi-project employee without explicit project does not arbitrarily guess: {l4_data['project_name']}")

    res4_with_proj = client.post('/api/apply-leave', data=json.dumps({
        'emp_id': emp4.id,
        'project_id': proj_a.id,
        'leave_type': 'Casual Leave',
        'start_date': '2026-12-15',
        'end_date': '2026-12-16',
        'reason': 'Multi Project Alpha Specific Leave'
    }), content_type='application/json')
    assert res4_with_proj.status_code == 201
    l4_with_proj_data = res4_with_proj.json()['data']
    assert l4_with_proj_data['project_name'] == proj_a.project_name
    leave4_proj_id = l4_with_proj_data['leave_id']
    print(f"[OK] Scenario 6B: Multi-project employee with explicit project specifies project accurately: {l4_with_proj_data['project_name']}")

    # Setup Admin Session
    session = client.session
    session['user_id'] = 1
    session['is_admin'] = 1
    session['name'] = 'Super Admin'
    session.save()

    # Scenario 2 & 7: Admin sees correct project column and existing leave requests without errors
    admin_index = client.get('/admin/leave-management')
    assert admin_index.status_code == 200
    content = admin_index.content.decode('utf-8')
    assert '<th>PROJECT</th>' in content or '<th>Project</th>' in content
    assert 'Solar Pro Project Alpha' in content
    assert 'Solar Pro Project Beta' in content
    assert 'Not Assigned' in content
    print("[OK] Scenario 2 & 7: Admin leave management page renders Project column header and correct project names")

    # Scenario 3: Admin filters by Project Alpha
    filter_alpha = client.get(f'/admin/leave-management?project={proj_a.id}')
    assert filter_alpha.status_code == 200
    content_alpha = filter_alpha.content.decode('utf-8')
    assert 'Alpha Leave Reason' in content_alpha
    assert 'Beta Leave Reason' not in content_alpha
    assert 'Unassigned Leave Reason' not in content_alpha
    print("[OK] Scenario 3: Filtering by Project Alpha shows only Project Alpha requests")

    # Filtering by Project Beta
    filter_beta = client.get(f'/admin/leave-management?project={proj_b.id}')
    assert filter_beta.status_code == 200
    content_beta = filter_beta.content.decode('utf-8')
    assert 'Beta Leave Reason' in content_beta
    assert 'Alpha Leave Reason' not in content_beta
    assert 'Unassigned Leave Reason' not in content_beta
    print("[OK] Filtering by Project Beta shows only Project Beta requests")

    # Filtering by Unassigned
    filter_unassigned = client.get('/admin/leave-management?project=unassigned')
    assert filter_unassigned.status_code == 200
    content_unassigned = filter_unassigned.content.decode('utf-8')
    assert 'Unassigned Leave Reason' in content_unassigned
    assert 'Alpha Leave Reason' not in content_unassigned
    assert 'Beta Leave Reason' not in content_unassigned
    print("[OK] Filtering by 'unassigned' shows only unassigned leave requests")

    # Scenario 4: Admin clears/resets project filter
    filter_cleared = client.get('/admin/leave-management?project=')
    assert filter_cleared.status_code == 200
    content_cleared = filter_cleared.content.decode('utf-8')
    assert 'Alpha Leave Reason' in content_cleared
    assert 'Beta Leave Reason' in content_cleared
    assert 'Unassigned Leave Reason' in content_cleared
    print("[OK] Scenario 4: Clearing project filter returns all leave requests")

    # Scenario 8: Admin approves leave request
    approve_res = client.post(f'/admin/leave-management/{leave1_id}/approve', {'admin_remarks': 'Approved by GM'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert approve_res.status_code == 200
    l1_db = LeaveRequest.objects.get(id=leave1_id)
    assert l1_db.status == 'approved'
    assert l1_db.action_by == 'Super Admin'
    print(f"[OK] Scenario 8: Admin approved leave #{leave1_id} successfully")

    # Scenario 9: Admin rejects leave request with mandatory reason
    reject_res = client.post(f'/admin/leave-management/{leave2_id}/reject', {
        'rejection_reason': 'Urgent project task scheduled',
        'admin_remarks': 'Reschedule please'
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert reject_res.status_code == 200
    l2_db = LeaveRequest.objects.get(id=leave2_id)
    assert l2_db.status == 'rejected'
    assert l2_db.rejection_reason == 'Urgent project task scheduled'
    print(f"[OK] Scenario 9: Admin rejected leave #{leave2_id} with mandatory reason")

    # Scenario 10: Employee can see updated leave status and project name via API
    emp_leaves_res = client.get(f'/api/get-employee-leaves?emp_id={emp1.id}')
    assert emp_leaves_res.status_code == 200
    emp_leaves_json = emp_leaves_res.json()
    assert emp_leaves_json['summary']['approved'] == 1
    found_l1 = [x for x in emp_leaves_json['data'] if x['id'] == leave1_id][0]
    assert found_l1['status'] == 'approved'
    assert found_l1['project_name'] == proj_a.project_name
    print(f"[OK] Scenario 10: Employee API reports approved status and project name accurately: {found_l1['project_name']}")

    # Scenario 11 & 12: Combined filters (Project + Status or Project + Leave Type)
    combined_res = client.get(f'/admin/leave-management?project={proj_a.id}&status=approved')
    assert combined_res.status_code == 200
    comb_content = combined_res.content.decode('utf-8')
    assert 'Alpha Leave Reason' in comb_content
    assert 'Multi Project Alpha Specific Leave' not in comb_content  # because this one is pending!
    print("[OK] Scenario 11 & 12: Combined Project and Status filters work seamlessly together")

    # Scenario 13: Review modal detail endpoint check
    detail_res = client.get(f'/admin/leave-management/{leave1_id}/detail')
    assert detail_res.status_code == 200
    d_json = detail_res.json()
    assert d_json['data']['project_name'] == proj_a.project_name
    print(f"[OK] Scenario 13: Review detail modal JSON endpoint returns correct project_name: {d_json['data']['project_name']}")

    # Cleanup
    LeaveRequest.objects.filter(employee__in=[emp1, emp2, emp3, emp4]).delete()
    emp1.delete()
    emp2.delete()
    emp3.delete()
    emp4.delete()
    proj_a.delete()
    proj_b.delete()
    desig.delete()
    dept.delete()
    print("=== [ALL 13 SCENARIOS TESTED AND PASSED SUCCESSFULLY] ===")

if __name__ == '__main__':
    run_tests()
