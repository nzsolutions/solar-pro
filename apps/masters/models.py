from django.db import models


class DepartmentMaster(models.Model):
    id = models.BigAutoField(primary_key=True)
    department_name = models.CharField(max_length=255)
    company_id = models.IntegerField(default=1)
    added_by = models.CharField(max_length=100, default='Admin')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'department_master'
        managed = True

    def __str__(self):
        return self.department_name


class DesignationMaster(models.Model):
    id = models.BigAutoField(primary_key=True)
    designation_name = models.CharField(max_length=255)
    department_id = models.IntegerField(null=True, blank=True)
    company_id = models.IntegerField(default=1)
    added_by = models.CharField(max_length=100, default='Admin')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'designation_master'
        managed = True

    def __str__(self):
        return self.designation_name


class DocumentTypeMaster(models.Model):
    id = models.BigAutoField(primary_key=True)
    type_name = models.CharField(max_length=255)
    status = models.CharField(max_length=50, default='active')
    company_id = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'document_master'
        managed = True

    def __str__(self):
        return self.type_name


class SiteMaster(models.Model):
    id = models.BigAutoField(primary_key=True)
    site_name = models.CharField(max_length=255)
    site_address = models.TextField(null=True, blank=True)
    contact_number = models.CharField(max_length=50, null=True, blank=True)
    latitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    radius = models.DecimalField(max_digits=8, decimal_places=2, default=500.00)
    company_id = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'site_master'
        managed = True

    def __str__(self):
        return self.site_name


class AttendanceMaster(models.Model):
    id = models.BigAutoField(primary_key=True)
    working_hours = models.CharField(max_length=50)
    required_working_hours = models.CharField(max_length=50, null=True, blank=True)
    latitude = models.DecimalField(max_digits=11, decimal_places=8)
    longitude = models.DecimalField(max_digits=11, decimal_places=8)
    company_id = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'attendance_master'
        managed = True

    def __str__(self):
        return f"Working Hours: {self.working_hours}"


class SMTPConfiguration(models.Model):
    id = models.BigAutoField(primary_key=True)
    config_name = models.CharField(max_length=255, null=True, blank=True)
    smtp_host = models.CharField(max_length=255)
    smtp_port = models.IntegerField(default=587)
    smtp_user = models.CharField(max_length=255)
    smtp_pass = models.CharField(max_length=255)
    smtp_crypto = models.CharField(max_length=50, default='tls')
    from_email = models.CharField(max_length=255)
    from_name = models.CharField(max_length=255)
    is_default = models.IntegerField(default=1)
    company_id = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'SMTP_Configuration'
        managed = True

    def __str__(self):
        return self.config_name or self.smtp_host


class AccessControl(models.Model):
    id = models.BigAutoField(primary_key=True)
    role_id = models.IntegerField()  # maps to designation_master.id
    menu_key = models.CharField(max_length=100)
    permissions = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'access_controls'
        managed = True

    def __str__(self):
        return f"Role {self.role_id} - {self.menu_key}"



class ActivityMaster(models.Model):
    CATEGORY_CHOICES = [
        ('Maintenance', 'Maintenance'),
        ('Inspection', 'Inspection'),
        ('Cleaning', 'Cleaning'),
        ('Electrical', 'Electrical'),
        ('Safety', 'Safety'),
        ('Other', 'Other'),
    ]

    FREQUENCY_CHOICES = [
        ('Daily', 'Daily'),
        ('Weekly', 'Weekly'),
        ('Monthly', 'Monthly'),
        ('Quarterly', 'Quarterly'),
        ('Half-Yearly', 'Half-Yearly'),
        ('Yearly', 'Yearly'),
        ('As Required', 'As Required'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    id = models.BigAutoField(primary_key=True)
    activity_title = models.CharField(max_length=255, unique=True)
    activity_category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, default='Maintenance')
    description = models.TextField(blank=True, null=True)
    default_frequency = models.CharField(max_length=50, choices=FREQUENCY_CHOICES, default='Monthly')
    estimated_duration = models.CharField(max_length=100, blank=True, null=True)
    form = models.ForeignKey(
        'dynamic_forms.DynamicForm',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_masters',
        db_column='form_id'
    )
    photo_required = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    company_id = models.IntegerField(default=1)
    added_by = models.CharField(max_length=100, default='Admin')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'activity_master'
        managed = True
        ordering = ['-id']

    def __str__(self):
        return self.activity_title
