import os
import smtplib
from email.mime.text import MIMEText
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.conf import settings
from django.db.models import Sum
from apps.authentication.decorators import admin_required
from apps.expenses.models import ExpenseCategory, Expense
from apps.employees.models import Employee
from apps.masters.models import SMTPConfiguration
from apps.operations.models import Project


def send_fcm_notification(fcm_token, title, body):
    if not fcm_token:
        return
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        cred_path = os.path.join(settings.BASE_DIR, 'firebase_credentials.json')
        if not os.path.exists(cred_path):
            # Also check parent dir
            cred_path = os.path.join(settings.BASE_DIR, '..', 'storage', 'app', 'firebase_credentials.json')

        if os.path.exists(cred_path):
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)

            msg = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=fcm_token,
            )
            messaging.send(msg)
    except Exception as e:
        print(f"FCM Notification Error: {e}")


def send_status_email(employee, amount, status, rejection_reason):
    if not employee or not employee.email:
        return
    try:
        smtp = SMTPConfiguration.objects.first()
        if not smtp:
            return

        body = f"Hello {employee.name},\n\nYour expense of ₹{amount} has been marked as {status.upper()}."
        if status == 'rejected' and rejection_reason:
            body += f"\nReason: {rejection_reason}"
        body += f"\n\nRegards,\nAdmin Team\n{smtp.from_name}"

        msg = MIMEText(body)
        msg['Subject'] = f"Expense {status.capitalize()} - {smtp.from_name}"
        msg['From'] = f"{smtp.from_name} <{smtp.from_email}>"
        msg['To'] = employee.email

        port = int(smtp.smtp_port) if smtp.smtp_port else 587
        if smtp.smtp_crypto == 'ssl' or port == 465:
            server = smtplib.SMTP_SSL(smtp.smtp_host, port, timeout=10)
        else:
            server = smtplib.SMTP(smtp.smtp_host, port, timeout=10)
            if smtp.smtp_crypto == 'tls' or port == 587:
                server.starttls()

        if smtp.smtp_user and smtp.smtp_pass:
            server.login(smtp.smtp_user, smtp.smtp_pass)
        server.sendmail(smtp.from_email, [employee.email], msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Expense Email Error: {e}")


# ==========================================
# 1. EXPENSE CATEGORIES CRUD
# ==========================================
@admin_required
def expense_categories_index(request):
    company_id = request.session.get('company_id', 1)
    categories = ExpenseCategory.objects.filter(company_id=company_id).order_by('-id')
    return render(request, 'admin/expenses/expensecategory.html', {
        'expenseCategories': categories,
    })


@admin_required
def expense_category_store(request):
    if request.method == 'POST':
        name = request.POST.get('category_name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
            return redirect('admin_expense_categories_index')

        ExpenseCategory.objects.create(
            category_name=name,
            company_id=request.session.get('company_id', 1),
        )
        messages.success(request, 'Expense category added successfully.')
    return redirect('admin_expense_categories_index')


@admin_required
def expense_category_update(request, id):
    category = get_object_or_404(ExpenseCategory, id=id)
    if request.method == 'POST':
        name = request.POST.get('category_name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
            return redirect('admin_expense_categories_index')

        category.category_name = name
        category.save()
        messages.success(request, 'Expense category updated successfully.')
    return redirect('admin_expense_categories_index')


@admin_required
def expense_category_destroy(request, id):
    category = get_object_or_404(ExpenseCategory, id=id)
    category.delete()
    messages.success(request, 'Expense category deleted successfully.')
    return redirect('admin_expense_categories_index')


# ==========================================
# 2. EMPLOYEE EXPENSES APPROVAL
# ==========================================
@admin_required
def employee_expenses(request):
    company_id = request.session.get('company_id', 1)
    search = request.GET.get('search', '').strip().lower()

    emps_map = {e.id: e.name for e in Employee.objects.all()}
    cats_map = {c.id: c.category_name for c in ExpenseCategory.objects.all()}

    qs = Expense.objects.filter(company_id=company_id, status='pending').order_by('-date', '-id')
    expenses = []
    for exp in qs:
        emp_name = emps_map.get(exp.employee_id, '—')
        cat_name = cats_map.get(exp.category_id, '—')
        if search and (search not in emp_name.lower() and search not in cat_name.lower()):
            continue

        expenses.append({
            'id': exp.id,
            'amount': exp.amount,
            'date': exp.date,
            'emp_comment': exp.emp_comment,
            'image': exp.image,
            'status': exp.status,
            'rejection_reason': exp.rejection_reason,
            'employee_name': emp_name,
            'category_name': cat_name,
        })

    return render(request, 'admin/expenses/employeeexpenses.html', {
        'expenses': expenses,
    })


@admin_required
def update_expense_status(request, id):
    expense = get_object_or_404(Expense, id=id)
    if request.method == 'POST':
        status = request.POST.get('status', 'pending')
        rejection_reason = request.POST.get('rejection_reason', '')

        expense.status = status
        expense.rejection_reason = rejection_reason if status == 'rejected' else None
        expense.save()

        # Send Notifications
        employee = Employee.objects.filter(id=expense.employee_id).first()
        if employee:
            # 1. FCM Push Notification
            title = f"Expense {status.capitalize()}"
            body = f"Your expense of ₹{expense.amount} has been marked as {status}."
            if status == 'rejected' and rejection_reason:
                body += f" Reason: {rejection_reason}"
            send_fcm_notification(employee.fcm_token, title, body)

            # 2. Dynamic SMTP Email
            send_status_email(employee, expense.amount, status, rejection_reason)

        messages.success(request, 'Expense status updated successfully.')
    return redirect('admin_employee_expenses_index')


# ==========================================
# 3. EXPENSE REPORT
# ==========================================
@admin_required
def expense_report(request):
    company_id = request.session.get('company_id', 1)
    employee_filter = request.GET.get('employee')
    status_filter = request.GET.get('status')
    project_filter = request.GET.get('project_id')

    qs = Expense.objects.filter(company_id=company_id).order_by('-date', '-id')

    emps_map = {e.id: e.name for e in Employee.objects.all()}
    cats_map = {c.id: c.category_name for c in ExpenseCategory.objects.all()}
    projs_map = {p.id: p.client_name for p in Project.objects.all()}

    if status_filter:
        qs = qs.filter(status=status_filter)
    if project_filter and project_filter.isdigit():
        qs = qs.filter(project_id=int(project_filter))

    expenses = []
    total_amount = Decimal('0.00')

    for exp in qs:
        emp_name = emps_map.get(exp.employee_id, '—')
        if employee_filter and emp_name != employee_filter:
            continue

        cat_name = cats_map.get(exp.category_id, '—')
        proj_name = projs_map.get(exp.project_id, '—') if exp.project_id else '—'

        total_amount += exp.amount
        expenses.append({
            'id': exp.id,
            'amount': exp.amount,
            'date': exp.date,
            'emp_comment': exp.emp_comment,
            'status': exp.status,
            'employee_name': emp_name,
            'category_name': cat_name,
            'project_name': proj_name,
        })

    employees = Employee.objects.filter(company_id=company_id).order_by('name')
    projects = Project.objects.order_by('client_name')
    status_options = ['pending', 'approved', 'rejected']

    return render(request, 'admin/expenses/expensereport.html', {
        'expenses': expenses,
        'employees': employees,
        'projects': projects,
        'statusOptions': status_options,
        'total_amount': total_amount,
    })
