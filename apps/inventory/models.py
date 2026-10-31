from django.db import models


class StockCategory(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    category_name = models.CharField(max_length=255)
    added_by = models.CharField(max_length=100, default='Admin')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'stock_categories'
        managed = True

    def __str__(self):
        return self.category_name


class OpeningStock(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    item_name = models.CharField(max_length=255)
    category = models.IntegerField()  # maps to stock_categories.id
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    unit = models.CharField(max_length=50, default='Nos')
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    low_stock_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=10.00)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'opening_stock'
        managed = True

    def __str__(self):
        return f"{self.item_name} ({self.quantity} {self.unit})"


class AssignedStock(models.Model):
    id = models.BigAutoField(primary_key=True)
    project_id = models.IntegerField()
    item_id = models.IntegerField()  # maps to opening_stock.id
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    used_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    grn_number = models.CharField(max_length=100, null=True, blank=True)
    received_by = models.CharField(max_length=100, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'assigned_stock'
        managed = True

    def __str__(self):
        return f"Assigned Item {self.item_id} to Project {self.project_id}"
