from django.db import models


class Project(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    project_name = models.CharField(max_length=255, null=True, blank=True)
    client_name = models.CharField(max_length=255)
    site_id = models.IntegerField(null=True, blank=True)
    site_manager = models.IntegerField(null=True, blank=True)
    field_staff = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=50, default='planning')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    reporting_frequency = models.CharField(max_length=50, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    # Agreement & Billing Management
    agreement = models.CharField(max_length=10, default='No', choices=[('Yes', 'Yes'), ('No', 'No')])
    agreement_document = models.FileField(upload_to='project_agreements/', null=True, blank=True, max_length=500)
    agreement_start_date = models.DateField(null=True, blank=True)
    agreement_end_date = models.DateField(null=True, blank=True)
    billing_frequency = models.CharField(max_length=50, null=True, blank=True)
    charge_frequency = models.CharField(max_length=50, null=True, blank=True)
    bill_date = models.DateField(null=True, blank=True)
    prepaid = models.CharField(max_length=10, default='No', choices=[('Yes', 'Yes'), ('No', 'No')])
    free_period_check = models.BooleanField(default=False)
    free_period_end_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'projects'
        managed = True

    def __str__(self):
        return self.client_name


class ProjectDocument(models.Model):
    id = models.BigAutoField(primary_key=True)
    project_id = models.IntegerField()
    document_type_id = models.IntegerField(null=True, blank=True)
    file = models.CharField(max_length=500)
    name = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'project_document'
        managed = True

    def __str__(self):
        return self.name or self.file


class Lead(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    client_name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, null=True, blank=True)
    source = models.CharField(max_length=100, null=True, blank=True)
    system_size = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    assigned_to = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=50, default='new')  # new, contacted, site_visit_scheduled, proposal_sent, negotiation, won, lost
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'leads'
        managed = True

    def __str__(self):
        return f"{self.client_name} ({self.status})"


class ProjectActivity(models.Model):
    """
    Represents an activity selected from ActivityMaster for a specific Project.
    """
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
        ('completed', 'Completed'),
    ]

    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    project = models.ForeignKey(
        'operations.Project',
        on_delete=models.CASCADE,
        related_name='project_activities',
        db_column='project_id'
    )
    activity = models.ForeignKey(
        'masters.ActivityMaster',
        on_delete=models.CASCADE,
        related_name='project_assignments',
        db_column='activity_id'
    )
    form = models.ForeignKey(
        'dynamic_forms.DynamicForm',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='project_activities',
        db_column='form_id'
    )
    frequency = models.CharField(max_length=50, choices=FREQUENCY_CHOICES, default='Monthly')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    estimated_duration = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    added_by = models.CharField(max_length=100, default='Admin')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'project_activities'
        managed = True
        unique_together = ('project', 'activity')
        ordering = ['id']

    def __str__(self):
        return f"{self.project.project_name or self.project.client_name} - {self.activity.activity_title} ({self.frequency})"


class ProjectActivityInstance(models.Model):
    """
    Represents an individual scheduled occurrence for a ProjectActivity.
    """
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Unable to Complete', 'Unable to Complete'),
        ('Exception Reported', 'Exception Reported'),
        ('Under Review', 'Under Review'),
        ('Rejected', 'Rejected / Resubmission Required'),
    ]

    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    project_activity = models.ForeignKey(
        'operations.ProjectActivity',
        on_delete=models.CASCADE,
        related_name='instances',
        db_column='project_activity_id'
    )
    project = models.ForeignKey(
        'operations.Project',
        on_delete=models.CASCADE,
        related_name='activity_instances',
        db_column='project_id'
    )
    activity = models.ForeignKey(
        'masters.ActivityMaster',
        on_delete=models.CASCADE,
        related_name='instances',
        db_column='activity_id'
    )
    scheduled_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    frequency = models.CharField(max_length=50, default='Monthly')
    assigned_employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_activity_instances',
        db_column='assigned_employee_id'
    )
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='Pending')

    # Execution fields
    actual_start_time = models.DateTimeField(null=True, blank=True)
    actual_completion_time = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_activity_instances',
        db_column='submitted_by_id'
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    completion_remarks = models.TextField(blank=True, null=True)
    supervisor_remarks = models.TextField(blank=True, null=True)

    # Form submission integration
    form_submission = models.ForeignKey(
        'dynamic_forms.FormSubmission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_instance_submissions',
        db_column='form_submission_id'
    )
    submission_data = models.JSONField(default=dict, blank=True)
    validation_result = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'project_activity_instances'
        managed = True
        unique_together = ('project_activity', 'scheduled_date')
        ordering = ['scheduled_date', 'id']

    def __str__(self):
        return f"{self.activity.activity_title} on {self.scheduled_date} [{self.status}]"


class ProjectActivityPhoto(models.Model):
    """
    Photo evidence captured before, after, or during activity execution.
    """
    STAGE_CHOICES = [
        ('Before', 'Before'),
        ('After', 'After'),
        ('Intermediate', 'Intermediate'),
    ]

    id = models.BigAutoField(primary_key=True)
    instance = models.ForeignKey(
        'operations.ProjectActivityInstance',
        on_delete=models.CASCADE,
        related_name='photos',
        db_column='instance_id'
    )
    photo_stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='Before')
    photo_file = models.CharField(max_length=500)
    uploaded_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_photos',
        db_column='uploaded_by_id'
    )
    latitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    capture_timestamp = models.DateTimeField(null=True, blank=True)
    verification_status = models.CharField(max_length=30, default='Verified')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        db_table = 'project_activity_photos'
        managed = True
        ordering = ['id']

    def __str__(self):
        return f"{self.photo_stage} photo for instance #{self.instance_id}"


class ProjectActivityIssue(models.Model):
    """
    Exception / issue reporting when employee is unable to complete an activity instance.
    """
    ISSUE_CATEGORY_CHOICES = [
        ('Equipment Not Working', 'Equipment Not Working'),
        ('Material Unavailable', 'Material Unavailable'),
        ('Site Inaccessible', 'Site Inaccessible'),
        ('No Manpower Available', 'No Manpower Available'),
        ('Weather Conditions', 'Weather Conditions'),
        ('Safety Issue', 'Safety Issue'),
        ('Technical Problem', 'Technical Problem'),
        ('Other Operational Reason', 'Other Operational Reason'),
    ]

    STATUS_CHOICES = [
        ('Reported', 'Reported'),
        ('Under Review', 'Under Review'),
        ('Resolved', 'Resolved'),
        ('Rejected', 'Rejected'),
    ]

    id = models.BigAutoField(primary_key=True)
    instance = models.ForeignKey(
        'operations.ProjectActivityInstance',
        on_delete=models.CASCADE,
        related_name='issues',
        db_column='instance_id'
    )
    issue_category = models.CharField(max_length=100, choices=ISSUE_CATEGORY_CHOICES)
    short_description = models.CharField(max_length=255)
    detailed_explanation = models.TextField()
    supporting_photo = models.CharField(max_length=500, blank=True, null=True)
    reported_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reported_activity_issues',
        db_column='reported_by_id'
    )
    latitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Reported')
    admin_remarks = models.TextField(blank=True, null=True)
    action_by = models.CharField(max_length=100, blank=True, null=True)
    action_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'project_activity_issues'
        managed = True
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f"Issue #{self.id} on Instance #{self.instance_id}: {self.issue_category}"
