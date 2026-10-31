import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarpro_core.settings')
django.setup()

from apps.authentication.models import AdminUser
from apps.authentication.hashers import LaravelBcryptPasswordHasher
from apps.masters.models import (
    DepartmentMaster, DesignationMaster, SiteMaster,
    AttendanceMaster, DocumentTypeMaster, SMTPConfiguration, AccessControl
)
from apps.employees.models import Employee
from apps.inventory.models import StockCategory, OpeningStock, AssignedStock
from apps.operations.models import Project
from apps.expenses.models import ExpenseCategory
from apps.dynamic_forms.models import DynamicForm

hasher = LaravelBcryptPasswordHasher()


def seed_database():
    print("[*] Starting SolarPro database seeding...")

    # 1. Admin Users
    admin_users = [
        {"email": "admin@solarpro.com", "password": "password123"},
        {"email": "shimpikumudini2@gmail.com", "password": "password123"},
    ]
    for u in admin_users:
        user, created = AdminUser.objects.get_or_create(
            email=u["email"],
            defaults={
                "password": hasher.encode(u["password"], hasher.salt()),
                "company_id": 1,
                "is_admin": 1
            }
        )
        if created:
            print(f"  [+] Created Admin User: {u['email']}")
        else:
            # Update password hash just in case
            user.password = hasher.encode(u["password"], hasher.salt())
            user.save()
            print(f"  [*] Updated Admin User: {u['email']}")

    # 2. Departments
    dept_names = ["Operations", "Maintenance", "Engineering", "Inventory", "Finance"]
    depts = {}
    for d in dept_names:
        obj, _ = DepartmentMaster.objects.get_or_create(
            department_name=d,
            company_id=1,
            defaults={"added_by": "Admin"}
        )
        depts[d] = obj.id
    print(f"  [+] Seeded {len(dept_names)} Departments")

    # 3. Designations
    designations = [
        ("Project Manager", depts.get("Operations")),
        ("Site Engineer", depts.get("Engineering")),
        ("Technician", depts.get("Maintenance")),
        ("Field Staff", depts.get("Operations")),
        ("Inventory Manager", depts.get("Inventory")),
    ]
    desig_map = {}
    for title, dept_id in designations:
        obj, _ = DesignationMaster.objects.get_or_create(
            designation_name=title,
            company_id=1,
            defaults={"department_id": dept_id, "added_by": "Admin"}
        )
        desig_map[title] = obj.id
    print(f"  [+] Seeded {len(designations)} Designations")

    # 4. Sites
    sites = [
        {
            "site_name": "Solar Plant Alpha - Mumbai HQ",
            "site_address": "Bandra Kurla Complex, Mumbai, Maharashtra",
            "contact_number": "+91 9876543210",
            "latitude": 19.0657,
            "longitude": 72.8687,
            "radius": 500.00
        },
        {
            "site_name": "Solar Plant Beta - Pune Hub",
            "site_address": "Hinjawadi Phase 2, Pune, Maharashtra",
            "contact_number": "+91 9876543211",
            "latitude": 18.5913,
            "longitude": 73.7389,
            "radius": 500.00
        }
    ]
    for s in sites:
        SiteMaster.objects.get_or_create(
            site_name=s["site_name"],
            defaults=s
        )
    print("  [+] Seeded Sites")

    # 5. Attendance Master
    AttendanceMaster.objects.get_or_create(
        id=1,
        defaults={
            "working_hours": "9 hours",
            "required_working_hours": "9",
            "latitude": 19.0657,
            "longitude": 72.8687,
            "company_id": 1
        }
    )
    print("  [+] Seeded Attendance Master")

    # 6. Document Types
    doc_types = [
        "Site Survey Report",
        "Single Line Diagram (SLD)",
        "Commissioning Report",
        "Safety Clearance Certificate",
        "Vendor Invoice"
    ]
    for dt in doc_types:
        DocumentTypeMaster.objects.get_or_create(
            type_name=dt,
            company_id=1,
            defaults={"status": "active"}
        )
    print(f"  [+] Seeded {len(doc_types)} Document Types")

    # 7. Sample Employees
    emp_password_hash = hasher.encode("password123", hasher.salt())
    employees_data = [
        {
            "name": "Rahul Sharma",
            "app_username": "rahul.sharma",
            "email": "rahul.sharma@solarpro.com",
            "phone": "9811122233",
            "role": desig_map.get("Site Engineer", 2),
            "status": "active"
        },
        {
            "name": "Amit Patel",
            "app_username": "amit.patel",
            "email": "amit.patel@solarpro.com",
            "phone": "9822233344",
            "role": desig_map.get("Technician", 3),
            "status": "active"
        }
    ]
    seeded_emps = []
    for emp_info in employees_data:
        emp, created = Employee.objects.get_or_create(
            app_username=emp_info["app_username"],
            defaults={
                "company_id": 1,
                "name": emp_info["name"],
                "app_password": emp_password_hash,
                "email": emp_info["email"],
                "phone": emp_info["phone"],
                "role": emp_info["role"],
                "status": emp_info["status"],
                "documents": []
            }
        )
        if not created:
            emp.app_password = emp_password_hash
            emp.save(update_fields=['app_password'])
        seeded_emps.append(emp)
    print(f"  [+] Seeded {len(seeded_emps)} Employees (Username: rahul.sharma, amit.patel / Password: password123)")

    # 8. Stock Categories
    stock_cats = ["Solar PV Modules", "Inverters", "Mounting Structures", "DC Cables", "AC Distribution Boxes"]
    cat_ids = {}
    for sc in stock_cats:
        c_obj, _ = StockCategory.objects.get_or_create(category_name=sc)
        cat_ids[sc] = c_obj.id
    print(f"  [+] Seeded {len(stock_cats)} Stock Categories")

    # 9. Opening Stock Items
    stock_items = [
        {"item_name": "540W Mono PERC Solar Panels", "category": cat_ids.get("Solar PV Modules"), "unit": "nos", "quantity": 300, "rate": 8500, "low_stock_threshold": 20},
        {"item_name": "50kW String Grid-Tie Inverter", "category": cat_ids.get("Inverters"), "unit": "nos", "quantity": 12, "rate": 120000, "low_stock_threshold": 3},
        {"item_name": "4 sqmm DC Solar Cable Red/Black", "category": cat_ids.get("DC Cables"), "unit": "meters", "quantity": 2500, "rate": 50, "low_stock_threshold": 200},
    ]
    for it in stock_items:
        OpeningStock.objects.get_or_create(
            item_name=it["item_name"],
            defaults=it
        )
    print("  [+] Seeded Opening Stock items")

    # 10. Sample Project
    p1, _ = Project.objects.get_or_create(
        client_name="SunPower 1.5MW Solar Park",
        defaults={
            "company_id": 1,
            "site_id": 1,
            "site_manager": seeded_emps[0].id if seeded_emps else 1,
            "field_staff": [seeded_emps[0].id, seeded_emps[1].id] if len(seeded_emps) > 1 else [1],
            "status": "in_progress",
            "reporting_frequency": "daily",
            "notes": "1.5MW Ground Mount solar project in Bandra Kurla site."
        }
    )
    print(f"  [+] Seeded Project: {p1.client_name}")

    # Seed assigned stock for testing
    op_first = OpeningStock.objects.first()
    if op_first:
        AssignedStock.objects.get_or_create(
            project_id=p1.id,
            item_id=op_first.id,
            defaults={"qty": 50, "used_qty": 10}
        )
        print("  [+] Seeded Assigned Stock for Project")

    # 11. Expense Categories
    exp_cats = ["Travel & Fuel", "Food & Meals", "Site Consumables", "Tools & Safety", "Emergency Spares"]
    for ec in exp_cats:
        ExpenseCategory.objects.get_or_create(
            category_name=ec,
            company_id=1
        )
    print(f"  [+] Seeded {len(exp_cats)} Expense Categories")

    # 12. Dynamic Form Template
    form_schema = {
        "columns": ["Block 01", "Block 02", "Inverter Station 01"],
        "sections": [
            {
                "name": "PV Module & String Checks",
                "rows": [
                    {"name": "String Open Circuit Voltage (Voc)", "type": "number", "unit": "V"},
                    {"name": "Visual Soiling / Dust Level", "type": "text", "unit": ""},
                    {"name": "MC4 Connector Condition", "type": "text", "unit": ""}
                ]
            },
            {
                "name": "Inverter Status",
                "rows": [
                    {"name": "AC Active Power Output", "type": "number", "unit": "kW"},
                    {"name": "Internal Heatsink Temperature", "type": "number", "unit": "°C"},
                    {"name": "Daily Yield Generation", "type": "number", "unit": "kWh"}
                ]
            }
        ]
    }
    DynamicForm.objects.get_or_create(
        form_name="Daily Solar Plant Health & Maintenance Checklist",
        defaults={
            "company_id": 1,
            "description": "Daily preventive maintenance inspection form for field engineers.",
            "project_ids": [p1.id],
            "form_schema": form_schema,
            "is_active": 1
        }
    )
    print("  [+] Seeded Dynamic Maintenance Form")

    # 13. SMTP Configuration #6
    SMTPConfiguration.objects.get_or_create(
        id=6,
        defaults={
            "config_name": "Default Gmail Gateway",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "notifications@solarpro.com",
            "smtp_pass": "sampleapppassword",
            "smtp_crypto": "tls",
            "from_email": "notifications@solarpro.com",
            "from_name": "SolarPro Alerts",
            "is_default": 1,
            "company_id": 1
        }
    )
    print("  [+] Seeded SMTP Configuration #6")

    print("\n[OK] Database seeding successfully completed!")


if __name__ == '__main__':
    seed_database()
