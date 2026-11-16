import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarpro_core.settings')
django.setup()

from django.test import Client
from apps.masters.models import (
    ActivityMaster,
    ActivityFormConfiguration,
    ActivityFormField,
    ActivityFormFieldOption,
    ActivityFormPhotoSetting,
    ActivityFormValidationRule,
)
from apps.masters.form_builder_service import ActivityFormService

def run_tests():
    print("=" * 60)
    print("ACTIVITY FORM BUILDER VERIFICATION TEST SUITE")
    print("=" * 60)

    # 1. Setup client and admin login
    client = Client()
    login_res = client.post('/admin/login', {'email': 'admin@solarpro.com', 'password': 'password123'}, follow=True)
    assert login_res.status_code == 200 and '/admin/dashboard' in login_res.request['PATH_INFO'], "Admin login failed"
    print(" [PASS] Admin authentication successful")

    # 2. Setup or get test Activity
    activity, created = ActivityMaster.objects.get_or_create(
        activity_title="Battery Check Test Activity",
        defaults={
            "description": "Standard battery check and voltage test",
            "default_frequency": "Monthly",
            "status": "Active"
        }
    )
    print(f" [PASS] Activity test fixture ready: {activity.activity_title} (ID: {activity.id})")

    # 3. Test GET Form Builder page
    res = client.get(f"/admin/activities/{activity.id}/form-builder")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert "Activity Form Builder" in res.content.decode('utf-8')
    print(" [PASS] GET /admin/activities/<id>/form-builder rendered successfully (200 OK)")

    # 4. Test Pre-built Template loading and Service
    templates = ActivityFormService.get_prebuilt_templates()
    assert "battery_check" in templates
    assert "solar_panel_cleaning" in templates
    battery_template = templates["battery_check"]
    print(" [PASS] Pre-built templates loaded: Battery Check & Solar Panel Cleaning templates verified")

    # 5. Test POST Save Form Configuration
    payload = {
        "form_title": "Battery Check Form",
        "description": "Routine battery maintenance checklist",
        "fields": [
            {
                "id": "field_condition",
                "field_label": "Battery Condition",
                "field_type": "yes_no",
                "is_required": True,
                "field_order": 1,
                "settings": {},
                "options": [],
                "validation_rules": [
                    {
                        "rule_type": "business_exception",
                        "rule_name": "Condition Check",
                        "condition_operator": "equals",
                        "expected_value": "Yes",
                        "error_message": "Battery condition is not satisfactory!"
                    }
                ]
            },
            {
                "id": "field_voltage",
                "field_label": "Battery Voltage (V)",
                "field_type": "number",
                "is_required": True,
                "field_order": 2,
                "settings": {"min_value": 0, "max_value": 24},
                "options": [],
                "validation_rules": [
                    {
                        "rule_type": "business_exception",
                        "rule_name": "Voltage Range",
                        "condition_operator": "between",
                        "min_value": 8.0,
                        "max_value": 14.5,
                        "error_message": "Battery voltage is below recommended minimum (8.0V)!"
                    }
                ]
            },
            {
                "id": "field_temp",
                "field_label": "Battery Temperature",
                "field_type": "short_text",
                "is_required": False,
                "field_order": 3,
                "settings": {"max_length": 50},
                "options": [],
                "validation_rules": []
            },
            {
                "id": "field_status",
                "field_label": "Status",
                "field_type": "dropdown",
                "is_required": True,
                "field_order": 4,
                "settings": {},
                "options": [
                    {"label": "Passed", "value": "passed"},
                    {"label": "Needs Repair", "value": "needs_repair"},
                    {"label": "Critical Failure", "value": "critical"}
                ],
                "validation_rules": [
                    {
                        "rule_type": "business_exception",
                        "rule_name": "Pass Status Check",
                        "condition_operator": "equals",
                        "expected_value": "passed",
                        "error_message": "Status is not Passed!"
                    }
                ]
            }
        ],
        "photo_settings": {
            "enable_photo_capture": True,
            "before_photo_required": True,
            "after_photo_required": True,
            "optional_photo": False,
            "photo_instructions": "Direct camera capture required.",
            "capture_timestamp_required": True,
            "submission_timestamp_required": True,
            "gps_coordinates_required": True
        }
    }

    save_res = client.post(
        f"/admin/activities/{activity.id}/form-builder/save",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert save_res.status_code == 200, f"Expected 200, got {save_res.status_code}: {save_res.content.decode()}"
    save_data = save_res.json()
    assert save_data.get("success") is True
    print(" [PASS] POST /admin/activities/<id>/form-builder/save persisted successfully")

    # 6. Verify Database State
    form_config = ActivityFormConfiguration.objects.get(activity=activity)
    assert form_config.fields.count() == 4
    photo_setting = form_config.photo_settings
    assert photo_setting.enable_photo_capture is True
    assert photo_setting.before_photo_required is True
    assert photo_setting.after_photo_required is True
    assert photo_setting.gps_coordinates_required is True

    # Check ActivityMaster synchronized
    activity.refresh_from_db()
    assert activity.photo_required is True
    assert activity.form is not None
    print(" [PASS] Database persistence & ActivityMaster synchronization verified (fields, rules, photo settings, DynamicForm)")

    # 7. Test Exception & Validation Rules Evaluation
    # Test case A: Battery voltage 7.5 (valid number, but triggers business exception: below 8.0)
    eval_payload = {
        "fields": payload["fields"],
        "values": {
            "field_condition": "Yes",
            "field_voltage": "7.5",
            "field_status": "passed"
        }
    }
    eval_res = client.post(
        "/admin/activities/form-builder/evaluate-preview",
        data=json.dumps(eval_payload),
        content_type="application/json"
    )
    eval_data = eval_res.json()
    assert eval_data["is_valid"] is True, "Syntax should be valid"
    assert eval_data["has_exceptions"] is True, "7.5V must trigger business exception"
    assert any("below recommended minimum" in exc["message"] for exc in eval_data["exceptions"])
    print(" [PASS] Exception Evaluation: 7.5V correctly identified as Business Exception (< 8.0V)")

    # Test case B: Battery voltage 8.5 (valid number, passes business rule)
    eval_payload["values"]["field_voltage"] = "8.5"
    eval_res2 = client.post(
        "/admin/activities/form-builder/evaluate-preview",
        data=json.dumps(eval_payload),
        content_type="application/json"
    )
    eval_data2 = eval_res2.json()
    assert eval_data2["is_valid"] is True
    assert eval_data2["has_exceptions"] is False
    print(" [PASS] Normal Validation: 8.5V passes without exception and is not flagged as error")

    # Test case C: Battery condition "No" (expected "Yes" -> triggers exception)
    eval_payload["values"]["field_condition"] = "No"
    eval_res3 = client.post(
        "/admin/activities/form-builder/evaluate-preview",
        data=json.dumps(eval_payload),
        content_type="application/json"
    )
    eval_data3 = eval_res3.json()
    assert eval_data3["has_exceptions"] is True
    assert any("field_condition" in exc["field_id"] for exc in eval_data3["exceptions"])
    print(" [PASS] Expected Value Exception: 'No' response triggers expected-value exception")

    # Test case D: Missing required field (normal validation error, not exception)
    eval_payload["values"].pop("field_voltage")
    eval_res4 = client.post(
        "/admin/activities/form-builder/evaluate-preview",
        data=json.dumps(eval_payload),
        content_type="application/json"
    )
    eval_data4 = eval_res4.json()
    assert eval_data4["is_valid"] is False
    assert "field_voltage" in eval_data4["validation_errors"]
    print(" [PASS] Syntax Validation: Missing required field identified as normal validation error")

    # 8. Re-saving with reordered/updated fields (no duplicate field records)
    payload["fields"].pop(2) # Remove temperature field
    save_res2 = client.post(
        f"/admin/activities/{activity.id}/form-builder/save",
        data=json.dumps(payload),
        content_type="application/json"
    )
    assert save_res2.status_code == 200
    form_config.refresh_from_db()
    assert form_config.fields.count() == 3
    print(" [PASS] Re-saving / Reopening updates configuration cleanly without duplicate records")

    print("=" * 60)
    print("ALL ACTIVITY FORM BUILDER TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
