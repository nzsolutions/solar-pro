from django.db import models


class DynamicForm(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    form_name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    project_ids = models.JSONField(default=list, blank=True)  # JSON array of project IDs
    form_schema = models.JSONField(default=dict)  # sections, rows, columns
    is_active = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'dynamic_forms'
        managed = True

    def __str__(self):
        return self.form_name


class FormSubmission(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    form_id = models.IntegerField()  # maps to dynamic_forms.id
    project_id = models.IntegerField(null=True, blank=True)
    emp_id = models.IntegerField()  # maps to employees.id
    submission_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'form_submissions'
        managed = True

    def __str__(self):
        return f"Submission #{self.id} for Form {self.form_id}"


class DynamicDashboardSectionMaster(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    section_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'dynamic_dashboard_section_master'
        managed = True

    def __str__(self):
        return self.section_name


class DashboardConfig(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    config_json = models.TextField(default='[]')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'dashboard_configs'
        managed = True

    def __str__(self):
        return f"DashboardConfig for Company {self.company_id}"
