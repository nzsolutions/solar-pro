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
    project = models.ForeignKey(
        'operations.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leave_requests',
        db_column='project_id'
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


class ActivitySchedule(models.Model):
    """
    Scheduled maintenance or inspection activity configuration.
    Supports recurring schedules (Daily, Weekly, Monthly) and automatic task generation.
    """
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Urgent', 'Urgent'),
    ]

    RECURRING_CHOICES = [
        ('one_time', 'One-Time'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Scheduled', 'Scheduled'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    id = models.BigAutoField(primary_key=True)
    schedule_code = models.CharField(max_length=50, unique=True, blank=True)
    title = models.CharField(max_length=255)
    activity = models.ForeignKey(
        'masters.ActivityMaster',
        on_delete=models.CASCADE,
        related_name='schedules',
        db_column='activity_id'
    )
    project = models.ForeignKey(
        'operations.Project',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='activity_schedules',
        db_column='project_id'
    )
    assigned_to = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_schedules',
        db_column='assigned_to_id'
    )
    assigned_staff = models.JSONField(default=list, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    recurring_type = models.CharField(max_length=20, choices=RECURRING_CHOICES, default='one_time')
    start_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Scheduled')
    auto_generate_tasks = models.BooleanField(default=True)
    last_generated_date = models.DateField(null=True, blank=True)
    remind_upcoming = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    company_id = models.IntegerField(default=1)
    created_by = models.CharField(max_length=100, default='Admin')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'activity_schedules'
        managed = True
        ordering = ['-id']

    def __str__(self):
        return f"{self.schedule_code or self.id} - {self.title}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if not self.schedule_code:
            self.schedule_code = f"SCH-{self.id:04d}"
            ActivitySchedule.objects.filter(pk=self.pk).update(schedule_code=self.schedule_code)

    @property
    def is_overdue(self):
        import datetime
        from django.utils import timezone
        if self.status in ['Completed', 'Cancelled']:
            return False
        today = timezone.localdate()
        if self.deadline:
            dl = self.deadline
            if isinstance(dl, str):
                try:
                    dl = datetime.date.fromisoformat(dl.split('T')[0].split(' ')[0])
                except Exception:
                    dl = None
            if isinstance(dl, datetime.datetime):
                if timezone.is_naive(dl):
                    dl = timezone.make_aware(dl)
                return timezone.now() > dl
            elif isinstance(dl, datetime.date):
                return today > dl
        start = self.start_date
        if isinstance(start, str):
            try:
                start = datetime.date.fromisoformat(start.split('T')[0].split(' ')[0])
            except Exception:
                start = None
        if isinstance(start, datetime.datetime):
            start = start.date()
        if isinstance(start, datetime.date):
            return start < today
        return False

    @property
    def tasks(self):
        return self.generated_tasks


class ActivityTask(models.Model):
    """
    Concrete execution instance of an activity generated automatically
    or manually according to schedule.
    """
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Urgent', 'Urgent'),
    ]

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Scheduled', 'Scheduled'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    id = models.BigAutoField(primary_key=True)
    task_code = models.CharField(max_length=50, unique=True, blank=True)
    schedule = models.ForeignKey(
        'masters.ActivitySchedule',
        on_delete=models.CASCADE,
        related_name='generated_tasks',
        db_column='schedule_id'
    )
    activity = models.ForeignKey(
        'masters.ActivityMaster',
        on_delete=models.CASCADE,
        related_name='activity_tasks',
        db_column='activity_id'
    )
    project = models.ForeignKey(
        'operations.Project',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='activity_tasks',
        db_column='project_id'
    )
    task_title = models.CharField(max_length=255)
    task_date = models.DateField()
    due_datetime = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_activity_tasks',
        db_column='assigned_to_id'
    )
    assigned_staff = models.JSONField(default=list, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    completion_remarks = models.TextField(blank=True, null=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    company_id = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'activity_tasks'
        managed = True
        ordering = ['task_date', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['schedule', 'task_date'],
                name='unique_schedule_task_per_date'
            )
        ]

    def __str__(self):
        return f"{self.task_code or self.id} - {self.task_title} ({self.task_date})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if not self.task_code:
            dt_str = self.task_date.strftime('%Y%m%d') if self.task_date else '00000000'
            self.task_code = f"TSK-{dt_str}-{self.id:04d}"
            ActivityTask.objects.filter(pk=self.pk).update(task_code=self.task_code)

    @property
    def is_overdue(self):
        import datetime
        from django.utils import timezone
        if self.status in ['Completed', 'Cancelled']:
            return False
        today = timezone.localdate()
        if self.due_datetime:
            due_dt = self.due_datetime
            if isinstance(due_dt, str):
                try:
                    due_dt = datetime.datetime.fromisoformat(due_dt)
                except Exception:
                    due_dt = None
            if isinstance(due_dt, datetime.datetime):
                if timezone.is_naive(due_dt):
                    due_dt = timezone.make_aware(due_dt)
                return timezone.now() > due_dt
            elif isinstance(due_dt, datetime.date):
                return today > due_dt
        t_date = self.task_date
        if isinstance(t_date, str):
            try:
                t_date = datetime.date.fromisoformat(t_date.split('T')[0].split(' ')[0])
            except Exception:
                t_date = None
        if isinstance(t_date, datetime.datetime):
            t_date = t_date.date()
        if isinstance(t_date, datetime.date):
            return t_date < today
        return False


class TaskReassignmentLog(models.Model):
    """
    Audit log tracking manual task reassignments across both workflows:
    - ActivityTask (Admin Activity Scheduling)
    - ProjectActivityInstance (Operations / Mobile Activity Execution)
    """
    WORKFLOW_CHOICES = [
        ('activity_task', 'Activity Task (Scheduling)'),
        ('project_activity_instance', 'Project Activity Instance (Mobile)'),
    ]

    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    workflow_type = models.CharField(max_length=35, choices=WORKFLOW_CHOICES)
    
    activity_task = models.ForeignKey(
        'masters.ActivityTask',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reassignment_logs',
        db_column='activity_task_id'
    )
    project_activity_instance = models.ForeignKey(
        'operations.ProjectActivityInstance',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reassignment_logs',
        db_column='project_activity_instance_id'
    )
    
    project = models.ForeignKey(
        'operations.Project',
        on_delete=models.CASCADE,
        related_name='reassignment_logs',
        db_column='project_id'
    )
    
    previous_employee = models.ForeignKey(
        'employees.Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reassignments_from',
        db_column='previous_employee_id'
    )
    previous_employee_name = models.CharField(max_length=150, blank=True)
    
    new_employee = models.ForeignKey(
        'employees.Employee',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reassignments_to',
        db_column='new_employee_id'
    )
    new_employee_name = models.CharField(max_length=150, blank=True)
    
    reassigned_by = models.CharField(max_length=150)
    reassigned_at = models.DateTimeField(auto_now_add=True)
    task_date = models.DateField()
    reason = models.TextField(blank=True, null=True)
    handover_remarks = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'task_reassignment_logs'
        ordering = ['-reassigned_at']
        indexes = [
            models.Index(fields=['workflow_type', 'task_date']),
            models.Index(fields=['project', 'task_date']),
            models.Index(fields=['reassigned_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(workflow_type='activity_task', activity_task__isnull=False, project_activity_instance__isnull=True) |
                    models.Q(workflow_type='project_activity_instance', project_activity_instance__isnull=False, activity_task__isnull=True)
                ),
                name='reassignment_log_mutually_exclusive_task'
            )
        ]

    def __str__(self):
        return f"[{self.workflow_type}] {self.previous_employee_name} -> {self.new_employee_name} on {self.task_date}"




