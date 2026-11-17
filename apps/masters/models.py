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


class ActivityFormConfiguration(models.Model):
    """
    Root configuration entity for an activity's dynamic form.
    Links 1:1 with an ActivityMaster record.
    """
    id = models.BigAutoField(primary_key=True)
    activity = models.OneToOneField(
        'masters.ActivityMaster',
        on_delete=models.CASCADE,
        related_name='form_configuration',
        db_column='activity_id'
    )
    form_title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    company_id = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'activity_form_configurations'
        managed = True
        ordering = ['id']

    def __str__(self):
        return f"Form Config: {self.form_title} ({self.activity.activity_title})"


class ActivityFormField(models.Model):
    """
    Individual form field item within an activity form configuration.
    Supports all 9 field types, ordering, requirements, and settings.
    """
    FIELD_TYPE_CHOICES = [
        ('short_text', 'Short Text'),
        ('long_text', 'Long Text'),
        ('number', 'Number'),
        ('yes_no', 'Yes/No'),
        ('dropdown', 'Dropdown'),
        ('multiple_choice', 'Multiple Choice'),
        ('date', 'Date'),
        ('time', 'Time'),
        ('photo_capture', 'Photo Capture'),
    ]

    id = models.BigAutoField(primary_key=True)
    form_config = models.ForeignKey(
        'masters.ActivityFormConfiguration',
        on_delete=models.CASCADE,
        related_name='fields',
        db_column='form_configuration_id'
    )
    field_label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=50, choices=FIELD_TYPE_CHOICES, default='short_text')
    placeholder = models.CharField(max_length=255, blank=True, null=True)
    help_text = models.TextField(blank=True, null=True)
    is_required = models.BooleanField(default=False)
    field_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'activity_form_fields'
        managed = True
        ordering = ['field_order', 'id']

    def __str__(self):
        return f"{self.field_label} ({self.get_field_type_display()})"


class ActivityFormFieldOption(models.Model):
    """
    Selectable options for dropdown and multiple-choice fields.
    """
    id = models.BigAutoField(primary_key=True)
    field = models.ForeignKey(
        'masters.ActivityFormField',
        on_delete=models.CASCADE,
        related_name='options',
        db_column='form_field_id'
    )
    option_label = models.CharField(max_length=255)
    option_value = models.CharField(max_length=255)
    display_order = models.PositiveIntegerField(default=0)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'activity_form_field_options'
        managed = True
        ordering = ['display_order', 'id']

    def __str__(self):
        return f"Option '{self.option_label}' for field #{self.field_id}"


class ActivityFormPhotoSetting(models.Model):
    """
    Photo evidence requirements for the activity execution in mobile app.
    Enforces camera-only direct capture, before/after requirements, and GPS/timestamp capture.
    """
    id = models.BigAutoField(primary_key=True)
    form_config = models.OneToOneField(
        'masters.ActivityFormConfiguration',
        on_delete=models.CASCADE,
        related_name='photo_settings',
        db_column='form_configuration_id'
    )
    enable_photo_capture = models.BooleanField(default=False)
    before_photo_required = models.BooleanField(default=False)
    after_photo_required = models.BooleanField(default=False)
    optional_photo = models.BooleanField(default=True)
    photo_instructions = models.TextField(blank=True, null=True)
    capture_timestamp_required = models.BooleanField(default=True)
    submission_timestamp_required = models.BooleanField(default=True)
    gps_coordinates_required = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'activity_form_photo_settings'
        managed = True

    def __str__(self):
        return f"Photo Settings for Form #{self.form_config_id}"


class ActivityFormValidationRule(models.Model):
    """
    Validation and business exception rule definitions.
    Distinguishes between standard validation and business exceptions.
    """
    RULE_TYPE_CHOICES = [
        ('normal', 'Normal Validation'),
        ('business_exception', 'Business Exception Validation'),
    ]

    id = models.BigAutoField(primary_key=True)
    field = models.ForeignKey(
        'masters.ActivityFormField',
        on_delete=models.CASCADE,
        related_name='validation_rules',
        db_column='form_field_id'
    )
    rule_type = models.CharField(max_length=30, choices=RULE_TYPE_CHOICES, default='normal')
    rule_name = models.CharField(max_length=100)
    condition_operator = models.CharField(max_length=50, blank=True, null=True)
    expected_value = models.CharField(max_length=255, blank=True, null=True)
    acceptable_values = models.JSONField(default=list, blank=True)
    min_value = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True)
    max_value = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True)
    error_message = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'activity_form_validation_rules'
        managed = True

    def __str__(self):
        return f"Rule '{self.rule_name}' ({self.get_rule_type_display()}) for field #{self.field_id}"


class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    LEAVE_TYPE_CHOICES = [
        ('Casual Leave', 'Casual Leave'),
        ('Sick Leave', 'Sick Leave'),
        ('Privilege Leave', 'Privilege Leave'),
        ('Maternity/Paternity Leave', 'Maternity/Paternity Leave'),
        ('Emergency Leave', 'Emergency Leave'),
        ('Compensatory Off', 'Compensatory Off'),
        ('Other', 'Other'),
    ]

    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='leave_requests',
        db_column='employee_id'
    )
    leave_type = models.CharField(max_length=100, choices=LEAVE_TYPE_CHOICES, default='Casual Leave')
    start_date = models.DateField()
    end_date = models.DateField()
    days_count = models.DecimalField(max_digits=5, decimal_places=1, default=1.0)
    reason = models.TextField()
    attachment = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, null=True)
    admin_remarks = models.TextField(blank=True, null=True)
    action_by = models.CharField(max_length=100, blank=True, null=True)
    action_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'leave_requests'
        ordering = ['-created_at', '-id']
        managed = True

    def __str__(self):
        return f"Leave #{self.id} - {self.employee.name} ({self.leave_type}: {self.start_date} to {self.end_date}) [{self.status}]"



