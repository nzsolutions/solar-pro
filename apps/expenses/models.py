from django.db import models


class ExpenseCategory(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    category_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'expenses_category_master'
        managed = True

    def __str__(self):
        return self.category_name


class Expense(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    employee_id = models.IntegerField()  # maps to employees.id
    project_id = models.IntegerField(null=True, blank=True)
    category_id = models.IntegerField()  # maps to expenses_category_master.id
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    emp_comment = models.TextField(null=True, blank=True)
    image = models.CharField(max_length=500, null=True, blank=True)
    status = models.CharField(max_length=50, default='pending')  # pending, approved, rejected
    rejection_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'expenses'
        managed = True

    def __str__(self):
        return f"Expense #{self.id} - {self.amount} ({self.status})"
