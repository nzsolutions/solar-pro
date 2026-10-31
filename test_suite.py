import os
import sys
import json
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarpro_core.settings')
django.setup()

from django.test import Client
from apps.employees.models import Employee, EmployeeOTP, EmployeeAttendance
from apps.expenses.models import Expense
from apps.authentication.hashers import LaravelBcryptPasswordHasher


def run_tests():
    print("=" * 60)
    print("SOLARPRO DJANGO END-TO-END VERIFICATION TEST SUITE")
    print("=" * 60)

    c = Client()
    passed = 0
    total = 0

    def assert_test(name, condition, details=""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f" [PASS] {name}")
        else:
            print(f" [FAIL] {name} - {details}")

    # ---------------------------------------------------------
    # TEST 1: Root redirect to login
    # ---------------------------------------------------------
    res = c.get('/')
    assert_test("Root URL redirects to /admin/login", res.status_code == 302 and '/admin/login' in res.url)

    # ---------------------------------------------------------
    # TEST 2: Admin Login Web Page
    # ---------------------------------------------------------
    res = c.get('/admin/login')
    assert_test("Admin Login page renders (200 OK)", res.status_code == 200 and 'SolarPro' in res.content.decode('utf-8'))

    # ---------------------------------------------------------
    # TEST 3: Admin Web Authentication
    # ---------------------------------------------------------
    res = c.post('/admin/login', {'email': 'admin@solarpro.com', 'password': 'password123'}, follow=True)
    assert_test("Admin login succeeds and redirects to dashboard", res.status_code == 200 and '/admin/dashboard' in res.request['PATH_INFO'])

    # ---------------------------------------------------------
    # TEST 4: Admin Dashboard & Operation Pages
    # ---------------------------------------------------------
    res = c.get('/admin/dashboard')
    assert_test("Admin Dashboard renders (200 OK)", res.status_code == 200)

    res = c.get('/admin/projects')
    assert_test("Projects Index renders (200 OK)", res.status_code == 200)

    res = c.get('/admin/stock')
    assert_test("Stock Dashboard renders (200 OK)", res.status_code == 200)

    res = c.get('/admin/forms')
    assert_test("Dynamic Forms Index renders (200 OK)", res.status_code == 200)

    res = c.get('/admin/employee-expenses')
    assert_test("Employee Expenses page renders (200 OK)", res.status_code == 200)

    res = c.get('/admin/reports/projects')
    assert_test("Reports page renders (200 OK)", res.status_code == 200)

    # ---------------------------------------------------------
    # TEST 5: API Login (Employee rahul.sharma)
    # ---------------------------------------------------------
    api_c = Client()  # Fresh client without web session
    res = api_c.post('/api/login', json.dumps({
        'username': 'rahul.sharma',
        'password': 'password123',
        'fcm_token': 'test_fcm_token_123'
    }), content_type='application/json')
    data = res.json()
    assert_test("API Login returns 200 OK for valid employee", res.status_code == 200 and data.get('success') is True, f"status: {res.status_code}, body: {res.content.decode('utf-8')}")
    emp_id = data.get('data', {}).get('id', 1)

    # ---------------------------------------------------------
    # TEST 6: API Login (Invalid Password Check)
    # ---------------------------------------------------------
    res = api_c.post('/api/login', json.dumps({
        'username': 'rahul.sharma',
        'password': 'wrongpassword'
    }), content_type='application/json')
    assert_test("API Login returns 401 for invalid credentials", res.status_code == 401)

    # ---------------------------------------------------------
    # TEST 7: API Get Employee Profile
    # ---------------------------------------------------------
    res = api_c.post('/api/get-employee-profile', json.dumps({'employee_id': emp_id}), content_type='application/json')
    data = res.json()
    assert_test("API Get Employee Profile returns 200 OK", res.status_code == 200 and data.get('data', {}).get('name') == 'Rahul Sharma')

    # ---------------------------------------------------------
    # TEST 8: API Get Projects by Employee ID
    # ---------------------------------------------------------
    res = api_c.post('/api/get-project-by-employee-id', json.dumps({'employee_id': emp_id}), content_type='application/json')
    data = res.json()
    assert_test("API Get Projects returns 200 OK and assigned project", res.status_code == 200 and len(data.get('data', [])) > 0)
    project_id = data.get('data', [])[0].get('id') if data.get('data') else 1

    # ---------------------------------------------------------
    # TEST 9: API Get Stock by Project ID
    # ---------------------------------------------------------
    res = api_c.get(f'/api/get-stock-by-project-id?project_id={project_id}')
    data = res.json()
    assert_test("API Get Stock by Project ID returns 200 OK", res.status_code == 200 and data.get('success') is True)

    # ---------------------------------------------------------
    # TEST 10: API Expense Categories
    # ---------------------------------------------------------
    res = api_c.post('/api/get-expense-categories')
    data = res.json()
    assert_test("API Get Expense Categories returns 200 OK", res.status_code == 200 and len(data.get('data', [])) > 0)
    exp_cat_id = data.get('data', [])[0].get('id')

    # ---------------------------------------------------------
    # TEST 11: API Add Expense
    # ---------------------------------------------------------
    res = api_c.post('/api/add-expense', {
        'emp_id': emp_id,
        'exp_cat_id': exp_cat_id,
        'project_id': project_id,
        'amount': '1450.00',
        'date': '2026-10-30',
        'emp_comment': 'Site visit taxi fare & lunch'
    })
    data = res.json()
    assert_test("API Add Expense returns 201 Created", res.status_code == 201 and data.get('success') is True)

    # ---------------------------------------------------------
    # TEST 12: API Get Employee Expenses
    # ---------------------------------------------------------
    res = api_c.get(f'/api/get-employee-expenses?emp_id={emp_id}')
    data = res.json()
    assert_test("API Get Employee Expenses returns 200 OK", res.status_code == 200 and len(data.get('data', [])) > 0)

    # ---------------------------------------------------------
    # TEST 13: API Get Dynamic Forms
    # ---------------------------------------------------------
    res = api_c.get(f'/api/get-dynamic-forms?emp_id={emp_id}&project_id={project_id}')
    data = res.json()
    assert_test("API Get Dynamic Forms returns 200 OK", res.status_code == 200 and len(data.get('data', [])) > 0)
    form_id = data.get('data', [])[0].get('id')

    # ---------------------------------------------------------
    # TEST 14: API Submit Dynamic Form Snapshot
    # ---------------------------------------------------------
    submission_payload = {
        'emp_id': emp_id,
        'form_id': form_id,
        'project_id': project_id,
        'submission_data': {
            'columns': ['Block 01', 'Block 02'],
            'sections': [
                {
                    'name': 'PV Module & String Checks',
                    'rows': [
                        {'name': 'String Open Circuit Voltage (Voc)', 'answers': {'Block 01': '650', 'Block 02': '648'}}
                    ]
                }
            ]
        }
    }
    res = api_c.post('/api/submit-form', json.dumps(submission_payload), content_type='application/json')
    data = res.json()
    assert_test("API Submit Dynamic Form returns 201 Created", res.status_code == 201 and data.get('success') is True)

    # ---------------------------------------------------------
    # TEST 15: API Get Employee Submissions
    # ---------------------------------------------------------
    res = api_c.get(f'/api/get-employee-submissions/{emp_id}')
    data = res.json()
    assert_test("API Get Employee Submissions returns 200 OK", res.status_code == 200 and len(data.get('data', [])) > 0)

    # ---------------------------------------------------------
    # TEST 16: API Punch In (Within 500m Site GPS: 19.0657, 72.8687)
    # ---------------------------------------------------------
    # Clear any active punch in
    EmployeeAttendance.objects.filter(employee_id=emp_id, punch_out__isnull=True).delete()

    res = api_c.post('/api/punch-in', json.dumps({
        'employee_id': emp_id,
        'latitude': 19.0657,
        'longitude': 72.8687
    }), content_type='application/json')
    data = res.json()
    assert_test("API Punch In within geofence returns 200 OK", res.status_code == 200 and data.get('success') is True)

    # ---------------------------------------------------------
    # TEST 17: API Punch Out (Within 500m Site GPS)
    # ---------------------------------------------------------
    res = api_c.post('/api/punch-out', json.dumps({
        'employee_id': emp_id,
        'latitude': 19.0657,
        'longitude': 72.8687
    }), content_type='application/json')
    data = res.json()
    assert_test("API Punch Out returns 200 OK with actual_worked calculation", res.status_code == 200 and data.get('success') is True)

    # ---------------------------------------------------------
    # TEST 18: API Employee Graph Analytics
    # ---------------------------------------------------------
    res = api_c.post('/api/employee-graph-analytics', json.dumps({'employee_id': emp_id}), content_type='application/json')
    data = res.json()
    assert_test("API Employee Graph Analytics returns 200 OK", res.status_code == 200 and 'attendance' in data.get('data', {}))

    # ---------------------------------------------------------
    # TEST 19: API Password OTP Flow (Send, Validate, Reset)
    # ---------------------------------------------------------
    res = api_c.post('/api/password/send-otp', json.dumps({'email': 'rahul.sharma@solarpro.com'}), content_type='application/json')
    assert_test("API Password Send OTP returns 200 OK", res.status_code == 200)

    otp_record = EmployeeOTP.objects.filter(employee_id=emp_id).first()
    valid_otp = otp_record.otp if otp_record else "000000"

    res = api_c.post('/api/password/validate-otp', json.dumps({
        'email': 'rahul.sharma@solarpro.com',
        'otp': valid_otp
    }), content_type='application/json')
    assert_test("API Password Validate OTP returns 200 OK", res.status_code == 200)

    res = api_c.post('/api/password/reset', json.dumps({
        'employee_id': emp_id,
        'otp': valid_otp,
        'password': 'NewPassword@2026',
        'password_confirmation': 'NewPassword@2026'
    }), content_type='application/json')
    assert_test("API Password Reset returns 200 OK", res.status_code == 200)

    # Restore default test password
    emp = Employee.objects.filter(id=emp_id).first()
    if emp:
        hasher = LaravelBcryptPasswordHasher()
        emp.app_password = hasher.encode("password123")
        emp.save(update_fields=['app_password'])

    print("=" * 60)
    print(f"TEST RESULTS: {passed} / {total} PASSED ({(passed/total)*100:.1f}%)")
    print("=" * 60)


if __name__ == '__main__':
    run_tests()
