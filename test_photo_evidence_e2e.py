import os
import sys
import json
import base64
import django
from io import BytesIO

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarpro_core.settings')
django.setup()

from django.test import Client
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.employees.models import Employee
from apps.operations.models import Project
from apps.dynamic_forms.models import DynamicForm, FormSubmission
from apps.masters.models import (
    ActivityMaster,
    ActivityFormConfiguration,
    ActivityFormField,
    ActivityFormPhotoSetting,
)
from apps.masters.form_builder_service import ActivityFormService


def generate_test_jpeg(color=(255, 100, 50)):
    """Generates a minimal valid binary JPEG in-memory."""
    # 1x1 or small image using PIL or raw JPEG bytes
    try:
        from PIL import Image
        img = Image.new('RGB', (100, 100), color=color)
        buf = BytesIO()
        img.save(buf, format='JPEG')
        return buf.getvalue()
    except ImportError:
        # Fallback minimal 1x1 JPEG
        return b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9'


def run_e2e_photo_verification():
    print("=" * 70)
    print("SOLARPRO FORM BUILDER - PHOTO EVIDENCE & SUBMISSION VERIFICATION")
    print("=" * 70)

    client = Client()

    # 1. Admin login
    login_res = client.post('/admin/login', {'email': 'admin@solarpro.com', 'password': 'password123'}, follow=True)
    assert login_res.status_code == 200, "Admin login failed"
    print(" [PASS] Step 1: Admin authentication successful")

    # 2. Activity Fixture with Photo Evidence Configuration (Both Before & After Required)
    activity, _ = ActivityMaster.objects.get_or_create(
        activity_title="Solar Inverter & Panel Maintenance",
        defaults={
            "description": "Routine maintenance requiring mandatory Before & After photo evidence",
            "default_frequency": "Monthly",
            "status": "Active"
        }
    )

    form_config = ActivityFormService.get_or_create_form_config(activity)
    form_config.form_title = "Solar Inverter Maintenance Checklist"
    form_config.save()

    photo_setting, _ = ActivityFormPhotoSetting.objects.get_or_create(form_config=form_config)
    photo_setting.enable_photo_capture = True
    photo_setting.before_photo_required = True
    photo_setting.after_photo_required = True
    photo_setting.optional_photo = False
    photo_setting.photo_instructions = "Capture clear before and after maintenance photos using direct camera."
    photo_setting.gps_coordinates_required = True
    photo_setting.capture_timestamp_required = True
    photo_setting.save()

    # Add test fields: a number field, a text field, and a dedicated Photo Evidence field
    form_config.fields.all().delete()
    f1 = ActivityFormField.objects.create(
        form_config=form_config,
        field_label="Inverter Operating Temperature",
        field_type="number",
        is_required=True,
        field_order=1,
        settings={"unit": "°C", "min_value": 0, "max_value": 100}
    )
    f2 = ActivityFormField.objects.create(
        form_config=form_config,
        field_label="Inverter Condition Status",
        field_type="short_text",
        is_required=True,
        field_order=2
    )
    f_photo = ActivityFormField.objects.create(
        form_config=form_config,
        field_label="Solar Panel Array Photo Evidence",
        field_type="photo_capture",
        is_required=True,
        field_order=3,
        settings={"allow_multiple": True, "min_photos": 1, "max_photos": 5}
    )

    # Sync DynamicForm
    ActivityFormService.save_form_from_dict(activity, ActivityFormService.form_to_dict(form_config))
    activity.refresh_from_db()
    dynamic_form = activity.form
    print(f" [PASS] Step 2: Form configuration setup (Form #{dynamic_form.id}) - Mode: Both Before & After Mandatory")

    # 3. Test Mandatory Photo Validation (Reject if Before or After photo is missing)
    # 3a. Attempt without Before photo
    eval_payload_no_before = {
        "fields": ActivityFormService.form_to_dict(form_config)["fields"],
        "values": {str(f1.id): "42.5", str(f2.id): "Operational"},
        "photo_settings": {
            "enable_photo_capture": True,
            "before_photo_required": True,
            "after_photo_required": True
        },
        "photo_data": {
            "before_photos": [],
            "after_photos": ["data:image/jpeg;base64," + base64.b64encode(generate_test_jpeg((0, 255, 0))).decode()]
        }
    }
    eval_res1 = client.post(
        "/admin/activities/form-builder/evaluate-preview",
        data=json.dumps(eval_payload_no_before),
        content_type="application/json"
    )
    eval_data1 = eval_res1.json()
    assert eval_data1["is_valid"] is False, "Should fail validation when Before photo is missing"
    assert "before_photos" in eval_data1["validation_errors"]
    print(" [PASS] Step 3a: Mandatory Validation: Missing Before photo correctly rejected")

    # 3b. Attempt without After photo
    eval_payload_no_after = {
        "fields": ActivityFormService.form_to_dict(form_config)["fields"],
        "values": {str(f1.id): "42.5", str(f2.id): "Operational"},
        "photo_settings": {
            "enable_photo_capture": True,
            "before_photo_required": True,
            "after_photo_required": True
        },
        "photo_data": {
            "before_photos": ["data:image/jpeg;base64," + base64.b64encode(generate_test_jpeg((255, 0, 0))).decode()],
            "after_photos": []
        }
    }
    eval_res2 = client.post(
        "/admin/activities/form-builder/evaluate-preview",
        data=json.dumps(eval_payload_no_after),
        content_type="application/json"
    )
    eval_data2 = eval_res2.json()
    assert eval_data2["is_valid"] is False, "Should fail validation when After photo is missing"
    assert "after_photos" in eval_data2["validation_errors"]
    print(" [PASS] Step 3b: Mandatory Validation: Missing After photo correctly rejected")

    # 4. Generate Real Photo Files:
    # 2 Before Maintenance photos, 2 After Maintenance photos, and 2 Field Photos
    before_img_1 = "data:image/jpeg;base64," + base64.b64encode(generate_test_jpeg((200, 50, 50))).decode()
    before_img_2 = "data:image/jpeg;base64," + base64.b64encode(generate_test_jpeg((180, 70, 70))).decode()

    after_img_1 = "data:image/jpeg;base64," + base64.b64encode(generate_test_jpeg((50, 200, 50))).decode()
    after_img_2 = "data:image/jpeg;base64," + base64.b64encode(generate_test_jpeg((70, 180, 70))).decode()

    field_img_1 = "data:image/jpeg;base64," + base64.b64encode(generate_test_jpeg((50, 100, 200))).decode()
    field_img_2 = "data:image/jpeg;base64," + base64.b64encode(generate_test_jpeg((70, 120, 220))).decode()

    # 5. Submit Form with Real Photos, GPS, and Timestamps
    submission_payload = {
        "values": {
            str(f1.id): "38.5",
            str(f2.id): "Cleaned and Normal",
            str(f_photo.id): "Multiple panel array photos attached"
        },
        "photo_data": {
            "before_photos": [before_img_1, before_img_2],
            "after_photos": [after_img_1, after_img_2],
            "field_photos": {
                str(f_photo.id): [field_img_1, field_img_2]
            }
        },
        "gps_coordinates": {
            "latitude": 19.0760,
            "longitude": 72.8777,
            "accuracy": 4.5
        },
        "timestamps": {
            "submission_time": "16 Nov 2026, 06:45 PM",
            "iso_timestamp": "2026-11-16T18:45:00Z"
        },
        "inspection_details": {
            "status": "Completed",
            "technician_notes": "All inverters inspected, thermal scans optimal, panels washed."
        }
    }

    submit_res = client.post(
        f"/admin/activities/{activity.id}/form-builder/submit-test",
        data=json.dumps(submission_payload),
        content_type="application/json"
    )
    assert submit_res.status_code == 200, f"Submission failed: {submit_res.content.decode()}"
    submit_data = submit_res.json()
    assert submit_data.get("success") is True, "Submission unsuccessful"
    sub_id = submit_data.get("submission_id")
    assert sub_id is not None
    print(f" [PASS] Step 4 & 5: Real submission accepted! Created FormSubmission #{sub_id}")

    # 6. Verify Physical Storage on Disk (media/form_submissions/...)
    sub_record = FormSubmission.objects.get(id=sub_id)
    sub_json = sub_record.submission_data

    # Check Before Photos in DB & on Disk
    saved_before = sub_json["photo_evidence"]["before_photos"]
    assert len(saved_before) == 2, f"Expected 2 before photos, got {len(saved_before)}"
    for idx, p in enumerate(saved_before):
        url = p["url"]
        rel_path = url.replace("/media/", "")
        disk_path = os.path.join(settings.MEDIA_ROOT, rel_path.replace("/", os.sep))
        assert os.path.exists(disk_path), f"File not found on disk: {disk_path}"
        assert os.path.getsize(disk_path) > 0, f"File on disk is empty: {disk_path}"
        print(f"   ✓ Verified Before Photo {idx+1} on disk: {os.path.basename(disk_path)} ({os.path.getsize(disk_path)} bytes)")

    # Check After Photos in DB & on Disk
    saved_after = sub_json["photo_evidence"]["after_photos"]
    assert len(saved_after) == 2, f"Expected 2 after photos, got {len(saved_after)}"
    for idx, p in enumerate(saved_after):
        url = p["url"]
        rel_path = url.replace("/media/", "")
        disk_path = os.path.join(settings.MEDIA_ROOT, rel_path.replace("/", os.sep))
        assert os.path.exists(disk_path), f"File not found on disk: {disk_path}"
        assert os.path.getsize(disk_path) > 0, f"File on disk is empty: {disk_path}"
        print(f"   ✓ Verified After Photo {idx+1} on disk: {os.path.basename(disk_path)} ({os.path.getsize(disk_path)} bytes)")

    # Check Field Photos in DB & on Disk
    saved_field_photos = sub_json["field_photos"].get(str(f_photo.id), [])
    assert len(saved_field_photos) == 2, f"Expected 2 field photos, got {len(saved_field_photos)}"
    for idx, p in enumerate(saved_field_photos):
        url = p["url"]
        rel_path = url.replace("/media/", "")
        disk_path = os.path.join(settings.MEDIA_ROOT, rel_path.replace("/", os.sep))
        assert os.path.exists(disk_path), f"File not found on disk: {disk_path}"
        assert os.path.getsize(disk_path) > 0, f"File on disk is empty: {disk_path}"
        print(f"   ✓ Verified Single Field Multi-Photo {idx+1} on disk: {os.path.basename(disk_path)} ({os.path.getsize(disk_path)} bytes)")

    print(" [PASS] Step 6: All 6 photos physically verified in media/ storage and database references match")

    # 7. Verify GPS and Timestamps
    gps = sub_json.get("gps_coordinates", {})
    assert gps.get("latitude") == 19.0760
    assert gps.get("longitude") == 72.8777
    assert sub_json.get("timestamps", {}).get("submission_time") is not None
    print(" [PASS] Step 7: GPS coordinates and timestamp verified in database")

    # 8. Verify Form Submissions Index Page Rendering
    list_res = client.get("/admin/form-submissions")
    assert list_res.status_code == 200
    list_html = list_res.content.decode("utf-8")
    assert f"Before (2)" in list_html, "Submissions listing should show Before (2) badge"
    assert f"After (2)" in list_html, "Submissions listing should show After (2) badge"
    assert "GPS" in list_html, "Submissions listing should show GPS badge"
    print(" [PASS] Step 8a: Submissions index page renders photo evidence badges & GPS indicators (200 OK)")

    # 9. Verify Submission Details / Edit Page View & Refresh Persistence
    detail_res1 = client.get(f"/admin/form-submissions/{sub_id}/edit")
    assert detail_res1.status_code == 200
    detail_html1 = detail_res1.content.decode("utf-8")

    assert "Before Maintenance Photos" in detail_html1
    assert "After Maintenance Photos" in detail_html1
    assert saved_before[0]["url"] in detail_html1
    assert saved_after[0]["url"] in detail_html1
    assert "19.076" in detail_html1
    assert "72.8777" in detail_html1
    print(" [PASS] Step 8b: Form Submission details page successfully renders Before & After photos and GPS location (200 OK)")

    # Refresh test (repeat GET to ensure retrieval from database & storage on refresh)
    detail_res2 = client.get(f"/admin/form-submissions/{sub_id}/edit")
    assert detail_res2.status_code == 200
    detail_html2 = detail_res2.content.decode("utf-8")
    assert saved_before[0]["url"] in detail_html2
    assert saved_after[0]["url"] in detail_html2
    print(" [PASS] Step 8c: Refresh verified - all data and photos remain intact upon page reload")

    # 10. Also verify API /api/submit-form with multipart file uploads
    employee = Employee.objects.first()
    proj = Project.objects.first()

    raw_before_1 = generate_test_jpeg((100, 200, 255))
    raw_after_1 = generate_test_jpeg((255, 200, 100))

    api_payload = {
        "emp_id": employee.id,
        "form_id": dynamic_form.id,
        "project_id": proj.id if proj else 1,
        "submission_data": json.dumps({
            "fields": {"status": "Passed"},
            "gps_coordinates": {"latitude": 19.1234, "longitude": 72.9876}
        })
    }
    api_files = {
        "before_photos": SimpleUploadedFile("api_before_1.jpg", raw_before_1, content_type="image/jpeg"),
        "after_photos": SimpleUploadedFile("api_after_1.jpg", raw_after_1, content_type="image/jpeg"),
    }
    api_res = client.post("/api/submit-form", {**api_payload, **api_files})
    assert api_res.status_code == 201, f"API submit failed: {api_res.content.decode()}"
    api_data = api_res.json()
    assert api_data.get("success") is True
    api_sub_id = api_data.get("submission_id")
    api_sub_rec = FormSubmission.objects.get(id=api_sub_id)
    assert len(api_sub_rec.submission_data["photo_evidence"]["before_photos"]) == 1
    assert len(api_sub_rec.submission_data["photo_evidence"]["after_photos"]) == 1
    print(f" [PASS] Step 9: API /api/submit-form verified with multipart Before & After photo uploads (#{api_sub_id})")

    print("=" * 70)
    print("ALL 8 PHOTO EVIDENCE & SUBMISSION REQUIREMENTS FULLY VERIFIED!")
    print("=" * 70)


if __name__ == "__main__":
    run_e2e_photo_verification()
