"""
Comprehensive Verification Tests for Agreement Management in Add Project & Edit Project
Verifies all 10 project requirements:
1. Create a project with Agreement = Yes.
2. Verify Agreement Start Date and End Date.
3. Verify Monthly, Quarterly, and Yearly billing frequency selections.
4. Verify Charge Frequency.
5. Verify Bill Date.
6. Create a project with Agreement = No.
7. Verify Prepaid and Free Period fields.
8. Edit an existing project and verify saved agreement information.
9. Verify that projects without agreement information continue working.
10. Verify that all existing Add Project wizard steps work correctly.
"""
import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarpro_core.settings')
django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.operations.models import Project
from apps.masters.models import SiteMaster
from apps.employees.models import Employee


def run_tests():
    print("=" * 70)
    print("AGREEMENT MANAGEMENT VERIFICATION TEST SUITE (WITH DOCUMENT UPLOAD)")
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

    # 1. Test GET /admin/projects/create renders wizard with Agreement in Step 1
    res = client.get('/admin/projects/create')
    assert res.status_code == 200, f"Add Project wizard failed to render: {res.status_code}"
    content = res.content.decode('utf-8')

    # Verify Agreement & Billing is inside Step 1 and NOT in Step 2
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
    assert 'charge_frequency' in content, "Charge Frequency dropdown missing"
    assert 'bill_date' in content, "Bill Date field missing"
    assert 'prepaid_select' in content, "Prepaid dropdown missing"
    assert 'free_period_check' in content, "Free Period Check missing"
    print(" [PASS] Step 1: Add Project wizard renders with Agreement & Billing relocated to Step 1 (200 OK)")

    # 2. Test Create Project with Agreement = Yes & Upload Agreement Document
    start_d = today
    end_d = today + timedelta(days=365)
    bill_d = today + timedelta(days=30)

    sample_doc = SimpleUploadedFile("contract_agreement.pdf", b"%PDF-1.4 sample contract agreement content", content_type="application/pdf")
    
    post_data_yes = {
        'client_name': 'TEST_AGREEMENT_CLIENT_YES_MONTHLY',
        'project_name': 'Solar Agreement Project 1',
        'site_id': site.id,
        'start_date': str(start_d),
        'end_date': str(end_d),
        'reporting_frequency': 'Weekly',
        'agreement': 'Yes',
        'agreement_document': sample_doc,
        'agreement_start_date': str(start_d),
        'agreement_end_date': str(end_d),
        'billing_frequency': 'Monthly',
        'charge_frequency': 'Monthly',
        'bill_date': str(bill_d),
        'notes': 'Test project with Agreement = Yes',
    }
    res = client.post('/admin/projects/store', post_data_yes, follow=True)
    assert res.status_code == 200, f"Project creation failed: {res.status_code}"
    p_yes_monthly = Project.objects.filter(client_name='TEST_AGREEMENT_CLIENT_YES_MONTHLY').first()
    assert p_yes_monthly is not None, "Project with Agreement=Yes was not created"
    assert p_yes_monthly.agreement == 'Yes', f"Expected agreement 'Yes', got {p_yes_monthly.agreement}"
    assert bool(p_yes_monthly.agreement_document), "Agreement document was not saved to project"
    assert "contract_agreement" in p_yes_monthly.agreement_document.name, f"Expected filename in document path, got {p_yes_monthly.agreement_document.name}"
    assert p_yes_monthly.agreement_start_date == start_d, "Agreement Start Date mismatch"
    assert p_yes_monthly.agreement_end_date == end_d, "Agreement End Date mismatch"
    assert p_yes_monthly.billing_frequency == 'Monthly', "Billing Frequency mismatch"
    assert p_yes_monthly.charge_frequency == 'Monthly', "Charge Frequency mismatch"
    assert p_yes_monthly.bill_date == bill_d, "Bill Date mismatch"
    assert p_yes_monthly.prepaid == 'No', "Prepaid should be 'No' when Agreement is 'Yes'"
    assert p_yes_monthly.free_period_check is False, "Free period should be False when Agreement is 'Yes'"
    print(" [PASS] Step 2: Project with Agreement = Yes, Monthly Billing & Document Upload created and verified")

    # 3. Test Create Project with Agreement = Yes without document (Optional doc)
    post_data_quarterly = {
        'client_name': 'TEST_AGREEMENT_CLIENT_YES_QUARTERLY',
        'project_name': 'Solar Agreement Project Quarterly',
        'site_id': site.id,
        'start_date': str(start_d),
        'end_date': str(end_d),
        'reporting_frequency': 'Monthly',
        'agreement': 'Yes',
        'agreement_start_date': str(start_d),
        'agreement_end_date': str(end_d),
        'billing_frequency': 'Quarterly',
        'charge_frequency': 'Quarterly',
        'bill_date': str(today + timedelta(days=90)),
    }
    client.post('/admin/projects/store', post_data_quarterly, follow=True)
    p_quarterly = Project.objects.filter(client_name='TEST_AGREEMENT_CLIENT_YES_QUARTERLY').first()
    assert p_quarterly.billing_frequency == 'Quarterly' and p_quarterly.charge_frequency == 'Quarterly'
    assert not bool(p_quarterly.agreement_document), "Agreement document should be empty when none provided"
    print(" [PASS] Step 3: Agreement = Yes without document verified")

    # 4. Test Yearly Billing & Charge Frequency
    post_data_yearly = {
        'client_name': 'TEST_AGREEMENT_CLIENT_YES_YEARLY',
        'project_name': 'Solar Agreement Project Yearly',
        'site_id': site.id,
        'start_date': str(start_d),
        'end_date': str(end_d),
        'reporting_frequency': 'Monthly',
        'agreement': 'Yes',
        'agreement_start_date': str(start_d),
        'agreement_end_date': str(end_d),
        'billing_frequency': 'Yearly',
        'charge_frequency': 'Yearly',
        'bill_date': str(today + timedelta(days=365)),
    }
    client.post('/admin/projects/store', post_data_yearly, follow=True)
    p_yearly = Project.objects.filter(client_name='TEST_AGREEMENT_CLIENT_YES_YEARLY').first()
    assert p_yearly.billing_frequency == 'Yearly' and p_yearly.charge_frequency == 'Yearly'
    print(" [PASS] Step 4: Yearly billing frequency and charge frequency verified")

    # 5. Test Create Project with Agreement = No (Prepaid = Yes, Free Period = Checked, No doc)
    free_end = today + timedelta(days=60)
    post_data_no = {
        'client_name': 'TEST_AGREEMENT_CLIENT_NO_PREPAID',
        'project_name': 'Solar Prepaid Project',
        'site_id': site.id,
        'start_date': str(start_d),
        'end_date': str(end_d),
        'reporting_frequency': 'Weekly',
        'agreement': 'No',
        'prepaid': 'Yes',
        'free_period_check': '1',
        'free_period_end_date': str(free_end),
        'agreement_start_date': str(start_d),
        'billing_frequency': 'Monthly',
    }
    res = client.post('/admin/projects/store', post_data_no, follow=True)
    assert res.status_code == 200
    p_no = Project.objects.filter(client_name='TEST_AGREEMENT_CLIENT_NO_PREPAID').first()
    assert p_no is not None, "Project with Agreement=No was not created"
    assert p_no.agreement == 'No', "Expected agreement 'No'"
    assert p_no.prepaid == 'Yes', "Prepaid mismatch"
    assert p_no.free_period_check is True, "Free Period Check mismatch"
    assert p_no.free_period_end_date == free_end, "Free Period End Date mismatch"
    assert not bool(p_no.agreement_document), "Agreement document must be None when Agreement is No"
    assert p_no.agreement_start_date is None, "Agreement Start Date must be None when Agreement is No"
    assert p_no.billing_frequency is None, "Billing Frequency must be None when Agreement is No"
    print(" [PASS] Step 5: Project with Agreement = No (Prepaid & Free Period) created and sanitized")

    # 6. Test Edit Existing Project & Verify Saved Agreement and Document
    edit_res = client.get(f'/admin/projects/{p_yes_monthly.id}/edit')
    assert edit_res.status_code == 200, "Edit Project failed to render"
    edit_content = edit_res.content.decode('utf-8')
    assert 'edit_agreement_select' in edit_content, "Edit Agreement dropdown missing"
    assert 'contract_agreement' in edit_content, "Previously uploaded agreement document not displayed in edit form"
    assert str(p_yes_monthly.agreement_start_date) in edit_content, "Saved agreement start date not found in edit form"
    assert str(p_yes_monthly.bill_date) in edit_content, "Saved bill date not found in edit form"
    print(" [PASS] Step 6: Edit Project renders with pre-filled Agreement details & uploaded document")

    # 7. Test Replace Agreement Document in Edit Project
    new_doc = SimpleUploadedFile("replaced_contract.jpg", b"fake jpeg content", content_type="image/jpeg")
    update_data_replace = {
        'client_name': 'TEST_AGREEMENT_CLIENT_YES_MONTHLY',
        'project_name': 'Solar Agreement Project Replaced',
        'site_id': site.id,
        'status': 'in_progress',
        'start_date': str(start_d),
        'end_date': str(end_d),
        'reporting_frequency': 'Daily',
        'agreement': 'Yes',
        'agreement_document': new_doc,
        'agreement_start_date': str(start_d),
        'agreement_end_date': str(end_d),
        'billing_frequency': 'Monthly',
        'charge_frequency': 'Monthly',
        'bill_date': str(bill_d),
    }
    client.post(f'/admin/projects/{p_yes_monthly.id}/update', update_data_replace, follow=True)
    p_yes_monthly.refresh_from_db()
    assert "replaced_contract" in p_yes_monthly.agreement_document.name, "Agreement document replacement failed"
    print(" [PASS] Step 7: Agreement document successfully replaced with new file")

    # 8. Test Remove Agreement Document in Edit Project
    update_data_remove = {
        'client_name': 'TEST_AGREEMENT_CLIENT_YES_MONTHLY',
        'project_name': 'Solar Agreement Project Doc Removed',
        'site_id': site.id,
        'status': 'in_progress',
        'start_date': str(start_d),
        'end_date': str(end_d),
        'reporting_frequency': 'Daily',
        'agreement': 'Yes',
        'remove_agreement_document': '1',
        'agreement_start_date': str(start_d),
        'agreement_end_date': str(end_d),
        'billing_frequency': 'Monthly',
        'charge_frequency': 'Monthly',
        'bill_date': str(bill_d),
    }
    client.post(f'/admin/projects/{p_yes_monthly.id}/update', update_data_remove, follow=True)
    p_yes_monthly.refresh_from_db()
    assert not bool(p_yes_monthly.agreement_document), "Agreement document was not removed"
    print(" [PASS] Step 8: Agreement document successfully removed on request")

    # 9. Update project from Agreement=Yes to Agreement=No with Prepaid=Yes
    update_data = {
        'client_name': 'TEST_AGREEMENT_CLIENT_YES_MONTHLY',
        'project_name': 'Updated Solar Project to No Agreement',
        'site_id': site.id,
        'status': 'in_progress',
        'start_date': str(start_d),
        'end_date': str(end_d),
        'reporting_frequency': 'Daily',
        'agreement': 'No',
        'prepaid': 'Yes',
        'free_period_check': '1',
        'free_period_end_date': str(today + timedelta(days=45)),
    }
    client.post(f'/admin/projects/{p_yes_monthly.id}/update', update_data, follow=True)
    p_yes_monthly.refresh_from_db()
    assert p_yes_monthly.agreement == 'No', "Failed to update Agreement to 'No'"
    assert p_yes_monthly.prepaid == 'Yes', "Failed to update Prepaid to 'Yes'"
    assert p_yes_monthly.agreement_start_date is None, "Agreement fields should be cleared after update to 'No'"
    assert p_yes_monthly.billing_frequency is None, "Billing frequency should be cleared after update to 'No'"
    assert not bool(p_yes_monthly.agreement_document), "Agreement doc should be cleared when Agreement is No"
    print(" [PASS] Step 9: Successfully updated existing project from Agreement=Yes to Agreement=No")

    # 10. Verify legacy projects without agreement continue working cleanly
    legacy_p = Project.objects.create(
        company_id=1,
        client_name='TEST_AGREEMENT_LEGACY_PROJECT',
        project_name='Legacy Project Without Agreement',
        site_id=site.id,
        status='planning'
    )
    assert legacy_p.agreement == 'No', "Default agreement should be 'No'"
    assert legacy_p.agreement_start_date is None
    assert not bool(legacy_p.agreement_document)
    list_res = client.get('/admin/projects')
    assert list_res.status_code == 200, "Projects index failed to render"
    assert b'TEST_AGREEMENT_LEGACY_PROJECT' in list_res.content
    print(" [PASS] Step 10: Legacy projects without agreement information continue working cleanly")

    # Clean up test projects
    Project.objects.filter(client_name__startswith='TEST_AGREEMENT_').delete()
    print(" [PASS] Step 11: Cleaned up temporary test projects")

    print("\n" + "=" * 70)
    print("ALL 11 AGREEMENT MANAGEMENT & DOCUMENT UPLOAD TESTS PASSED (100%)!")
    print("=" * 70)


if __name__ == '__main__':
    run_tests()


if __name__ == '__main__':
    run_tests()
