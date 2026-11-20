import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarpro_core.settings')
django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.operations.models import Project, ProjectBillingNotification
from apps.masters.models import SiteMaster
from apps.employees.models import Employee
from apps.operations.billing_service import calculate_billing_dates, sync_project_billing_notifications


def run_tests():
    print("=" * 70)
    print("COMPREHENSIVE DYNAMIC AGREEMENT & BILLING VERIFICATION SUITE")
    print("=" * 70)

    client = Client()
    today = date.today()

    # Setup Session
    session = client.session
    session['user_id'] = 1
    session['is_admin'] = 1
    session['company_id'] = 1
    session['name'] = 'Admin'
    session.save()

    site = SiteMaster.objects.first()
    if not site:
        site = SiteMaster.objects.create(
            site_name='Test Solar Site Alpha',
            site_address='100 Industrial Parkway',
            company_id=1,
            added_by='Admin'
        )

    # Clean up test projects
    Project.objects.filter(client_name__startswith='TEST_AGREEMENT_').delete()

    # -------------------------------------------------------------
    # 1. Test UI: Agreement in Step 1, Bill Date field REMOVED, Dynamic Fields Present
    # -------------------------------------------------------------
    res = client.get('/admin/projects/create')
    assert res.status_code == 200, f"Add Project wizard failed to render: {res.status_code}"
    content = res.content.decode('utf-8')

    step1_start = content.find('data-step="1"')
    step2_start = content.find('data-step="2"')
    step3_start = content.find('data-step="3"')
    agreement_pos = content.find('id="agreement_select"')
    
    assert step1_start < agreement_pos < step2_start, "Agreement & Billing must be located inside Step 1, not Step 2"
    assert content.find('id="agreement_select"', step2_start, step3_start) == -1, "Agreement & Billing must not exist in Step 2"

    assert 'agreement_select' in content, "Agreement select dropdown missing in Add Project"
    assert 'agreement_document_input' in content, "Agreement Document upload input missing"
    assert 'agreement_start_date' in content, "Agreement Start Date field missing"
    assert 'agreement_end_date' in content, "Agreement End Date field missing"
    assert 'billing_frequency' in content, "Billing Frequency dropdown missing"
    assert 'billing_day' in content, "Billing Day dropdown missing"
    assert 'billing_month' in content, "Billing Month dropdown missing"
    
    # Crucial Requirement: Bill Date input field removed from UI
    assert 'name="bill_date"' not in content, "Bill Date input must be completely removed from the Add Project UI"
    
    print(" [PASS] Step 1: Add Project wizard UI verified (Agreement in Step 1, Bill Date removed, Dynamic billing fields present)")

    # -------------------------------------------------------------
    # 2. Test Monthly Billing: Billing Day = 5, Generates 1 notification per month
    # -------------------------------------------------------------
    start_d = date(2026, 1, 1)
    end_d = date(2026, 6, 30)

    post_data_monthly = {
        'client_name': 'TEST_AGREEMENT_CLIENT_MONTHLY_5',
        'project_name': 'Solar Monthly Billing Project',
        'site_id': site.id,
        'start_date': str(start_d),
        'end_date': str(end_d),
        'reporting_frequency': 'Weekly',
        'agreement': 'Yes',
        'agreement_start_date': str(start_d),
        'agreement_end_date': str(end_d),
        'billing_frequency': 'Monthly',
        'billing_day': '5',
        'notes': 'Test monthly billing on 5th',
    }
    res = client.post('/admin/projects/store', post_data_monthly, follow=True)
    assert res.status_code == 200, f"Project creation failed: {res.status_code}"
    p_monthly = Project.objects.filter(client_name='TEST_AGREEMENT_CLIENT_MONTHLY_5').first()
    assert p_monthly is not None, "Monthly project was not created"
    assert p_monthly.agreement == 'Yes'
    assert p_monthly.billing_frequency == 'Monthly'
    assert p_monthly.billing_day == 5
    
    # Verify generated billing notifications
    notifs = list(ProjectBillingNotification.objects.filter(project=p_monthly).order_by('notification_date'))
    assert len(notifs) == 6, f"Expected exactly 6 monthly notifications between Jan and June, got {len(notifs)}"
    for idx, notif in enumerate(notifs):
        expected_month = idx + 1
        assert notif.notification_date == date(2026, expected_month, 5), f"Notification date mismatch: {notif.notification_date}"
    print(" [PASS] Step 2: Monthly billing generated exactly 1 notification per month on the 5th (6/6 notifications)")

    # -------------------------------------------------------------
    # 3. Test Quarterly Billing: Billing Day = 10, Generates 1 notification per quarter
    # -------------------------------------------------------------
    start_q = date(2026, 1, 1)
    end_q = date(2026, 12, 31)

    post_data_quarterly = {
        'client_name': 'TEST_AGREEMENT_CLIENT_QUARTERLY_10',
        'project_name': 'Solar Quarterly Billing Project',
        'site_id': site.id,
        'start_date': str(start_q),
        'end_date': str(end_q),
        'reporting_frequency': 'Monthly',
        'agreement': 'Yes',
        'agreement_start_date': str(start_q),
        'agreement_end_date': str(end_q),
        'billing_frequency': 'Quarterly',
        'billing_day': '10',
    }
    client.post('/admin/projects/store', post_data_quarterly, follow=True)
    p_quarterly = Project.objects.filter(client_name='TEST_AGREEMENT_CLIENT_QUARTERLY_10').first()
    assert p_quarterly.billing_frequency == 'Quarterly' and p_quarterly.billing_day == 10
    
    q_notifs = list(ProjectBillingNotification.objects.filter(project=p_quarterly).order_by('notification_date'))
    assert len(q_notifs) == 4, f"Expected exactly 4 quarterly notifications for 1 year, got {len(q_notifs)}"
    expected_dates = [date(2026, 1, 10), date(2026, 4, 10), date(2026, 7, 10), date(2026, 10, 10)]
    actual_dates = [n.notification_date for n in q_notifs]
    assert actual_dates == expected_dates, f"Quarterly dates mismatch: {actual_dates} vs {expected_dates}"
    print(" [PASS] Step 3: Quarterly billing generated exactly 1 notification per quarter on the 10th (4/4 quarters)")

    # -------------------------------------------------------------
    # 4. Test Yearly Billing: Billing Month = January, Billing Day = 15
    # -------------------------------------------------------------
    start_y = date(2026, 1, 1)
    end_y = date(2028, 12, 31)

    post_data_yearly = {
        'client_name': 'TEST_AGREEMENT_CLIENT_YEARLY_JAN15',
        'project_name': 'Solar Yearly Billing Project',
        'site_id': site.id,
        'start_date': str(start_y),
        'end_date': str(end_y),
        'reporting_frequency': 'Monthly',
        'agreement': 'Yes',
        'agreement_start_date': str(start_y),
        'agreement_end_date': str(end_y),
        'billing_frequency': 'Yearly',
        'billing_month': 'January',
        'billing_day': '15',
    }
    client.post('/admin/projects/store', post_data_yearly, follow=True)
    p_yearly = Project.objects.filter(client_name='TEST_AGREEMENT_CLIENT_YEARLY_JAN15').first()
    assert p_yearly.billing_frequency == 'Yearly' and p_yearly.billing_month == 'January' and p_yearly.billing_day == 15

    y_notifs = list(ProjectBillingNotification.objects.filter(project=p_yearly).order_by('notification_date'))
    assert len(y_notifs) == 3, f"Expected exactly 3 yearly notifications (2026, 2027, 2028), got {len(y_notifs)}"
    expected_y_dates = [date(2026, 1, 15), date(2027, 1, 15), date(2028, 1, 15)]
    actual_y_dates = [n.notification_date for n in y_notifs]
    assert actual_y_dates == expected_y_dates, f"Yearly dates mismatch: {actual_y_dates} vs {expected_y_dates}"
    print(" [PASS] Step 4: Yearly billing generated exactly 1 notification per year on January 15 (3/3 years)")

    # -------------------------------------------------------------
    # 5. Test Clamping for Day 31 on 30-Day Months and Feb (Leap Year test)
    # -------------------------------------------------------------
    start_clamp = date(2026, 1, 1)
    end_clamp = date(2026, 4, 30)

    post_data_clamp = {
        'client_name': 'TEST_AGREEMENT_CLIENT_CLAMP_31',
        'project_name': 'Solar Day 31 Clamping Project',
        'site_id': site.id,
        'start_date': str(start_clamp),
        'end_date': str(end_clamp),
        'reporting_frequency': 'Monthly',
        'agreement': 'Yes',
        'agreement_start_date': str(start_clamp),
        'agreement_end_date': str(end_clamp),
        'billing_frequency': 'Monthly',
        'billing_day': '31',
    }
    client.post('/admin/projects/store', post_data_clamp, follow=True)
    p_clamp = Project.objects.filter(client_name='TEST_AGREEMENT_CLIENT_CLAMP_31').first()
    c_notifs = list(ProjectBillingNotification.objects.filter(project=p_clamp).order_by('notification_date'))
    assert len(c_notifs) == 4
    # Jan 31, Feb 28 (non-leap), Mar 31, Apr 30 (30-day month)
    assert c_notifs[0].notification_date == date(2026, 1, 31)
    assert c_notifs[1].notification_date == date(2026, 2, 28)
    assert c_notifs[2].notification_date == date(2026, 3, 31)
    assert c_notifs[3].notification_date == date(2026, 4, 30)
    print(" [PASS] Step 5: Day 31 clamping handled correctly across 31-day, 30-day, and February dates")

    # Leap Year Test: Feb 29 in 2028
    leap_dates = calculate_billing_dates(date(2028, 1, 1), date(2028, 3, 31), 'Monthly', 31)
    assert leap_dates[1][0] == date(2028, 2, 29), f"Leap year 2028 Feb should clamp to 29, got {leap_dates[1][0]}"
    print(" [PASS] Step 5b: Leap year February 29 clamping verified")

    # -------------------------------------------------------------
    # 6. Test Date Validation: End Date cannot be earlier than Start Date
    # -------------------------------------------------------------
    post_invalid_dates = {
        'client_name': 'TEST_AGREEMENT_CLIENT_INVALID_DATES',
        'project_name': 'Invalid Date Project',
        'site_id': site.id,
        'start_date': '2026-06-01',
        'end_date': '2026-01-01',
        'reporting_frequency': 'Weekly',
        'agreement': 'Yes',
        'agreement_start_date': '2026-06-01',
        'agreement_end_date': '2026-01-01',
        'billing_frequency': 'Monthly',
        'billing_day': '1',
    }
    res_inv = client.post('/admin/projects/store', post_invalid_dates, follow=True)
    p_inv = Project.objects.filter(client_name='TEST_AGREEMENT_CLIENT_INVALID_DATES').first()
    assert p_inv is None, "Project with End Date < Start Date should be rejected"
    print(" [PASS] Step 6: Validation correctly rejects Agreement End Date earlier than Start Date")

    # -------------------------------------------------------------
    # 7. Test Avoid Duplicate Notifications on Project Edit / Save
    # -------------------------------------------------------------
    initial_count = ProjectBillingNotification.objects.filter(project=p_monthly).count()
    # Save project again with same data
    update_data = {
        'client_name': p_monthly.client_name,
        'project_name': p_monthly.project_name,
        'site_id': site.id,
        'status': 'in_progress',
        'start_date': str(p_monthly.start_date),
        'end_date': str(p_monthly.end_date),
        'reporting_frequency': 'Weekly',
        'agreement': 'Yes',
        'agreement_start_date': str(p_monthly.agreement_start_date),
        'agreement_end_date': str(p_monthly.agreement_end_date),
        'billing_frequency': 'Monthly',
        'billing_day': '5',
    }
    client.post(f'/admin/projects/{p_monthly.id}/update', update_data, follow=True)
    after_count = ProjectBillingNotification.objects.filter(project=p_monthly).count()
    assert initial_count == after_count == 6, f"Expected no duplicate notifications, got {after_count}"
    print(" [PASS] Step 7: Saving existing project avoided duplicate notifications")

    # -------------------------------------------------------------
    # 8. Test Edit Project Form UI Renders Saved Billing Configuration
    # -------------------------------------------------------------
    edit_res = client.get(f'/admin/projects/{p_yearly.id}/edit')
    assert edit_res.status_code == 200
    edit_content = edit_res.content.decode('utf-8')
    assert 'edit_agreement_select' in edit_content
    assert 'name="bill_date"' not in edit_content, "Bill Date must be removed from Edit Project UI"
    assert 'edit_billing_day' in edit_content
    assert 'edit_billing_month' in edit_content
    print(" [PASS] Step 8: Edit Project UI renders with saved dynamic billing configuration")

    # -------------------------------------------------------------
    # 9. Test Switch Agreement from Yes to No Clears Notifications
    # -------------------------------------------------------------
    update_to_no = {
        'client_name': p_monthly.client_name,
        'project_name': p_monthly.project_name,
        'site_id': site.id,
        'status': 'in_progress',
        'start_date': str(p_monthly.start_date),
        'end_date': str(p_monthly.end_date),
        'reporting_frequency': 'Weekly',
        'agreement': 'No',
        'prepaid': 'Yes',
    }
    client.post(f'/admin/projects/{p_monthly.id}/update', update_to_no, follow=True)
    p_monthly.refresh_from_db()
    assert p_monthly.agreement == 'No'
    notifs_after_no = ProjectBillingNotification.objects.filter(project=p_monthly, is_sent=False).count()
    assert notifs_after_no == 0, "Unsent notifications should be cleared when Agreement is set to No"
    print(" [PASS] Step 9: Switching Agreement to No successfully cleared notifications")

    # -------------------------------------------------------------
    # 10. Clean up test projects
    # -------------------------------------------------------------
    Project.objects.filter(client_name__startswith='TEST_AGREEMENT_').delete()
    print(" [PASS] Step 10: Cleaned up temporary test projects")

    print("\n" + "=" * 70)
    print("ALL 10 DYNAMIC AGREEMENT & BILLING TESTS PASSED (100%)!")
    print("=" * 70)


if __name__ == '__main__':
    run_tests()
