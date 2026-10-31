import re
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from apps.authentication.decorators import admin_required
from apps.inventory.models import StockCategory, OpeningStock, AssignedStock
from apps.operations.models import Project


def indian_number(num):
    try:
        val = int(round(float(num)))
    except (ValueError, TypeError):
        return "0"
    is_neg = val < 0
    s = str(abs(val))
    if len(s) > 3:
        last3 = s[-3:]
        rest = s[:-3]
        rest = re.sub(r'\B(?=(\d{2})+(?!\d))', ',', rest)
        res = rest + ',' + last3
    else:
        res = s
    return ('-' if is_neg else '') + res


def indian_lakh(num):
    try:
        val = float(num) / 100000.0
        return f"{val:.1f}L"
    except (ValueError, TypeError):
        return "0.0L"


# ==========================================
# 1. STOCK DASHBOARD
# ==========================================
@admin_required
def stock_dashboard(request):
    search = request.GET.get('search', '').strip().lower()

    categories_map = {c.id: c.category_name for c in StockCategory.objects.all()}
    projects_map = {p.id: p.client_name for p in Project.objects.all()}

    # Group assigned stock by item_id & project_id
    assigned_qs = AssignedStock.objects.all()
    assigned_by_item = {}
    for ast in assigned_qs:
        item_id = ast.item_id
        if item_id not in assigned_by_item:
            assigned_by_item[item_id] = {}
        pid = ast.project_id
        if pid not in assigned_by_item[item_id]:
            assigned_by_item[item_id][pid] = {
                'project_name': projects_map.get(pid, f'Project #{pid}'),
                'assigned_qty': 0.0,
                'used_qty': 0.0,
            }
        assigned_by_item[item_id][pid]['assigned_qty'] += float(ast.qty)
        assigned_by_item[item_id][pid]['used_qty'] += float(ast.used_qty)

    items_qs = OpeningStock.objects.all().order_by('item_name')
    inventory = []
    low_stock_count = 0
    total_stock_value = Decimal('0.00')

    for item in items_qs:
        cat_name = categories_map.get(item.category, 'General')
        if search and (search not in item.item_name.lower() and search not in cat_name.lower()):
            continue

        item_breakdown_dict = assigned_by_item.get(item.id, {})
        breakdown_list = []
        site_opening = 0.0
        site_used = 0.0

        for p_data in item_breakdown_dict.values():
            a_qty = p_data['assigned_qty']
            u_qty = p_data['used_qty']
            site_opening += a_qty
            site_used += u_qty
            breakdown_list.append({
                'project_name': p_data['project_name'],
                'assigned_qty': a_qty,
                'used_qty': u_qty,
                'closing_qty': a_qty - u_qty,
            })

        site_closing = site_opening - site_used
        closing_stock = float(item.quantity)
        overall_opening = closing_stock + site_opening
        val = closing_stock * float(item.rate)
        total_stock_value += Decimal(str(val))

        is_low = closing_stock <= float(item.low_stock_threshold)
        if is_low:
            low_stock_count += 1

        inventory.append({
            'id': item.id,
            'name': item.item_name,
            'category': cat_name,
            'unit': item.unit,
            'rate': float(item.rate),
            'opening_stock': overall_opening,
            'closing_stock': closing_stock,
            'site_opening_stock': site_opening,
            'site_closing_stock': site_closing,
            'site_breakdown': breakdown_list,
            'value': val,
            'status': 'Low' if is_low else 'Sufficient',
            'opening_formatted': indian_number(overall_opening),
            'closing_formatted': indian_number(closing_stock),
            'site_opening_formatted': indian_number(site_opening),
            'site_closing_formatted': indian_number(site_closing),
        })

    data = {
        'total_items': len(inventory),
        'low_stock_alerts': low_stock_count,
        'stock_value': total_stock_value,
        'stock_value_formatted': indian_lakh(total_stock_value),
    }

    return render(request, 'admin/stock/stockdashboard.html', {
        'data': data,
        'inventory': inventory,
    })


# ==========================================
# 2. STOCK CATEGORIES CRUD
# ==========================================
@admin_required
def stock_categories_index(request):
    categories = StockCategory.objects.order_by('-created_at')
    return render(request, 'admin/stock/stockcategorymaster.html', {
        'categories': categories,
    })


@admin_required
def stock_category_store(request):
    if request.method == 'POST':
        name = request.POST.get('category_name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
            return redirect('admin_stock_categories_index')

        if StockCategory.objects.filter(category_name__iexact=name).exists():
            messages.error(request, f'Category "{name}" already exists.')
            return redirect('admin_stock_categories_index')

        StockCategory.objects.create(
            category_name=name,
            added_by=request.session.get('user_name', 'Admin'),
            company_id=request.session.get('company_id', 1),
        )
        messages.success(request, 'Category added successfully.')
    return redirect('admin_stock_categories_index')


@admin_required
def stock_category_update(request, id):
    category = get_object_or_404(StockCategory, id=id)
    if request.method == 'POST':
        name = request.POST.get('category_name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
            return redirect('admin_stock_categories_index')

        if StockCategory.objects.filter(category_name__iexact=name).exclude(id=id).exists():
            messages.error(request, f'Category "{name}" already exists.')
            return redirect('admin_stock_categories_index')

        category.category_name = name
        category.save()
        messages.success(request, 'Category updated successfully.')
    return redirect('admin_stock_categories_index')


@admin_required
def stock_category_destroy(request, id):
    category = get_object_or_404(StockCategory, id=id)
    category.delete()
    messages.success(request, 'Category deleted successfully.')
    return redirect('admin_stock_categories_index')


# ==========================================
# 3. OPENING STOCK
# ==========================================
@admin_required
def create_opening_stock(request):
    categories = StockCategory.objects.order_by('category_name')
    return render(request, 'admin/stock/openingstock.html', {
        'categories': categories,
    })


@admin_required
def store_opening_stock(request):
    if request.method == 'POST':
        item_name = request.POST.get('item_name', '').strip()
        category_id = request.POST.get('category_id')
        unit = request.POST.get('unit', '').strip()
        quantity = request.POST.get('quantity', 0)
        rate = request.POST.get('rate', 0)
        low_stock_threshold = request.POST.get('low_stock_threshold', 10)

        if not item_name or not category_id:
            messages.error(request, 'Item name and category are required.')
            return redirect('admin_stock_opening_create')

        OpeningStock.objects.create(
            company_id=request.session.get('company_id', 1),
            item_name=item_name,
            category=int(category_id),
            unit=unit,
            quantity=Decimal(str(quantity)),
            rate=Decimal(str(rate)),
            low_stock_threshold=Decimal(str(low_stock_threshold)),
        )

        messages.success(request, f'Opening stock for "{item_name}" was added successfully.')
        return redirect('admin_stock_dashboard')
    return redirect('admin_stock_opening_create')


# ==========================================
# 4. GOODS RECEIPT NOTE (GRN)
# ==========================================
@admin_required
def create_grn(request):
    next_grn_number = 'GRN-2026-001'
    vendors = ['Tata Power Solar', 'Adani Solar', 'SolarEdge Distributors', 'Fronius India', 'Polycab Cables']
    stock_items = OpeningStock.objects.order_by('item_name')

    return render(request, 'admin/stock/addgrn.html', {
        'nextGrnNumber': next_grn_number,
        'vendors': vendors,
        'stockItems': stock_items,
    })


@admin_required
def store_grn(request):
    if request.method == 'POST':
        grn_number = request.POST.get('grn_number', 'GRN-001')
        vendor_name = request.POST.get('vendor_name')
        received_by = request.POST.get('received_by')

        # Items are passed as items[0][item_id], items[0][qty], items[0][rate]
        idx = 0
        while True:
            item_id = request.POST.get(f'items[{idx}][item_id]')
            if not item_id:
                break
            qty = Decimal(request.POST.get(f'items[{idx}][qty]', 0))
            if qty > 0:
                item = OpeningStock.objects.filter(id=int(item_id)).first()
                if item:
                    item.quantity += qty
                    item.save()
            idx += 1

        messages.success(request, f'GRN "{grn_number}" was saved successfully.')
        return redirect('admin_stock_dashboard')
    return redirect('admin_grn_create')


# ==========================================
# 5. ASSIGN STOCK
# ==========================================
@admin_required
def assign_stock_index(request):
    assigned_stock_qs = AssignedStock.objects.order_by('-created_at')

    categories_map = {c.id: c.category_name for c in StockCategory.objects.all()}
    items_map = {i.id: i for i in OpeningStock.objects.all()}
    projects_map = {p.id: p.client_name for p in Project.objects.all()}

    assigned_stock = []
    for ast in assigned_stock_qs:
        item = items_map.get(ast.item_id)
        cat_name = categories_map.get(item.category, '—') if item else '—'
        assigned_stock.append({
            'id': ast.id,
            'project_name': projects_map.get(ast.project_id, '—'),
            'category_name': cat_name,
            'item_name': item.item_name if item else '—',
            'qty': ast.qty,
            'unit': item.unit if item else 'Nos',
            'created_at': ast.created_at,
        })

    categories = StockCategory.objects.order_by('category_name')
    items = [{
        'id': i.id,
        'item_name': i.item_name,
        'category_id': i.category,
        'unit': i.unit,
        'quantity': float(i.quantity),
    } for i in OpeningStock.objects.order_by('item_name')]

    projects = Project.objects.order_by('client_name')

    return render(request, 'admin/stock/assignstock.html', {
        'assignedStock': assigned_stock,
        'categories': categories,
        'items': items,
        'projects': projects,
    })


@admin_required
def store_assign_stock(request):
    if request.method == 'POST':
        project_id = request.POST.get('project_id')
        item_id = request.POST.get('item_id')
        qty = Decimal(request.POST.get('qty', 0))

        if not project_id or not item_id or qty <= 0:
            messages.error(request, 'Please provide valid project, item, and quantity.')
            return redirect('admin_stock_assign_index')

        with transaction.atomic():
            item = OpeningStock.objects.select_for_update().filter(id=int(item_id)).first()
            if not item or qty > item.quantity:
                avail = item.quantity if item else 0
                unit = item.unit if item else ''
                messages.error(request, f'Cannot assign more than available stock ({avail} {unit} available).')
                return redirect('admin_stock_assign_index')

            AssignedStock.objects.create(
                project_id=int(project_id),
                item_id=int(item_id),
                qty=qty,
            )

            item.quantity -= qty
            item.save()

        messages.success(request, 'Stock assigned successfully.')
        return redirect('admin_stock_assign_index')
    return redirect('admin_stock_assign_index')
