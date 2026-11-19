import os
import uuid
import json
import math
import random
import re
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.authentication.hashers import LaravelBcryptPasswordHasher
from apps.dynamic_forms.models import DynamicForm, FormSubmission
from apps.dynamic_forms.flag_service import evaluate_form_submission
from apps.employees.models import Employee, EmployeeAttendance, EmployeeOTP
from apps.expenses.models import Expense, ExpenseCategory
from apps.inventory.models import AssignedStock, OpeningStock, StockCategory
from apps.masters.models import AttendanceMaster, DocumentTypeMaster, SiteMaster, SMTPConfiguration, LeaveRequest, DesignationMaster, DepartmentMaster, ActivityMaster, ActivityFormConfiguration
from apps.operations.models import (
    Project,
    ProjectDocument,
    ProjectActivity,
    ProjectActivityInstance,
    ProjectActivityPhoto,
    ProjectActivityIssue,
)
from apps.masters.form_builder_service import ActivityFormService

laravel_hasher = LaravelBcryptPasswordHasher()


def verify_employee_password(password, encoded_hash):
    if not encoded_hash:
        return False
    if laravel_hasher.verify(password, encoded_hash):
        return True
    try:
        return check_password(password, encoded_hash)
    except Exception:
        return False


def calculate_distance_in_meters(lat1, lon1, lat2, lon2):
    """
    Haversine formula to calculate the distance between two GPS coordinates in meters.
    """
    earth_radius = 6371000.0  # meters

    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a = math.sin(delta_lat / 2.0) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * (math.sin(delta_lon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return earth_radius * c


def get_request_data(request):
    """
    Helper to extract parameters from JSON body, POST multipart/form-data, or GET query params.
    """
    data = {}
    if request.method in ['POST', 'PUT', 'PATCH']:
        if request.content_type and 'application/json' in request.content_type:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception:
                data = {}
        else:
            data = request.POST.dict()
    else:
        data = request.GET.dict()
    return data


def send_dynamic_smtp_email(to_email, subject, body_text):
    """
    Sends email dynamically using SMTP_Configuration table.
    """
    try:
        smtp = SMTPConfiguration.objects.filter(id=6).first()
        if not smtp:
            smtp = SMTPConfiguration.objects.filter(is_default=1).first()
        if not smtp:
            smtp = SMTPConfiguration.objects.first()

        if not smtp:
            return False, "SMTP configuration not found in database."

        msg = MIMEMultipart()
        msg['From'] = f"{smtp.from_name} <{smtp.from_email}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_text, 'plain'))

        server = smtplib.SMTP(smtp.smtp_host, int(smtp.smtp_port), timeout=15)
        if smtp.smtp_crypto and smtp.smtp_crypto.lower() in ['tls', 'ssl']:
            server.starttls()
        if smtp.smtp_user and smtp.smtp_pass:
            server.login(smtp.smtp_user, smtp.smtp_pass)
        server.sendmail(smtp.from_email, [to_email], msg.as_string())
        server.quit()
        return True, "Email sent successfully."
    except Exception as e:
        return False, str(e)


# -------------------------------------------------------------
# 1. Login API
# -------------------------------------------------------------
@csrf_exempt
def login(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    username = data.get('username')
    password = data.get('password')
    fcm_token = data.get('fcm_token')

    if not username or not password:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed. Username and password are required.',
            'errors': {
                'username': ['The username field is required.'] if not username else [],
                'password': ['The password field is required.'] if not password else []
            }
        }, status=422)

    try:
        employee = Employee.objects.filter(app_username=username).first()
        if not employee or not verify_employee_password(password, employee.app_password):
            return JsonResponse({
                'success': False,
                'message': 'Invalid username or password.'
            }, status=401)

        if employee.status != 'active':
            return JsonResponse({
                'success': False,
                'message': 'Your account is inactive. Please contact the administrator.'
            }, status=403)

        if fcm_token:
            employee.fcm_token = fcm_token
            employee.save(update_fields=['fcm_token', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'Login successful.',
            'data': {
                'id': employee.id,
                'company_id': employee.company_id,
                'name': employee.name,
                'role': employee.role,
                'app_username': employee.app_username,
                'email': employee.email,
                'phone': employee.phone,
                'status': employee.status,
                'fcm_token': employee.fcm_token or None
            }
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred during login.',
            'error': str(e)
        }, status=500)


# -------------------------------------------------------------
# 2. Forgot Password APIs: Send OTP, Validate OTP, Reset
# -------------------------------------------------------------
@csrf_exempt
def send_otp(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    email = data.get('email')

    if not email:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed. Email is required.',
            'errors': {'email': ['The email field is required.']}
        }, status=422)

    try:
        employee = Employee.objects.filter(email=email).first()
        if not employee:
            return JsonResponse({
                'success': False,
                'message': 'No matching employee record found for the provided email address.'
            }, status=404)

        otp = str(random.randint(100000, 999999))
        expires_at = timezone.now() + timedelta(minutes=10)

        EmployeeOTP.objects.update_or_create(
            employee_id=employee.id,
            defaults={'otp': otp, 'expires_at': expires_at}
        )

        smtp = SMTPConfiguration.objects.filter(id=6).first() or SMTPConfiguration.objects.first()
        from_name = smtp.from_name if smtp else 'SolarPro'

        email_body = (
            f"Hello {employee.name},\n\n"
            f"Your OTP for password reset is: {otp}.\n"
            f"This OTP is valid for 10 minutes.\n\n"
            f"If you did not request this, please ignore this email."
        )

        success, _ = send_dynamic_smtp_email(
            employee.email,
            f"Password Reset OTP - {from_name}",
            email_body
        )

        return JsonResponse({
            'success': True,
            'message': 'OTP has been sent successfully to your email address.',
            'data': {'email': employee.email}
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Failed to send OTP email.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def validate_otp(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp or len(str(otp)) != 6:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed. Email and 6-digit OTP are required.',
            'errors': {
                'email': ['Email is required.'] if not email else [],
                'otp': ['A 6-digit OTP is required.'] if not otp or len(str(otp)) != 6 else []
            }
        }, status=422)

    try:
        employee = Employee.objects.filter(email=email).first()
        if not employee:
            return JsonResponse({
                'success': False,
                'message': 'No matching employee record found for the provided email address.'
            }, status=404)

        otp_record = EmployeeOTP.objects.filter(employee_id=employee.id).first()
        if not otp_record:
            return JsonResponse({
                'success': False,
                'message': 'No active OTP request found. Please request a new OTP.'
            }, status=400)

        if otp_record.expires_at < timezone.now():
            return JsonResponse({
                'success': False,
                'message': 'OTP has expired. Please request a new one.'
            }, status=400)

        if str(otp_record.otp).strip() != str(otp).strip():
            return JsonResponse({
                'success': False,
                'message': 'Invalid OTP. Please try again.'
            }, status=400)

        return JsonResponse({
            'success': True,
            'message': 'OTP validated successfully. You may now reset your password.',
            'data': {'employee_id': employee.id}
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while validating OTP.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def reset_password(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    employee_id = data.get('employee_id')
    otp = data.get('otp')
    password = data.get('password')
    password_confirmation = data.get('password_confirmation')

    if not employee_id or not otp or not password or not password_confirmation:
        return JsonResponse({
            'success': False,
            'message': 'Password validation failed.',
            'errors': {'fields': ['All fields are required.']}
        }, status=422)

    if password != password_confirmation:
        return JsonResponse({
            'success': False,
            'message': 'Password validation failed.',
            'errors': {'password_confirmation': ['Passwords do not match.']}
        }, status=422)

    if (len(password) < 6 or
            not re.search(r'[a-z]', password) or
            not re.search(r'[A-Z]', password) or
            not re.search(r'[0-9]', password) or
            not re.search(r'[@$!%*#?&]', password)):
        return JsonResponse({
            'success': False,
            'message': 'Password validation failed.',
            'errors': {
                'password': ['Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character (@$!%*#?&).']
            }
        }, status=422)

    try:
        otp_record = EmployeeOTP.objects.filter(employee_id=employee_id).first()
        if not otp_record or otp_record.expires_at < timezone.now():
            return JsonResponse({
                'success': False,
                'message': 'Session expired or invalid OTP request. Please start again.'
            }, status=400)

        if str(otp_record.otp).strip() != str(otp).strip():
            return JsonResponse({
                'success': False,
                'message': 'Invalid OTP provided.'
            }, status=400)

        employee = Employee.objects.filter(id=employee_id).first()
        if not employee:
            return JsonResponse({
                'success': False,
                'message': 'Employee record not found or password was not modified.'
            }, status=404)

        employee.app_password = make_password(password)
        employee.save(update_fields=['app_password', 'updated_at'])

        EmployeeOTP.objects.filter(employee_id=employee_id).delete()

        return JsonResponse({
            'success': True,
            'message': 'Password has been reset successfully.'
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while resetting the password.',
            'error': str(e)
        }, status=500)


# -------------------------------------------------------------
# 3. Punch In & Punch Out APIs (Geofenced 500m)
# -------------------------------------------------------------
@csrf_exempt
def punch_in(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    employee_id = data.get('employee_id')
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if not employee_id or latitude is None or longitude is None:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed.',
            'errors': {'fields': ['employee_id, latitude, and longitude are required.']}
        }, status=422)

    try:
        employee = Employee.objects.filter(id=employee_id).first()
        if not employee:
            return JsonResponse({'success': False, 'message': 'Employee not found.'}, status=404)

        active_attendance = EmployeeAttendance.objects.filter(
            employee_id=employee_id,
            punch_out__isnull=True
        ).first()

        if active_attendance:
            return JsonResponse({
                'success': False,
                'message': 'You are already punched in. Please punch out first before punching in again.'
            }, status=400)

        locations = list(AttendanceMaster.objects.all())
        sites = list(SiteMaster.objects.all())
        all_coords = []
        for loc in locations:
            if loc.latitude and loc.longitude:
                all_coords.append((float(loc.latitude), float(loc.longitude)))
        for site in sites:
            if site.latitude and site.longitude:
                all_coords.append((float(site.latitude), float(site.longitude)))

        allowed_radius = 500.00
        is_within_location = False

        if all_coords:
            for clat, clon in all_coords:
                dist = calculate_distance_in_meters(clat, clon, latitude, longitude)
                if dist <= allowed_radius:
                    is_within_location = True
                    break

            if not is_within_location:
                return JsonResponse({
                    'success': False,
                    'message': 'You are outside the allowed office location radius.'
                }, status=403)

        now_ist = timezone.now()
        attendance = EmployeeAttendance.objects.create(
            employee_id=employee.id,
            punch_in=now_ist,
            punch_out=None,
            latitude=latitude,
            longitude=longitude
        )

        return JsonResponse({
            'success': True,
            'message': 'Punched in successfully.',
            'data': {
                'attendance_id': attendance.id,
                'employee_id': employee.id,
                'employee_name': employee.name,
                'type': 'in',
                'date': now_ist.strftime('%Y-%m-%d'),
                'time': now_ist.strftime('%H:%M:%S'),
                'latitude': float(latitude),
                'longitude': float(longitude),
            }
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred during punch in.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def punch_out(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    employee_id = data.get('employee_id')
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if not employee_id or latitude is None or longitude is None:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed.',
            'errors': {'fields': ['employee_id, latitude, and longitude are required.']}
        }, status=422)

    try:
        employee = Employee.objects.filter(id=employee_id).first()
        if not employee:
            return JsonResponse({'success': False, 'message': 'Employee not found.'}, status=404)

        attendance = EmployeeAttendance.objects.filter(
            employee_id=employee_id,
            punch_out__isnull=True
        ).order_by('-punch_in').first()

        if not attendance:
            return JsonResponse({
                'success': False,
                'message': 'No active punch-in found for this employee.'
            }, status=404)

        locations = list(AttendanceMaster.objects.all())
        sites = list(SiteMaster.objects.all())
        all_coords = []
        matched_location = None
        allowed_radius = 500.00
        is_within_location = False

        for loc in locations:
            if loc.latitude and loc.longitude:
                dist = calculate_distance_in_meters(loc.latitude, loc.longitude, latitude, longitude)
                if dist <= allowed_radius:
                    is_within_location = True
                    matched_location = loc
                    break
                all_coords.append((float(loc.latitude), float(loc.longitude)))

        if not is_within_location:
            for site in sites:
                if site.latitude and site.longitude:
                    dist = calculate_distance_in_meters(site.latitude, site.longitude, latitude, longitude)
                    if dist <= allowed_radius:
                        is_within_location = True
                        break
                    all_coords.append((float(site.latitude), float(site.longitude)))

        if (locations or sites) and all_coords and not is_within_location:
            return JsonResponse({
                'success': False,
                'message': 'You are outside the allowed office location radius.'
            }, status=403)

        now_ist = timezone.now()
        punch_in_time = attendance.punch_in or now_ist
        total_seconds = (now_ist - punch_in_time).total_seconds()
        total_minutes = int(total_seconds // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        actual_worked_str = f"{hours} hours and {minutes} minutes"

        working_hours_comparison = None
        if matched_location and matched_location.working_hours:
            match = re.search(r'\d+', str(matched_location.working_hours))
            if match:
                req_hours = float(match.group(0))
                req_mins = req_hours * 60
                working_hours_comparison = {
                    'required_working_hours': matched_location.working_hours,
                    'actual_worked_hours': actual_worked_str,
                    'is_completed': total_minutes >= req_mins
                }

        attendance.punch_out = now_ist
        attendance.latitude = latitude
        attendance.longitude = longitude
        attendance.actual_worked = actual_worked_str
        attendance.save(update_fields=['punch_out', 'latitude', 'longitude', 'actual_worked', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'Punched out successfully.',
            'data': {
                'attendance_id': attendance.id,
                'employee_id': employee_id,
                'type': 'out',
                'date': now_ist.strftime('%Y-%m-%d'),
                'time': now_ist.strftime('%H:%M:%S'),
                'actual_worked': actual_worked_str,
                'working_hours_comparison': working_hours_comparison,
                'latitude': float(latitude),
                'longitude': float(longitude),
            }
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred during punch out.',
            'error': str(e)
        }, status=500)


# -------------------------------------------------------------
# 4. Projects by Employee ID API
# -------------------------------------------------------------
@csrf_exempt
def get_projects_by_employee_id(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    employee_id = data.get('employee_id')

    if not employee_id:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed. Employee ID is required.',
            'errors': {'employee_id': ['Employee ID is required.']}
        }, status=422)

    try:
        employee_id = int(employee_id)
        if not Employee.objects.filter(id=employee_id).exists():
            return JsonResponse({'success': False, 'message': 'Employee not registered.'}, status=404)

        all_projects = Project.objects.all()
        matched = []
        doc_types = {d.id: d.type_name for d in DocumentTypeMaster.objects.all()}

        for p in all_projects:
            is_sm = (p.site_manager == employee_id)
            staff_list = p.field_staff if isinstance(p.field_staff, list) else []
            is_staff = (employee_id in staff_list or str(employee_id) in [str(x) for x in staff_list])

            if is_sm or is_staff:
                docs = ProjectDocument.objects.filter(project_id=p.id)
                formatted_docs = []
                for doc in docs:
                    formatted_docs.append({
                        'project_document_id': doc.id,
                        'document_path': doc.file,
                        'document_type_id': doc.document_type_id,
                        'document_name': doc_types.get(doc.document_type_id, doc.name or 'Document'),
                        'name': doc.name or doc.file,
                    })

                matched.append({
                    'id': p.id,
                    'company_id': p.company_id,
                    'client_name': p.client_name,
                    'site_id': p.site_id,
                    'site_manager': p.site_manager,
                    'field_staff': staff_list,
                    'status': p.status,
                    'start_date': str(p.start_date) if p.start_date else None,
                    'end_date': str(p.end_date) if p.end_date else None,
                    'reporting_frequency': p.reporting_frequency,
                    'notes': p.notes,
                    'documents': formatted_docs
                })

        if not matched:
            return JsonResponse({'success': False, 'message': 'No project assigned.'}, status=404)

        return JsonResponse({
            'success': True,
            'message': 'Projects retrieved successfully.',
            'data': matched
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while retrieving projects.',
            'error': str(e)
        }, status=500)


# -------------------------------------------------------------
# 5. Employee Profile: Get & Update APIs
# -------------------------------------------------------------
@csrf_exempt
def get_employee_profile(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    employee_id = data.get('employee_id')

    if not employee_id:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed. Employee ID is required.',
            'errors': {'employee_id': ['Employee ID is required.']}
        }, status=422)

    try:
        emp = Employee.objects.filter(id=employee_id).first()
        if not emp:
            return JsonResponse({'success': False, 'message': 'Employee not registered.'}, status=404)

        docs = emp.documents if isinstance(emp.documents, list) else []

        emp_data = {
            'id': emp.id,
            'company_id': emp.company_id,
            'name': emp.name,
            'role': emp.role,
            'app_username': emp.app_username,
            'email': emp.email,
            'phone': emp.phone,
            'gender': emp.gender,
            'dob': str(emp.dob) if emp.dob else None,
            'address': emp.address,
            'city': emp.city,
            'state': emp.state,
            'pincode': emp.pincode,
            'joining_date': str(emp.joining_date) if emp.joining_date else None,
            'relieving_date': str(emp.relieving_date) if emp.relieving_date else None,
            'status': emp.status,
            'documents': docs,
            'fcm_token': emp.fcm_token,
            'created_at': emp.created_at.isoformat() if emp.created_at else None,
            'updated_at': emp.updated_at.isoformat() if emp.updated_at else None,
        }

        return JsonResponse({
            'success': True,
            'message': 'Employee profile retrieved successfully.',
            'data': emp_data
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while retrieving employee profile.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def update_employee_profile(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    emp_id = data.get('id')

    if not emp_id:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed.',
            'errors': {'id': ['The id field is required.']}
        }, status=422)

    try:
        emp = Employee.objects.filter(id=emp_id).first()
        if not emp:
            return JsonResponse({'success': False, 'message': 'Employee not registered.'}, status=404)

        updatable_fields = [
            'company_id', 'name', 'role', 'app_username', 'joining_date',
            'relieving_date', 'status', 'dob', 'gender', 'phone', 'email',
            'address', 'city', 'pincode', 'state'
        ]

        updated = False
        for f in updatable_fields:
            if f in data:
                val = data.get(f)
                if f in ['joining_date', 'relieving_date', 'dob'] and not val:
                    val = None
                setattr(emp, f, val)
                updated = True

        if 'app_password' in data and data['app_password']:
            emp.app_password = make_password(data['app_password'])
            updated = True

        if 'documents' in data:
            doc_val = data['documents']
            if isinstance(doc_val, str):
                try:
                    doc_val = json.loads(doc_val)
                except Exception:
                    pass
            emp.documents = doc_val
            updated = True

        if not updated:
            return JsonResponse({
                'success': False,
                'message': 'No updatable fields provided.'
            }, status=400)

        emp.save()

        return JsonResponse({
            'success': True,
            'message': 'Updated successfully.',
            'data': {
                'id': emp.id,
                'name': emp.name,
                'email': emp.email,
                'phone': emp.phone,
                'app_username': emp.app_username,
                'status': emp.status
            }
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while updating the profile.',
            'error': str(e)
        }, status=500)


# -------------------------------------------------------------
# 6. Expenses APIs
# -------------------------------------------------------------
@csrf_exempt
def add_expense(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    emp_id = data.get('emp_id')
    exp_cat_id = data.get('exp_cat_id')
    amount = data.get('amount')
    date_val = data.get('date')
    emp_comment = data.get('emp_comment', '')
    project_id = data.get('project_id')

    if not emp_id or not exp_cat_id or not amount or not date_val:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed.',
            'errors': {
                'emp_id': ['Employee ID is required.'] if not emp_id else [],
                'exp_cat_id': ['Expense category is required.'] if not exp_cat_id else [],
                'amount': ['Amount is required.'] if not amount else [],
                'date': ['Date is required.'] if not date_val else [],
            }
        }, status=422)

    try:
        employee = Employee.objects.filter(id=emp_id).first()
        if not employee:
            return JsonResponse({'success': False, 'message': 'Employee not found.'}, status=404)

        if not project_id:
            last_att = EmployeeAttendance.objects.filter(
                employee_id=emp_id,
                punch_out__isnull=True
            ).order_by('-punch_in').first()
            if last_att and hasattr(last_att, 'project_id'):
                project_id = last_att.project_id

        image_path = None
        if 'image' in request.FILES:
            file_obj = request.FILES['image']
            save_name = f"expenses/{timezone.now().strftime('%Y%m%d%H%M%S')}_{file_obj.name}"
            saved_path = default_storage.save(save_name, file_obj)
            image_path = saved_path

        expense = Expense.objects.create(
            company_id=employee.company_id,
            category_id=exp_cat_id,
            employee_id=emp_id,
            project_id=project_id,
            amount=amount,
            date=date_val,
            emp_comment=emp_comment,
            image=image_path,
            status='pending'
        )

        try:
            admin_email = 'shimpikumudini2@gmail.com'
            smtp = SMTPConfiguration.objects.filter(id=6).first() or SMTPConfiguration.objects.first()
            from_name = smtp.from_name if smtp else 'SolarPro'
            email_body = (
                f"Hello Admin,\n\n"
                f"A new expense has been submitted by {employee.name}.\n\n"
                f"Amount: {amount}\nDate: {date_val}\nComment: {emp_comment}\n\n"
                f"Please review it in the admin portal."
            )
            send_dynamic_smtp_email(admin_email, f"New Expense Submitted - {from_name}", email_body)
        except Exception:
            pass

        return JsonResponse({
            'success': True,
            'message': 'Expense added successfully.',
            'expense_id': expense.id
        }, status=201)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while adding the expense.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def get_expense_categories(request):
    try:
        data = get_request_data(request)
        company_id = data.get('company_id') or request.GET.get('company_id')
        query = ExpenseCategory.objects.all()
        if company_id:
            query = query.filter(company_id=company_id)

        categories = [
            {'id': c.id, 'company_id': c.company_id, 'category_name': c.category_name}
            for c in query
        ]

        return JsonResponse({
            'success': True,
            'message': 'Expense categories fetched successfully.',
            'data': categories
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error fetching expense categories.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def get_employee_expenses(request):
    data = get_request_data(request)
    emp_id = data.get('emp_id') or request.GET.get('emp_id')

    if not emp_id:
        return JsonResponse({
            'success': False,
            'message': 'Please provide an emp_id.'
        }, status=400)

    try:
        employee = Employee.objects.filter(id=emp_id).first()
        if not employee:
            return JsonResponse({'success': False, 'message': 'Employee not found.'}, status=404)

        cat_map = {c.id: c.category_name for c in ExpenseCategory.objects.all()}
        expenses = Expense.objects.filter(employee_id=emp_id).order_by('-date')

        res = []
        for exp in expenses:
            res.append({
                'expense_id': exp.id,
                'amount': str(exp.amount),
                'status': exp.status,
                'date': str(exp.date),
                'emp_comment': exp.emp_comment,
                'rejection_reason': exp.rejection_reason,
                'category_name': cat_map.get(exp.category_id, 'General'),
                'employee_name': employee.name
            })

        return JsonResponse({
            'success': True,
            'message': 'Expenses retrieved successfully.',
            'data': res
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while retrieving expenses.',
            'error': str(e)
        }, status=500)


# -------------------------------------------------------------
# 7. Stock by Project ID API
# -------------------------------------------------------------
@csrf_exempt
def get_stock_by_project_id(request):
    data = get_request_data(request)
    project_id = data.get('project_id') or request.GET.get('project_id')

    if not project_id:
        return JsonResponse({
            'success': False,
            'message': 'Please provide a project_id.'
        }, status=400)

    try:
        assigned_stocks = AssignedStock.objects.filter(project_id=project_id)
        item_ids = [s.item_id for s in assigned_stocks]
        items = {it.id: it for it in OpeningStock.objects.filter(id__in=item_ids)}
        categories = {c.id: c.category_name for c in StockCategory.objects.all()}

        res = []
        for s in assigned_stocks:
            item = items.get(s.item_id)
            cat_name = categories.get(item.category if item else None, 'General')
            res.append({
                'id': s.id,
                'item_name': item.item_name if item else 'Unknown Item',
                'item_id': s.item_id,
                'category_id': item.category if item else None,
                'category_name': cat_name,
                'unit': item.unit if item else 'pcs',
                'available_quantity': float(item.quantity) if item else 0.0,
                'assigned_quantity': float(s.qty),
            })

        return JsonResponse({
            'success': True,
            'message': 'Stock retrieved successfully.',
            'data': res
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while fetching stock details.',
            'error': str(e)
        }, status=500)


# -------------------------------------------------------------
# 8. Dynamic Forms APIs: Get Forms, Submit, Get Submissions
# -------------------------------------------------------------
@csrf_exempt
def get_dynamic_forms(request):
    try:
        data = get_request_data(request)
        emp_id = data.get('emp_id') or request.GET.get('emp_id')
        project_id = data.get('project_id') or request.GET.get('project_id')
        company_id = data.get('company_id') or request.GET.get('company_id')

        if emp_id and project_id:
            try:
                emp_id_int = int(emp_id)
                proj = Project.objects.filter(id=project_id).first()
                if proj:
                    staff_list = proj.field_staff if isinstance(proj.field_staff, list) else []
                    is_assigned = (proj.site_manager == emp_id_int or emp_id_int in staff_list or str(emp_id) in [str(x) for x in staff_list])
                    if not is_assigned:
                        return JsonResponse({
                            'success': False,
                            'message': 'This project is not assigned to the specified employee.',
                            'data': []
                        }, status=403)
            except Exception:
                pass

        forms_query = DynamicForm.objects.filter(is_active=1)
        if company_id:
            forms_query = forms_query.filter(company_id=company_id)

        all_forms = forms_query.order_by('-created_at')
        filtered = []

        for f in all_forms:
            pids = f.project_ids if isinstance(f.project_ids, list) else []
            if project_id:
                if (int(project_id) not in pids and str(project_id) not in [str(x) for x in pids]):
                    continue

            schema = f.form_schema
            if isinstance(schema, str):
                try:
                    schema = json.loads(schema)
                except Exception:
                    pass

            filtered.append({
                'id': f.id,
                'company_id': f.company_id,
                'form_name': f.form_name,
                'description': f.description,
                'project_ids': pids,
                'form_schema': schema,
                'is_active': f.is_active,
                'created_at': f.created_at.isoformat() if f.created_at else None,
                'updated_at': f.updated_at.isoformat() if f.updated_at else None,
            })

        return JsonResponse({
            'success': True,
            'message': 'Dynamic forms retrieved successfully.',
            'data': filtered
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while retrieving dynamic forms.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def submit_form(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    emp_id = data.get('emp_id')
    form_id = data.get('form_id')
    project_id = data.get('project_id')
    submission_data = data.get('submission_data')

    if not emp_id or not form_id or submission_data is None:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed.',
            'errors': {
                'emp_id': ['Employee ID is required.'] if not emp_id else [],
                'form_id': ['Form ID is required.'] if not form_id else [],
                'submission_data': ['Submission data is required.'] if submission_data is None else []
            }
        }, status=422)

    try:
        from apps.masters.form_builder_service import ActivityFormService

        employee = Employee.objects.filter(id=emp_id).first()
        if not employee:
            return JsonResponse({'success': False, 'message': 'Employee not found.'}, status=404)

        form = DynamicForm.objects.filter(id=form_id).first()
        if not form:
            return JsonResponse({'success': False, 'message': 'Form template not found.'}, status=404)

        if not project_id:
            last_att = EmployeeAttendance.objects.filter(
                employee_id=emp_id,
                punch_out__isnull=True
            ).order_by('-punch_in').first()
            if last_att and hasattr(last_att, 'project_id'):
                project_id = last_att.project_id

        # Normalize submission_data into dictionary
        if isinstance(submission_data, str):
            try:
                sub_dict = json.loads(submission_data)
            except Exception:
                sub_dict = {'raw_data': submission_data}
        elif isinstance(submission_data, dict):
            sub_dict = submission_data
        else:
            sub_dict = {}

        # 1. Process and save any uploaded files from request.FILES and base64 payloads
        before_photos = []
        after_photos = []
        field_photos = {}

        # Check existing photos in sub_dict
        existing_ev = sub_dict.get('photo_evidence', {})
        if isinstance(existing_ev, dict):
            for p in existing_ev.get('before_photos', []):
                saved = ActivityFormService.save_photo_file(p, subfolder='before_photos')
                if saved:
                    before_photos.append(saved)
            for p in existing_ev.get('after_photos', []):
                saved = ActivityFormService.save_photo_file(p, subfolder='after_photos')
                if saved:
                    after_photos.append(saved)

        # Check request.FILES
        if 'before_photos' in request.FILES:
            for f in request.FILES.getlist('before_photos'):
                saved = ActivityFormService.save_photo_file(f, subfolder='before_photos')
                if saved:
                    before_photos.append(saved)
        if 'after_photos' in request.FILES:
            for f in request.FILES.getlist('after_photos'):
                saved = ActivityFormService.save_photo_file(f, subfolder='after_photos')
                if saved:
                    after_photos.append(saved)

        for key in request.FILES:
            if key.startswith('field_photo_') or key.startswith('field_'):
                f_id = key.split('_')[-1]
                for f in request.FILES.getlist(key):
                    saved = ActivityFormService.save_photo_file(f, subfolder='field_photos')
                    if saved:
                        field_photos.setdefault(f_id, []).append(saved)

        # 2. Check Photo Evidence Requirements from Form Schema or ActivityFormPhotoSetting
        form_schema = form.form_schema if isinstance(form.form_schema, dict) else json.loads(form.form_schema or '{}')
        photo_cfg = form_schema.get('photo_settings', {})

        if photo_cfg.get('enable_photo_capture'):
            if photo_cfg.get('before_photo_required') and not before_photos:
                return JsonResponse({
                    'success': False,
                    'message': 'Before Maintenance photo is required. Please capture or upload evidence before maintenance.',
                    'errors': {'before_photos': ['Before Maintenance photo is mandatory.']}
                }, status=422)

            if photo_cfg.get('after_photo_required') and not after_photos:
                return JsonResponse({
                    'success': False,
                    'message': 'After Maintenance photo is required. Please capture or upload evidence after maintenance.',
                    'errors': {'after_photos': ['After Maintenance photo is mandatory.']}
                }, status=422)

        # Update sub_dict with saved photos
        if before_photos or after_photos or photo_cfg.get('enable_photo_capture'):
            sub_dict['photo_evidence'] = {
                'before_photos': before_photos,
                'after_photos': after_photos,
                'before_count': len(before_photos),
                'after_count': len(after_photos)
            }
        if field_photos:
            sub_dict['field_photos'] = field_photos

        # Ensure GPS and Timestamps if submitted
        if 'latitude' in data and 'longitude' in data and 'gps_coordinates' not in sub_dict:
            sub_dict['gps_coordinates'] = {
                'latitude': data.get('latitude'),
                'longitude': data.get('longitude'),
                'accuracy': data.get('accuracy')
            }
        if 'timestamps' not in sub_dict:
            sub_dict['timestamps'] = {
                'submission_time': timezone.now().strftime('%d %b %Y, %I:%M %p'),
                'iso_timestamp': timezone.now().isoformat()
            }

        is_flg, flg_dets = evaluate_form_submission(form.form_schema, sub_dict)

        submission = FormSubmission.objects.create(
            company_id=employee.company_id,
            form_id=form_id,
            project_id=project_id,
            emp_id=emp_id,
            submission_data=sub_dict,
            is_flagged=is_flg,
            flagged_details=flg_dets
        )

        return JsonResponse({
            'success': True,
            'message': 'Form submitted successfully.',
            'submission_id': submission.id,
            'before_photos': before_photos,
            'after_photos': after_photos
        }, status=201)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while submitting the form.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def get_employee_submissions(request, emp_id):
    try:
        if not Employee.objects.filter(id=emp_id).exists():
            return JsonResponse({'success': False, 'message': 'Employee not found.'}, status=404)

        forms = {f.id: f.form_name for f in DynamicForm.objects.all()}
        submissions = FormSubmission.objects.filter(emp_id=emp_id).order_by('-created_at')

        res = []
        for s in submissions:
            data = s.submission_data
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    pass

            res.append({
                'submission_id': s.id,
                'form_id': s.form_id,
                'form_name': forms.get(s.form_id, 'Form'),
                'submission_data': data,
                'submitted_at': s.created_at.isoformat() if s.created_at else None
            })

        return JsonResponse({
            'success': True,
            'message': 'Form submissions retrieved successfully.',
            'data': res
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while retrieving submissions.',
            'error': str(e)
        }, status=500)


# -------------------------------------------------------------
# 9. Firebase Push Notifications APIs
# -------------------------------------------------------------
def get_firebase_app():
    """
    Initializes and returns firebase_admin app singleton.
    """
    import firebase_admin
    from firebase_admin import credentials

    cred_paths = [
        settings.FIREBASE_CREDENTIALS_PATH,
        settings.BASE_DIR / 'firebase_credentials.json',
        settings.BASE_DIR.parent / 'storage' / 'app' / 'firebase_credentials.json'
    ]

    found_path = None
    for p in cred_paths:
        if Path(p).exists():
            found_path = p
            break

    if not found_path:
        raise FileNotFoundError(f"Firebase credentials not found at any configured location.")

    if not firebase_admin._apps:
        cred = credentials.Certificate(str(found_path))
        return firebase_admin.initialize_app(cred)
    return firebase_admin.get_app()


@csrf_exempt
def test_firebase_connection(request):
    try:
        app = get_firebase_app()
        from firebase_admin import auth
        auth.list_users(max_results=1, app=app)
        return JsonResponse({
            'success': True,
            'message': 'FIREBASE IS CONNECTED! 🎉',
            'details': 'Your Django portal successfully authenticated with Google servers using the JSON credentials.'
        }, status=200)
    except FileNotFoundError as fnf:
        return JsonResponse({'success': False, 'message': str(fnf)}, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Firebase connection failed. ❌',
            'error': str(e)
        }, status=500)


@csrf_exempt
def test_topic_notification(request):
    try:
        app = get_firebase_app()
        from firebase_admin import messaging

        message = messaging.Message(
            notification=messaging.Notification(
                title='Topic Test 🎉',
                body='This is a test notification for all subscribers of solar_notifications!'
            ),
            topic='solar_notifications'
        )
        messaging.send(message, app=app)

        return JsonResponse({
            'success': True,
            'message': 'Topic notification broadcasted successfully to solar_notifications!'
        }, status=200)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Failed to send topic notification.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def test_token_notification(request):
    try:
        app = get_firebase_app()
        from firebase_admin import messaging

        token = "eIvQBFe2Slmc6ozK_y7Xkk:APA91bGXltSFfPpUxx0k7JVyfiK4ry7-UI4ayAK2mcv_0tS1ajoaFcVqbhIsSEHyGDN1KHwVysvDH3NI_5evedts3pp8_Hr8xwtZjGo8GIfdeCHrgp-h7Q0"

        message = messaging.Message(
            notification=messaging.Notification(
                title='Direct Token Test 🚀',
                body='This is a direct test notification for your specific device!'
            ),
            token=token
        )
        messaging.send(message, app=app)

        return JsonResponse({
            'success': True,
            'message': 'Direct token notification sent successfully!'
        }, status=200)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Failed to send token notification.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def send_employee_notification(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    employee_id = data.get('employee_id')
    title = data.get('title')
    body = data.get('body')

    if not employee_id or not title or not body:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed.',
            'errors': {
                'employee_id': ['Employee ID is required.'] if not employee_id else [],
                'title': ['Title is required.'] if not title else [],
                'body': ['Body is required.'] if not body else [],
            }
        }, status=422)

    try:
        employee = Employee.objects.filter(id=employee_id).first()
        if not employee:
            return JsonResponse({'success': False, 'message': 'Employee not found.'}, status=404)

        if not employee.fcm_token:
            return JsonResponse({
                'success': False,
                'message': 'Employee does not have an active FCM token registered (User has not logged into the mobile app with FCM enabled).'
            }, status=400)

        app = get_firebase_app()
        from firebase_admin import messaging

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=employee.fcm_token
        )
        messaging.send(message, app=app)

        return JsonResponse({
            'success': True,
            'message': f"Notification sent successfully to {employee.name}!",
            'data': {
                'employee_id': employee.id,
                'fcm_token': employee.fcm_token
            }
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Failed to send notification.',
            'error': str(e)
        }, status=500)


# -------------------------------------------------------------
# 10. Employee Graph & Analytics API
# -------------------------------------------------------------
@csrf_exempt
def employee_graph_analytics(request):
    data = get_request_data(request)
    emp_id = data.get('employee_id') or data.get('emp_id') or request.GET.get('employee_id')

    if not emp_id:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed. Employee ID is required.'
        }, status=422)

    try:
        emp_id = int(emp_id)
        employee = Employee.objects.filter(id=emp_id).first()
        if not employee:
            return JsonResponse({'success': False, 'message': 'Employee not found.'}, status=404)

        total_attendances = EmployeeAttendance.objects.filter(employee_id=emp_id).count()
        now = timezone.now()
        this_month_attendances = EmployeeAttendance.objects.filter(
            employee_id=emp_id,
            punch_in__year=now.year,
            punch_in__month=now.month
        ).count()

        emp_expenses = Expense.objects.filter(employee_id=emp_id)
        total_expenses = emp_expenses.count()
        approved_expenses = emp_expenses.filter(status='approved').count()
        pending_expenses = emp_expenses.filter(status='pending').count()
        rejected_expenses = emp_expenses.filter(status='rejected').count()
        total_approved_amount = sum(float(e.amount) for e in emp_expenses.filter(status='approved'))

        total_submissions = FormSubmission.objects.filter(emp_id=emp_id).count()

        all_projects = Project.objects.all()
        assigned_proj_count = 0
        for p in all_projects:
            staff_list = p.field_staff if isinstance(p.field_staff, list) else []
            if p.site_manager == emp_id or emp_id in staff_list or str(emp_id) in [str(x) for x in staff_list]:
                assigned_proj_count += 1

        analytics_data = {
            'employee': {
                'id': employee.id,
                'name': employee.name,
                'username': employee.app_username,
                'status': employee.status
            },
            'attendance': {
                'total_punch_ins': total_attendances,
                'this_month_punch_ins': this_month_attendances,
            },
            'expenses': {
                'total_count': total_expenses,
                'approved_count': approved_expenses,
                'pending_count': pending_expenses,
                'rejected_count': rejected_expenses,
                'total_approved_amount': total_approved_amount
            },
            'submissions': {
                'total_forms_submitted': total_submissions,
            },
            'projects': {
                'assigned_projects_count': assigned_proj_count,
            }
        }

        return JsonResponse({
            'success': True,
            'message': 'Employee graph analytics retrieved successfully.',
            'data': analytics_data
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while fetching graph analytics.',
            'error': str(e)
        }, status=500)


# -------------------------------------------------------------
# 11. Leave Management Mobile APIs
# -------------------------------------------------------------
@csrf_exempt
def apply_leave(request):
    """
    POST /api/apply-leave
    Allows employees to submit leave requests from the mobile application.
    Extracts employee identity from session or authenticated payload (emp_id).
    Validates date ranges, calculates days count, checks for overlapping leaves,
    and supports optional file attachments.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    data = get_request_data(request)
    emp_id = data.get('emp_id') or request.POST.get('emp_id') or request.session.get('user_id')

    if not emp_id:
        return JsonResponse({
            'success': False,
            'message': 'Employee authentication required. Please provide a valid emp_id or log in.'
        }, status=401)

    employee = Employee.objects.filter(id=emp_id, status='active').first()
    if not employee:
        return JsonResponse({'success': False, 'message': 'Active employee record not found.'}, status=404)

    leave_type = data.get('leave_type') or request.POST.get('leave_type')
    start_date_str = data.get('start_date') or request.POST.get('start_date')
    end_date_str = data.get('end_date') or request.POST.get('end_date')
    reason = data.get('reason') or request.POST.get('reason')

    errors = {}
    if not leave_type:
        errors['leave_type'] = ['Leave type is required.']
    if not start_date_str:
        errors['start_date'] = ['Start date is required.']
    if not end_date_str:
        errors['end_date'] = ['End date is required.']
    if not reason:
        errors['reason'] = ['Reason for leave is required.']

    if errors:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed.',
            'errors': errors
        }, status=422)

    try:
        start_date = datetime.strptime(str(start_date_str).strip(), '%Y-%m-%d').date()
        end_date = datetime.strptime(str(end_date_str).strip(), '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid date format. Expected YYYY-MM-DD.'
        }, status=422)

    if end_date < start_date:
        return JsonResponse({
            'success': False,
            'message': 'End date cannot be earlier than start date.'
        }, status=422)

    # Calculate days count (inclusive)
    days_count = (end_date - start_date).days + 1
    custom_days = data.get('days_count') or request.POST.get('days_count')
    if custom_days:
        try:
            days_count = float(custom_days)
        except (ValueError, TypeError):
            pass

    # Prevent duplicate or overlapping pending/approved leave requests
    overlapping = LeaveRequest.objects.filter(
        employee=employee,
        status__in=['pending', 'approved'],
        start_date__lte=end_date,
        end_date__gte=start_date
    ).first()

    if overlapping:
        return JsonResponse({
            'success': False,
            'message': f'You already have a {overlapping.status} leave request overlapping with this period ({overlapping.start_date} to {overlapping.end_date}).'
        }, status=409)

    attachment_path = None
    if 'attachment' in request.FILES:
        file_obj = request.FILES['attachment']
        save_name = f"leaves/{timezone.now().strftime('%Y%m%d%H%M%S')}_{file_obj.name}"
        saved_path = default_storage.save(save_name, file_obj)
        attachment_path = saved_path

    try:
        leave_request = LeaveRequest.objects.create(
            company_id=employee.company_id,
            employee=employee,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            days_count=days_count,
            reason=reason,
            attachment=attachment_path,
            status='pending'
        )

        # Notify Admin via dynamic SMTP if configured
        try:
            smtp = SMTPConfiguration.objects.first()
            admin_email = smtp.from_email if smtp and smtp.from_email else 'admin@solarpro.local'
            from_name = smtp.from_name if smtp else 'SolarPro'
            email_body = (
                f"Hello Admin,\n\n"
                f"A new leave request has been submitted by {employee.name} (EMP-{employee.id:04d}).\n\n"
                f"Leave Type: {leave_type}\n"
                f"Dates: {start_date} to {end_date} ({days_count} days)\n"
                f"Reason: {reason}\n\n"
                f"Please review and take action in the Leave Management module."
            )
            send_dynamic_smtp_email(admin_email, f"New Leave Request - {employee.name}", email_body)
        except Exception:
            pass

        return JsonResponse({
            'success': True,
            'message': 'Leave request submitted successfully.',
            'data': {
                'leave_id': leave_request.id,
                'employee_id': employee.id,
                'employee_name': employee.name,
                'leave_type': leave_request.leave_type,
                'start_date': str(leave_request.start_date),
                'end_date': str(leave_request.end_date),
                'days_count': str(leave_request.days_count),
                'reason': leave_request.reason,
                'status': leave_request.status,
                'attachment': leave_request.attachment,
                'created_at': leave_request.created_at.strftime('%Y-%m-%d %H:%M:%S') if leave_request.created_at else ''
            }
        }, status=201)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while submitting the leave request.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def get_employee_leaves(request):
    """
    GET or POST /api/get-employee-leaves
    Retrieves leave history and current status for an employee.
    Extracts employee identity from payload, GET query param, or session.
    Returns details including leave type, dates, days, reason, current status,
    admin remarks, and rejection reason.
    """
    data = get_request_data(request)
    emp_id = data.get('emp_id') or request.GET.get('emp_id') or request.POST.get('emp_id') or request.session.get('user_id')

    if not emp_id:
        return JsonResponse({
            'success': False,
            'message': 'Please provide an emp_id or authenticate.'
        }, status=400)

    try:
        employee = Employee.objects.filter(id=emp_id).first()
        if not employee:
            return JsonResponse({'success': False, 'message': 'Employee not found.'}, status=404)

        status_filter = data.get('status') or request.GET.get('status') or request.POST.get('status')

        leaves_qs = LeaveRequest.objects.filter(employee=employee)
        if status_filter in ['pending', 'approved', 'rejected']:
            leaves_qs = leaves_qs.filter(status=status_filter)

        leaves_qs = leaves_qs.order_by('-created_at', '-id')

        # Compute summary stats
        all_leaves = LeaveRequest.objects.filter(employee=employee)
        stats = {
            'total_requests': all_leaves.count(),
            'pending': all_leaves.filter(status='pending').count(),
            'approved': all_leaves.filter(status='approved').count(),
            'rejected': all_leaves.filter(status='rejected').count(),
        }

        desig = DesignationMaster.objects.filter(id=employee.role).first() if employee.role else None
        dept = DepartmentMaster.objects.filter(id=desig.department_id).first() if desig and desig.department_id else None

        records = []
        for l in leaves_qs:
            records.append({
                'id': l.id,
                'leave_type': l.leave_type,
                'start_date': str(l.start_date),
                'end_date': str(l.end_date),
                'days_count': str(l.days_count),
                'reason': l.reason,
                'status': l.status,
                'rejection_reason': l.rejection_reason or '',
                'admin_remarks': l.admin_remarks or '',
                'action_by': l.action_by or '',
                'action_at': l.action_at.strftime('%Y-%m-%d %H:%M:%S') if l.action_at else '',
                'attachment': l.attachment or '',
                'created_at': l.created_at.strftime('%Y-%m-%d %H:%M:%S') if l.created_at else ''
            })

        return JsonResponse({
            'success': True,
            'message': 'Employee leaves retrieved successfully.',
            'employee': {
                'id': employee.id,
                'name': employee.name,
                'employee_code': f"EMP-{employee.id:04d}",
                'department': dept.department_name if dept else '—',
                'designation': desig.designation_name if desig else '—',
            },
            'summary': stats,
            'data': records
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while retrieving employee leaves.',
            'error': str(e)
        }, status=500)


# -------------------------------------------------------------
# 11. Project Activity Management (Mobile APIs)
# -------------------------------------------------------------

def authenticate_employee_request(request):
    """
    Helper to authenticate employee from session or request parameters (emp_id / employee_id).
    Ensures employee exists and is active.
    """
    data = get_request_data(request)
    emp_id = (
        request.session.get('user_id')
        or data.get('emp_id')
        or data.get('employee_id')
        or request.GET.get('emp_id')
        or request.GET.get('employee_id')
    )
    if not emp_id:
        return None, "Employee ID is required."
    try:
        emp = Employee.objects.filter(id=int(emp_id)).first()
        if not emp:
            return None, "Employee not registered."
        if emp.status != 'active':
            return None, "Employee account is inactive."
        return emp, None
    except Exception as e:
        return None, str(e)


@csrf_exempt
def get_employee_activities(request):
    """
    1. Fetch activities assigned to the authenticated employee.
    Filters instances where assigned_employee = employee, or employee is part of project field_staff.
    """
    employee, err = authenticate_employee_request(request)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=401 if 'inactive' in err else 400)

    try:
        data = get_request_data(request)
        project_id = data.get('project_id') or request.GET.get('project_id')
        status = data.get('status') or request.GET.get('status')
        date_str = data.get('date') or request.GET.get('date')

        # Permitted projects: employee is site_manager or in field_staff
        accessible_project_ids = []
        for p in Project.objects.all():
            staff = p.field_staff if isinstance(p.field_staff, list) else []
            if p.site_manager == employee.id or str(employee.id) in [str(x) for x in staff]:
                accessible_project_ids.append(p.id)

        qs = ProjectActivityInstance.objects.filter(
            Q(assigned_employee=employee) | Q(project_id__in=accessible_project_ids)
        ).select_related('project', 'activity', 'project_activity', 'project_activity__form')

        if project_id and str(project_id).isdigit():
            qs = qs.filter(project_id=int(project_id))
        if status:
            qs = qs.filter(status=status)
        if date_str:
            qs = qs.filter(scheduled_date=date_str)

        instances = qs.order_by('scheduled_date', 'id')

        result = []
        for inst in instances:
            form = inst.project_activity.form
            photo_count = inst.photos.count()
            has_issues = inst.issues.exists()

            result.append({
                'id': inst.id,
                'project_id': inst.project_id,
                'project_name': inst.project.project_name or inst.project.client_name,
                'client_name': inst.project.client_name,
                'activity_id': inst.activity_id,
                'activity_title': inst.activity.activity_title,
                'activity_category': inst.activity.activity_category,
                'scheduled_date': str(inst.scheduled_date),
                'due_date': str(inst.due_date) if inst.due_date else None,
                'frequency': inst.frequency,
                'status': inst.status,
                'estimated_duration': inst.project_activity.estimated_duration or inst.activity.estimated_duration or '',
                'photo_required': inst.activity.photo_required,
                'photos_uploaded': photo_count,
                'has_issues': has_issues,
                'form_id': form.id if form else None,
                'form_name': form.form_name if form else None,
                'actual_start_time': inst.actual_start_time.isoformat() if inst.actual_start_time else None,
                'actual_completion_time': inst.actual_completion_time.isoformat() if inst.actual_completion_time else None,
            })

        return JsonResponse({
            'success': True,
            'message': 'Assigned activities retrieved successfully.',
            'employee_id': employee.id,
            'count': len(result),
            'data': result
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error retrieving employee activities.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def get_activity_instance_detail(request):
    """
    2. Fetch detailed record for an individual activity instance.
    """
    employee, err = authenticate_employee_request(request)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=400)

    data = get_request_data(request)
    instance_id = data.get('instance_id') or request.GET.get('instance_id')
    if not instance_id:
        return JsonResponse({'success': False, 'message': 'instance_id is required.'}, status=422)

    try:
        inst = ProjectActivityInstance.objects.filter(id=int(instance_id)).select_related(
            'project', 'activity', 'project_activity', 'project_activity__form', 'assigned_employee', 'submitted_by'
        ).first()

        if not inst:
            return JsonResponse({'success': False, 'message': 'Activity instance not found.'}, status=404)

        # Check authorization: assigned employee or project staff
        p = inst.project
        staff = p.field_staff if isinstance(p.field_staff, list) else []
        if inst.assigned_employee_id != employee.id and p.site_manager != employee.id and str(employee.id) not in [str(x) for x in staff]:
            return JsonResponse({'success': False, 'message': 'You are not authorized to view this activity.'}, status=403)

        form = inst.project_activity.form
        photos = [
            {
                'id': ph.id,
                'stage': ph.photo_stage,
                'file_url': f"/media/{ph.photo_file}",
                'latitude': float(ph.latitude) if ph.latitude else None,
                'longitude': float(ph.longitude) if ph.longitude else None,
                'capture_timestamp': ph.capture_timestamp.isoformat() if ph.capture_timestamp else None,
                'created_at': ph.created_at.isoformat() if ph.created_at else None,
            }
            for ph in inst.photos.all()
        ]

        issues = [
            {
                'id': iss.id,
                'category': iss.issue_category,
                'short_description': iss.short_description,
                'detailed_explanation': iss.detailed_explanation,
                'supporting_photo': f"/media/{iss.supporting_photo}" if iss.supporting_photo else None,
                'status': iss.status,
                'reported_at': iss.created_at.isoformat() if iss.created_at else None,
            }
            for iss in inst.issues.all()
        ]

        # Activity Form Configuration & Photo Settings (if defined via Activity Form Builder)
        form_config = ActivityFormConfiguration.objects.filter(activity=inst.activity).first()
        photo_rules = {}
        if form_config and hasattr(form_config, 'photo_settings'):
            ps = form_config.photo_settings
            photo_rules = {
                'enable_photo_capture': ps.enable_photo_capture,
                'before_photo_required': ps.before_photo_required,
                'after_photo_required': ps.after_photo_required,
                'optional_photo': ps.optional_photo,
                'photo_instructions': ps.photo_instructions,
                'gps_required': ps.gps_coordinates_required,
            }

        return JsonResponse({
            'success': True,
            'message': 'Activity instance details retrieved successfully.',
            'data': {
                'id': inst.id,
                'project_id': inst.project_id,
                'project_name': inst.project.project_name or inst.project.client_name,
                'client_name': inst.project.client_name,
                'activity_id': inst.activity_id,
                'activity_title': inst.activity.activity_title,
                'activity_category': inst.activity.activity_category,
                'description': inst.activity.description,
                'scheduled_date': str(inst.scheduled_date),
                'due_date': str(inst.due_date) if inst.due_date else None,
                'frequency': inst.frequency,
                'status': inst.status,
                'assigned_employee_id': inst.assigned_employee_id,
                'assigned_employee_name': inst.assigned_employee.name if inst.assigned_employee else None,
                'form_id': form.id if form else None,
                'form_name': form.form_name if form else None,
                'photo_rules': photo_rules,
                'photos': photos,
                'issues': issues,
                'submission_data': inst.submission_data,
                'validation_result': inst.validation_result,
                'completion_remarks': inst.completion_remarks,
                'actual_start_time': inst.actual_start_time.isoformat() if inst.actual_start_time else None,
                'actual_completion_time': inst.actual_completion_time.isoformat() if inst.actual_completion_time else None,
            }
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error retrieving activity instance details.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def get_activity_form_schema(request):
    """
    3. Fetch attached form configuration schema for rendering dynamically on mobile.
    """
    employee, err = authenticate_employee_request(request)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=400)

    data = get_request_data(request)
    instance_id = data.get('instance_id') or request.GET.get('instance_id')
    form_id = data.get('form_id') or request.GET.get('form_id')

    try:
        form = None
        activity = None
        if instance_id and str(instance_id).isdigit():
            inst = ProjectActivityInstance.objects.filter(id=int(instance_id)).select_related('project_activity', 'activity').first()
            if inst:
                activity = inst.activity
                form = inst.project_activity.form

        if not form and form_id and str(form_id).isdigit():
            form = DynamicForm.objects.filter(id=int(form_id)).first()

        if not form:
            return JsonResponse({'success': False, 'message': 'No form attached or form not found.'}, status=404)

        # Retrieve rich field definitions if available from ActivityFormConfiguration
        builder_config = None
        if activity:
            builder_config = ActivityFormConfiguration.objects.filter(activity=activity).first()

        fields_data = []
        if builder_config:
            dict_rep = ActivityFormService.form_to_dict(builder_config)
            fields_data = dict_rep.get('fields', [])

        return JsonResponse({
            'success': True,
            'message': 'Form configuration schema retrieved.',
            'form': {
                'id': form.id,
                'form_name': form.form_name,
                'description': form.description,
                'form_schema': form.form_schema,
                'builder_fields': fields_data,
            }
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error fetching activity form schema.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def start_activity_instance(request):
    """
    4. Start activity execution: transitions status to 'In Progress' and logs start time.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    employee, err = authenticate_employee_request(request)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=400)

    data = get_request_data(request)
    instance_id = data.get('instance_id')
    if not instance_id:
        return JsonResponse({'success': False, 'message': 'instance_id is required.'}, status=422)

    try:
        inst = ProjectActivityInstance.objects.filter(id=int(instance_id)).first()
        if not inst:
            return JsonResponse({'success': False, 'message': 'Activity instance not found.'}, status=404)

        if inst.status == 'Completed':
            return JsonResponse({'success': False, 'message': 'Activity is already completed.'}, status=400)

        inst.status = 'In Progress'
        if not inst.actual_start_time:
            inst.actual_start_time = timezone.now()
        if not inst.assigned_employee_id:
            inst.assigned_employee = employee
        inst.save(update_fields=['status', 'actual_start_time', 'assigned_employee', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'Activity started successfully.',
            'instance_id': inst.id,
            'status': inst.status,
            'actual_start_time': inst.actual_start_time.isoformat(),
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error starting activity.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def upload_activity_photo(request):
    """
    6. Upload photo evidence (Before, After, or Intermediate).
    Supports multipart image upload with GPS and capture timestamp.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    employee, err = authenticate_employee_request(request)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=400)

    instance_id = request.POST.get('instance_id')
    photo_stage = request.POST.get('photo_stage', 'Before').capitalize()
    latitude = request.POST.get('latitude')
    longitude = request.POST.get('longitude')
    capture_time = request.POST.get('capture_timestamp')

    if not instance_id:
        return JsonResponse({'success': False, 'message': 'instance_id is required.'}, status=422)

    if 'photo' not in request.FILES:
        return JsonResponse({'success': False, 'message': 'Photo file is required.'}, status=422)

    try:
        inst = ProjectActivityInstance.objects.filter(id=int(instance_id)).first()
        if not inst:
            return JsonResponse({'success': False, 'message': 'Activity instance not found.'}, status=404)

        uploaded_file = request.FILES['photo']
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'activity_photos')
        os.makedirs(upload_dir, exist_ok=True)

        ext = os.path.splitext(uploaded_file.name)[1] or '.jpg'
        filename = f"act_{inst.id}_{photo_stage.lower()}_{uuid.uuid4().hex[:10]}{ext}"
        filepath = os.path.join(upload_dir, filename)

        with open(filepath, 'wb+') as dest:
            for chunk in uploaded_file.chunks():
                dest.write(chunk)

        cap_dt = None
        if capture_time:
            try:
                cap_dt = datetime.fromisoformat(capture_time.replace('Z', '+00:00'))
            except Exception:
                cap_dt = timezone.now()
        else:
            cap_dt = timezone.now()

        photo = ProjectActivityPhoto.objects.create(
            instance=inst,
            photo_stage=photo_stage if photo_stage in ['Before', 'After', 'Intermediate'] else 'Before',
            photo_file=f"activity_photos/{filename}",
            uploaded_by=employee,
            latitude=latitude or None,
            longitude=longitude or None,
            capture_timestamp=cap_dt,
            verification_status='Verified'
        )

        # Advance status to In Progress if currently Pending
        if inst.status == 'Pending':
            inst.status = 'In Progress'
            if not inst.actual_start_time:
                inst.actual_start_time = timezone.now()
            inst.save(update_fields=['status', 'actual_start_time', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': f'{photo_stage} photo uploaded successfully.',
            'photo': {
                'id': photo.id,
                'stage': photo.photo_stage,
                'file_url': f"/media/{photo.photo_file}",
                'created_at': photo.created_at.isoformat(),
            }
        }, status=201)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error uploading activity photo.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def submit_activity_form(request):
    """
    5. Submitting activity form answers using dynamic form submission architecture.
    Validates form answers against rules and persists into FormSubmission and ProjectActivityInstance.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    employee, err = authenticate_employee_request(request)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=400)

    data = get_request_data(request)
    instance_id = data.get('instance_id')
    submission_data = data.get('submission_data')

    if not instance_id or submission_data is None:
        return JsonResponse({
            'success': False,
            'message': 'instance_id and submission_data are required.'
        }, status=422)

    try:
        inst = ProjectActivityInstance.objects.filter(id=int(instance_id)).select_related('project_activity', 'activity').first()
        if not inst:
            return JsonResponse({'success': False, 'message': 'Activity instance not found.'}, status=404)

        form = inst.project_activity.form
        form_submission = None

        if form:
            is_flg, flg_dets = evaluate_form_submission(form.form_schema, submission_data)
            form_submission = FormSubmission.objects.create(
                company_id=employee.company_id,
                form_id=form.id,
                project_id=inst.project_id,
                emp_id=employee.id,
                submission_data=submission_data,
                is_flagged=is_flg,
                flagged_details=flg_dets
            )

        # Business exception rule check if ActivityFormConfiguration exists
        builder_config = ActivityFormConfiguration.objects.filter(activity=inst.activity).first()
        validation_result = {'status': 'valid', 'exceptions': []}
        if builder_config:
            dict_rep = ActivityFormService.form_to_dict(builder_config)
            fields_config = dict_rep.get('fields', [])
            eval_res = ActivityFormService.evaluate_submission(fields_config, submission_data if isinstance(submission_data, dict) else {})
            validation_result = {
                'status': 'error' if not eval_res.get('is_valid') else ('exception' if eval_res.get('has_exceptions') else 'valid'),
                'errors': eval_res.get('validation_errors', {}),
                'exceptions': eval_res.get('exceptions', []),
            }

        inst.form_submission = form_submission
        inst.submission_data = submission_data if isinstance(submission_data, dict) else {}
        inst.validation_result = validation_result
        inst.save(update_fields=['form_submission', 'submission_data', 'validation_result', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'Form answers submitted and saved successfully.',
            'submission_id': form_submission.id if form_submission else None,
            'validation_result': validation_result
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error submitting activity form answers.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def complete_activity_instance(request):
    """
    7. Completes an activity occurrence: verifies photo evidence requirements and marks status as Completed.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    employee, err = authenticate_employee_request(request)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=400)

    data = get_request_data(request)
    instance_id = data.get('instance_id')
    remarks = data.get('remarks', '').strip()

    if not instance_id:
        return JsonResponse({'success': False, 'message': 'instance_id is required.'}, status=422)

    try:
        inst = ProjectActivityInstance.objects.filter(id=int(instance_id)).select_related('activity').first()
        if not inst:
            return JsonResponse({'success': False, 'message': 'Activity instance not found.'}, status=404)

        # Enforce photo requirements if configured
        form_config = ActivityFormConfiguration.objects.filter(activity=inst.activity).first()
        if form_config and hasattr(form_config, 'photo_settings'):
            ps = form_config.photo_settings
            if ps.before_photo_required:
                if not inst.photos.filter(photo_stage='Before').exists():
                    return JsonResponse({
                        'success': False,
                        'message': 'Mandatory Before Photo is required before completing this activity.'
                    }, status=422)
            if ps.after_photo_required:
                if not inst.photos.filter(photo_stage='After').exists():
                    return JsonResponse({
                        'success': False,
                        'message': 'Mandatory After Photo is required before completing this activity.'
                    }, status=422)

        inst.status = 'Completed'
        inst.submitted_by = employee
        inst.submitted_at = timezone.now()
        inst.actual_completion_time = timezone.now()
        if remarks:
            inst.completion_remarks = remarks
        inst.save(update_fields=['status', 'submitted_by', 'submitted_at', 'actual_completion_time', 'completion_remarks', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'Activity marked as completed successfully.',
            'instance_id': inst.id,
            'status': inst.status,
            'completed_at': inst.actual_completion_time.isoformat()
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error completing activity instance.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def report_activity_issue(request):
    """
    8. Reporting an inability to complete an activity (operational exception).
    Collects issue category, description, explanation, GPS, and optional photo without marking completed.
    Sets instance status to 'Unable to Complete' or 'Exception Reported'.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    employee, err = authenticate_employee_request(request)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=400)

    data = get_request_data(request)
    instance_id = data.get('instance_id') or request.POST.get('instance_id')
    issue_category = data.get('issue_category') or request.POST.get('issue_category')
    short_description = data.get('short_description') or request.POST.get('short_description', '').strip()
    detailed_explanation = data.get('detailed_explanation') or request.POST.get('detailed_explanation', '').strip()
    latitude = data.get('latitude') or request.POST.get('latitude')
    longitude = data.get('longitude') or request.POST.get('longitude')

    if not instance_id or not issue_category or not short_description or not detailed_explanation:
        return JsonResponse({
            'success': False,
            'message': 'Validation failed.',
            'errors': {
                'instance_id': ['Instance ID is required.'] if not instance_id else [],
                'issue_category': ['Issue category is required.'] if not issue_category else [],
                'short_description': ['Short description is required.'] if not short_description else [],
                'detailed_explanation': ['Detailed explanation is required.'] if not detailed_explanation else []
            }
        }, status=422)

    try:
        inst = ProjectActivityInstance.objects.filter(id=int(instance_id)).first()
        if not inst:
            return JsonResponse({'success': False, 'message': 'Activity instance not found.'}, status=404)

        saved_photo_path = None
        if 'supporting_photo' in request.FILES:
            uploaded = request.FILES['supporting_photo']
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'activity_issues')
            os.makedirs(upload_dir, exist_ok=True)
            ext = os.path.splitext(uploaded.name)[1] or '.jpg'
            filename = f"issue_{inst.id}_{uuid.uuid4().hex[:10]}{ext}"
            filepath = os.path.join(upload_dir, filename)
            with open(filepath, 'wb+') as dest:
                for chunk in uploaded.chunks():
                    dest.write(chunk)
            saved_photo_path = f"activity_issues/{filename}"

        issue = ProjectActivityIssue.objects.create(
            instance=inst,
            issue_category=issue_category,
            short_description=short_description,
            detailed_explanation=detailed_explanation,
            supporting_photo=saved_photo_path,
            reported_by=employee,
            latitude=latitude or None,
            longitude=longitude or None,
            status='Reported'
        )

        # Update activity occurrence status to 'Unable to Complete'
        inst.status = 'Unable to Complete'
        inst.save(update_fields=['status', 'updated_at'])

        return JsonResponse({
            'success': True,
            'message': 'Inability to complete activity reported successfully. Your report is under review.',
            'issue_id': issue.id,
            'status': inst.status
        }, status=201)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error reporting activity exception.',
            'error': str(e)
        }, status=500)


@csrf_exempt
def get_employee_activity_history(request):
    """
    9. Viewing the employee's submitted activity and exception history.
    """
    employee, err = authenticate_employee_request(request)
    if err:
        return JsonResponse({'success': False, 'message': err}, status=400)

    try:
        completed_instances = ProjectActivityInstance.objects.filter(
            submitted_by=employee
        ).select_related('project', 'activity').order_by('-actual_completion_time')

        reported_issues = ProjectActivityIssue.objects.filter(
            reported_by=employee
        ).select_related('instance', 'instance__project', 'instance__activity').order_by('-created_at')

        history_items = []
        for c in completed_instances:
            history_items.append({
                'type': 'execution',
                'instance_id': c.id,
                'activity_title': c.activity.activity_title,
                'project_name': c.project.project_name or c.project.client_name,
                'scheduled_date': str(c.scheduled_date),
                'completed_at': c.actual_completion_time.isoformat() if c.actual_completion_time else None,
                'status': c.status,
                'remarks': c.completion_remarks,
            })

        for iss in reported_issues:
            history_items.append({
                'type': 'issue',
                'issue_id': iss.id,
                'instance_id': iss.instance_id,
                'activity_title': iss.instance.activity.activity_title,
                'project_name': iss.instance.project.project_name or iss.instance.project.client_name,
                'issue_category': iss.issue_category,
                'short_description': iss.short_description,
                'reported_at': iss.created_at.isoformat() if iss.created_at else None,
                'issue_status': iss.status,
                'admin_remarks': iss.admin_remarks,
            })

        return JsonResponse({
            'success': True,
            'message': 'Activity history retrieved successfully.',
            'employee_id': employee.id,
            'data': history_items
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error retrieving activity history.',
            'error': str(e)
        }, status=500)


