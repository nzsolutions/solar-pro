import os
import sys
import json
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarpro_core.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from apps.dynamic_forms.models import DynamicForm, FormSubmission
from apps.operations.models import Project
from apps.employees.models import Employee
from apps.dynamic_forms.views import forms_store, forms_update, form_submissions_index
from apps.api.views import submit_form
from apps.dynamic_forms.flag_service import evaluate_form_submission

def run_tests():
    print("=" * 60)
    print("RUNNING COMPREHENSIVE TESTS: FORM FLAGS & FLAG ALERTS")
    print("=" * 60)
    rf = RequestFactory()

    # 1. Setup Test Data
    project = Project.objects.first()
    if not project:
        project = Project.objects.create(client_name="Test Solar Site", company_id=1)
    
    employee = Employee.objects.first()
    if not employee:
        employee = Employee.objects.create(name="Test Employee", email="test@solar.com", company_id=1)

    # -------------------------------------------------------------
    # TEST 1: Flag Evaluation Service - All Operators & Types
    # -------------------------------------------------------------
    print("\n--- TEST 1: Flag Service Comparison Logic ---")
    schema_test = {
        'columns': ['Block 01', 'Block 02'],
        'sections': [
            {
                'name': 'Inverter Checks',
                'rows': [
                    {'name': 'Cleaning Status', 'type': 'ok_nok', 'unit': ''},
                    {'name': 'Operating Temp', 'type': 'number', 'unit': '°C'},
                    {'name': 'Physical Condition', 'type': 'text', 'unit': ''}
                ]
            }
        ],
        'flags': [
            {'question': 'Cleaning Status', 'question_type': 'ok_nok', 'operator': 'equals', 'value': 'NOK'},
            {'question': 'Operating Temp', 'question_type': 'number', 'operator': 'greater_than', 'value': '75'},
            {'question': 'Physical Condition', 'question_type': 'text', 'operator': 'contains', 'value': 'damage'}
        ]
    }

    # Case A: Matches Cleaning Status = NOK and Operating Temp > 75
    sub_data_1 = {
        'sections': [
            {
                'name': 'Inverter Checks',
                'rows': [
                    {'name': 'Cleaning Status', 'answers': {'Block 01': 'NOK', 'Block 02': 'OK'}},
                    {'name': 'Operating Temp', 'answers': {'Block 01': '82 °C', 'Block 02': '65'}},
                    {'name': 'Physical Condition', 'answers': {'Block 01': 'Normal', 'Block 02': 'Good'}}
                ]
            }
        ]
    }
    is_flg, details = evaluate_form_submission(schema_test, sub_data_1)
    assert is_flg is True, "Expected submission 1 to be flagged"
    assert len(details) == 2, f"Expected 2 flagged items, got {len(details)}"
    print("  ✓ Flagged 2 matched conditions (OK/NOK synonym and numeric > threshold)")

    # Case B: Case-insensitive 'no' matching 'NOK'
    sub_data_case = {
        'sections': [
            {
                'name': 'Inverter Checks',
                'rows': [
                    {'name': 'Cleaning Status', 'answers': {'Block 01': 'no'}}
                ]
            }
        ]
    }
    is_flg, details = evaluate_form_submission(schema_test, sub_data_case)
    assert is_flg is True, "Expected 'no' to match 'NOK' flag"
    print("  ✓ Handled case-insensitive & synonym matching ('no' matched 'NOK')")

    # Case C: Clean submission matching none
    sub_data_clean = {
        'sections': [
            {
                'name': 'Inverter Checks',
                'rows': [
                    {'name': 'Cleaning Status', 'answers': {'Block 01': 'OK', 'Block 02': 'OK'}},
                    {'name': 'Operating Temp', 'answers': {'Block 01': '60 °C', 'Block 02': '62'}},
                    {'name': 'Physical Condition', 'answers': {'Block 01': 'Normal', 'Block 02': 'Good'}}
                ]
            }
        ]
    }
    is_flg, details = evaluate_form_submission(schema_test, sub_data_clean)
    assert is_flg is False, "Expected clean submission not to be flagged"
    assert len(details) == 0
    print("  ✓ Clean submission correctly evaluated as NOT flagged")

    # -------------------------------------------------------------
    # TEST 2: Create Form with Flags via forms_store
    # -------------------------------------------------------------
    print("\n--- TEST 2: Dynamic Form Creation with Flags ---")
    form_schema_payload = {
        'columns': ['Unit 01'],
        'sections': [
            {
                'name': 'Safety Inspection',
                'rows': [
                    {'name': 'Emergency Stop Functional?', 'type': 'ok_nok', 'unit': ''},
                    {'name': 'DC Voltage', 'type': 'number', 'unit': 'V'}
                ]
            }
        ],
        'flags': [
            {'question': 'Emergency Stop Functional?', 'question_type': 'ok_nok', 'operator': 'equals', 'value': 'NOK'},
            {'question': 'DC Voltage', 'question_type': 'number', 'operator': 'less_than', 'value': '400'}
        ]
    }

    from django.contrib.messages.storage.fallback import FallbackStorage

    req = rf.post('/admin/forms/store', {
        'form_name': 'Automated Test Matrix Form with Flags',
        'description': 'Created by test suite',
        'form_schema': json.dumps(form_schema_payload),
        'project_ids[]': [str(project.id)]
    })
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(req)
    req.session['company_id'] = 1
    req.session['user_id'] = 1
    req.session['is_admin'] = 1
    req.session.save()
    setattr(req, '_messages', FallbackStorage(req))

    resp = forms_store(req)
    assert resp.status_code == 302, f"Expected redirect, got {resp.status_code}"
    created_form = DynamicForm.objects.filter(form_name='Automated Test Matrix Form with Flags').first()
    assert created_form is not None, "Form was not created in DB"
    assert 'flags' in created_form.form_schema, "Flags key missing from form_schema"
    assert len(created_form.form_schema['flags']) == 2, "Expected 2 flags saved"
    print("  ✓ DynamicForm created and flags persisted in form_schema")

    # -------------------------------------------------------------
    # TEST 3: Update Form Flags via forms_update
    # -------------------------------------------------------------
    print("\n--- TEST 3: Form Edit & Update Flags ---")
    form_schema_payload['flags'].append({
        'question': 'DC Voltage',
        'question_type': 'number',
        'operator': 'greater_than',
        'value': '900'
    })
    req_update = rf.post(f'/admin/forms/{created_form.id}/update', {
        'form_name': 'Automated Test Matrix Form with Flags (Updated)',
        'description': 'Updated description',
        'form_schema': json.dumps(form_schema_payload),
        'project_ids[]': [str(project.id)]
    })
    middleware.process_request(req_update)
    req_update.session['company_id'] = 1
    req_update.session['user_id'] = 1
    req_update.session['is_admin'] = 1
    req_update.session.save()
    setattr(req_update, '_messages', FallbackStorage(req_update))

    resp_up = forms_update(req_update, created_form.id)
    assert resp_up.status_code == 302
    created_form.refresh_from_db()
    assert len(created_form.form_schema['flags']) == 3, f"Expected 3 flags after update, got {len(created_form.form_schema['flags'])}"
    print("  ✓ DynamicForm flags updated and saved successfully (3 flags)")

    # -------------------------------------------------------------
    # TEST 4: Mobile API Form Submission with Flag Trigger
    # -------------------------------------------------------------
    print("\n--- TEST 4: Mobile API Submission (Flagged) ---")
    api_payload_flagged = {
        'emp_id': employee.id,
        'form_id': created_form.id,
        'project_id': project.id,
        'submission_data': json.dumps({
            'sections': [
                {
                    'name': 'Safety Inspection',
                    'rows': [
                        {'name': 'Emergency Stop Functional?', 'answers': {'Unit 01': 'NOK'}},
                        {'name': 'DC Voltage', 'answers': {'Unit 01': '350 V'}}  # < 400 V!
                    ]
                }
            ]
        })
    }
    req_api_1 = rf.post('/api/submit-form', json.dumps(api_payload_flagged), content_type='application/json')
    resp_api_1 = submit_form(req_api_1)
    assert resp_api_1.status_code == 201, f"Expected HTTP 201, got {resp_api_1.status_code}"
    res_json_1 = json.loads(resp_api_1.content)
    assert res_json_1.get('success') is True, "Submission was rejected or errored"
    sub_id_1 = res_json_1.get('submission_id')
    
    sub_rec_1 = FormSubmission.objects.get(id=sub_id_1)
    assert sub_rec_1.is_flagged is True, "Submission record is_flagged should be True"
    assert len(sub_rec_1.flagged_details) == 2, f"Expected 2 flagged items in DB record, got {len(sub_rec_1.flagged_details)}"
    print(f"  ✓ Flagged submission saved with HTTP 201 (ID: {sub_id_1})")
    print(f"    is_flagged: {sub_rec_1.is_flagged}")
    print(f"    flagged_details: {sub_rec_1.flagged_details}")

    # -------------------------------------------------------------
    # TEST 5: Mobile API Form Submission (Clean - Not Flagged)
    # -------------------------------------------------------------
    print("\n--- TEST 5: Mobile API Submission (Clean / Unflagged) ---")
    api_payload_clean = {
        'emp_id': employee.id,
        'form_id': created_form.id,
        'project_id': project.id,
        'submission_data': json.dumps({
            'sections': [
                {
                    'name': 'Safety Inspection',
                    'rows': [
                        {'name': 'Emergency Stop Functional?', 'answers': {'Unit 01': 'OK'}},
                        {'name': 'DC Voltage', 'answers': {'Unit 01': '650 V'}}
                    ]
                }
            ]
        })
    }
    req_api_2 = rf.post('/api/submit-form', json.dumps(api_payload_clean), content_type='application/json')
    resp_api_2 = submit_form(req_api_2)
    assert resp_api_2.status_code == 201
    res_json_2 = json.loads(resp_api_2.content)
    sub_id_2 = res_json_2.get('submission_id')
    sub_rec_2 = FormSubmission.objects.get(id=sub_id_2)
    assert sub_rec_2.is_flagged is False, "Clean submission is_flagged should be False"
    assert len(sub_rec_2.flagged_details) == 0, "Clean submission should have 0 flagged_details"
    print(f"  ✓ Clean submission saved with HTTP 201 (ID: {sub_id_2}, is_flagged=False)")

    # -------------------------------------------------------------
    # TEST 6: All Form Submissions View UI Rendering
    # -------------------------------------------------------------
    print("\n--- TEST 6: All Form Submissions View UI & Modal ---")
    req_view = rf.get('/admin/form-submissions')
    middleware.process_request(req_view)
    req_view.session['company_id'] = 1
    req_view.session['user_id'] = 1
    req_view.session['is_admin'] = 1
    req_view.session.save()
    setattr(req_view, '_messages', FallbackStorage(req_view))

    resp_view = form_submissions_index(req_view)
    assert resp_view.status_code == 200
    html_content = resp_view.content.decode('utf-8')

    # Check row highlighting for flagged submission
    assert 'background-color: #FEF2F2;' in html_content, "Flagged row highlight #FEF2F2 not found in HTML"
    # Check alert icon button
    assert 'bi-exclamation-triangle-fill' in html_content, "Alert icon not found in HTML"
    # Check modal content for sub_id_1
    assert f'flagModal{sub_id_1}' in html_content, f"Modal #flagModal{sub_id_1} not found in HTML"
    assert 'Flagged Checkpoints / Questions' in html_content, "Flag details header not found in modal"
    assert 'Emergency Stop Functional?' in html_content, "Flagged question not found in modal"
    assert 'NOK' in html_content, "Flagged answer not found in modal"

    print("  ✓ Row highlighting (#FEF2F2) verified")
    print("  ✓ Alert icon (bi-exclamation-triangle-fill) verified")
    print("  ✓ Flag Alert Modal with question, answer, and condition verified")

    # -------------------------------------------------------------
    # Cleanup Test Form & Submissions
    # -------------------------------------------------------------
    sub_rec_1.delete()
    sub_rec_2.delete()
    created_form.delete()
    print("\n--- Cleaned up temporary test records ---")

    print("\n" + "=" * 60)
    print("ALL 6 TEST SUITES PASSED (100%) - ZERO FAILURES")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
