from django.urls import path
from apps.inventory import views

urlpatterns = [
    # Stock Dashboard
    path('admin/stock', views.stock_dashboard, name='admin_stock_dashboard'),

    # Stock Categories
    path('stock/categories', views.stock_categories_index, name='admin_stock_categories_index'),
    path('stock/categories/store', views.stock_category_store, name='admin_stock_categories_store'),
    path('stock/categories/<int:id>/update', views.stock_category_update, name='admin_stock_categories_update'),
    path('stock/categories/<int:id>/destroy', views.stock_category_destroy, name='admin_stock_categories_destroy'),

    # Opening Stock
    path('admin/stock/opening/create', views.create_opening_stock, name='admin_stock_opening_create'),
    path('admin/stock/opening/store', views.store_opening_stock, name='admin_stock_opening_store'),

    # GRN
    path('admin/stock/grn/create', views.create_grn, name='admin_grn_create'),
    path('admin/stock/grn/store', views.store_grn, name='admin_grn_store'),

    # Assign Stock
    path('admin/stock/assign', views.assign_stock_index, name='admin_stock_assign_index'),
    path('admin/stock/assign/store', views.store_assign_stock, name='admin_stock_assign_store'),
]
