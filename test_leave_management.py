import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarpro_core.settings')
django.setup()

from django.test import Client
from apps.employees.models import Employee
from apps.masters.models import LeaveRequest, DepartmentMaster, DesignationMaster

def run_tests():
    print("=== Testing Leave Management Module ===")
    client = Client()

    # 1. Setup Test Employee
    dept, _ = DepartmentMaster.objects.get_or_create(id=999, defaults={'department_name': 'Operations Test'})
    desig, _ = DesignationMaster.objects.get_or_create(id=999, defaults={'designation_name': 'Solar Tech Test', 'department_id': dept.id})
    emp, _ = Employee.objects.get_or_create(
        id=9999,
        defaults={
            'name': 'Test Leave Employee',
            'app_username': 'test_leave_emp',
            'app_password': 'hash',
            'role': desig.id,
            'status': 'active',
            'email': 'testleave@solarpro.local'
        }
    )
    print(f"[OK] Test employee ready: {emp.name} (ID: {emp.id})")

    # Clean existing test leaves
    LeaveRequest.objects.filter(employee=emp).delete()

    # 2. Test Mobile API: Apply Leave (Success)
    post_data = {
        'emp_id': emp.id,
        'leave_type': 'Sick Leave',
        'start_date': '2026-12-01',
        'end_date': '2026-12-03',
        'reason': 'Medical recovery and doctor consultation',
    }
    resp = client.post('/api/apply-leave', data=json.dumps(post_data), content_type='application/json')
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.content}"
    res_json = resp.json()
    assert res_json['success'] is True
    leave1_id = res_json['data']['leave_id']
    assert float(res_json['data']['days_count']) == 3.0
    print(f"[OK] Step 1: Employee submitted leave via POST /api/apply-leave (ID: {leave1_id}, Days: {res_json['data']['days_count']})")

    # 3. Test Mobile API: Overlapping prevention
    resp_overlap = client.post('/api/apply-leave', data=json.dumps({
        'emp_id': emp.id,
        'leave_type': 'Casual Leave',
        'start_date': '2026-12-02',
        'end_date': '2026-12-04',
        'reason': 'Overlapping request'
    }), content_type='application/json')
    assert resp_overlap.status_code == 409, f"Expected 409 for overlap, got {resp_overlap.status_code}"
    print(f"[OK] Step 2: Overlapping leave prevented (HTTP 409 Conflict)")

    # 4. Test Mobile API: Submit Second Leave for Rejection Test
    resp2 = client.post('/api/apply-leave', data=json.dumps({
        'emp_id': emp.id,
        'leave_type': 'Casual Leave',
        'start_date': '2026-12-10',
        'end_date': '2026-12-11',
        'reason': 'Personal errands'
    }), content_type='application/json')
    assert resp2.status_code == 201
    leave2_id = resp2.json()['data']['leave_id']
    print(f"[OK] Step 3: Second leave submitted (ID: {leave2_id})")

    # 5. Test Mobile API: Get Employee Leaves
    get_resp = client.get(f'/api/get-employee-leaves?emp_id={emp.id}')
    assert get_resp.status_code == 200
    leaves_data = get_resp.json()
    assert leaves_data['summary']['pending'] == 2
    assert len(leaves_data['data']) == 2
    print(f"[OK] Step 4: GET /api/get-employee-leaves retrieved 2 pending leaves")

    # 6. Test Admin Session: View Leave Management Index
    session = client.session
    session['user_id'] = 1
    session['is_admin'] = 1
    session['name'] = 'Super Admin'
    session.save()

    index_resp = client.get('/admin/leave-management')
    assert index_resp.status_code == 200
    assert b"Leave Management" in index_resp.content
    assert b"Employee Leave Requests" in index_resp.content
    print(f"[OK] Step 5: Admin Leave Management index rendered successfully (HTTP 200)")

    # 7. Test Admin Review Detail API
    detail_resp = client.get(f'/admin/leave-management/{leave1_id}/detail')
    assert detail_resp.status_code == 200
    detail_json = detail_resp.json()
    assert detail_json['success'] is True
    assert detail_json['data']['employee_name'] == emp.name
    print(f"[OK] Step 6: Admin viewed request details via modal endpoint (HTTP 200)")

    # 8. Test Admin Approve Leave
    approve_resp = client.post(f'/admin/leave-management/{leave1_id}/approve', {'admin_remarks': 'Approved by HR Director'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert approve_resp.status_code == 200
    leave1 = LeaveRequest.objects.get(id=leave1_id)
    assert leave1.status == 'approved'
    assert leave1.action_by == 'Super Admin'
    assert leave1.action_at is not None
    assert leave1.admin_remarks == 'Approved by HR Director'
    print(f"[OK] Step 7: Admin approved leave #{leave1_id} officially (Status: approved, Approver: {leave1.action_by})")

    # 9. Test Admin Reject Leave (Validation: Mandatory reason)
    reject_fail = client.post(f'/admin/leave-management/{leave2_id}/reject', {'rejection_reason': ''}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert reject_fail.status_code == 422
    print(f"[OK] Step 8: Rejection without mandatory reason rejected with 422")

    # 10. Test Admin Reject Leave (Success)
    reject_resp = client.post(f'/admin/leave-management/{leave2_id}/reject', {
        'rejection_reason': 'Critical project milestone on those dates',
        'admin_remarks': 'Please re-apply for next week'
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert reject_resp.status_code == 200
    leave2 = LeaveRequest.objects.get(id=leave2_id)
    assert leave2.status == 'rejected'
    assert leave2.rejection_reason == 'Critical project milestone on those dates'
    assert leave2.action_by == 'Super Admin'
    print(f"[OK] Step 9: Admin rejected leave #{leave2_id} with mandatory reason")

    # 11. Test Mobile App Verification: Verify Employee Sees Updated Statuses
    verify_resp = client.get(f'/api/get-employee-leaves?emp_id={emp.id}')
    assert verify_resp.status_code == 200
    verify_json = verify_resp.json()
    assert verify_json['summary']['approved'] == 1
    assert verify_json['summary']['rejected'] == 1
    assert verify_json['summary']['pending'] == 0

    records = {r['id']: r for r in verify_json['data']}
    assert records[leave1_id]['status'] == 'approved'
    assert records[leave1_id]['admin_remarks'] == 'Approved by HR Director'
    assert records[leave2_id]['status'] == 'rejected'
    assert records[leave2_id]['rejection_reason'] == 'Critical project milestone on those dates'
    print(f"[OK] Step 10: Mobile API reflected approved and rejected states accurately to the employee!")

    # 12. Clean up test records
    LeaveRequest.objects.filter(employee=emp).delete()
    emp.delete()
    desig.delete()
    dept.delete()
    print("[SUCCESS] All 10 verification steps passed flawlessly!")

if __name__ == '__main__':
    run_tests()
