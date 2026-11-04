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
