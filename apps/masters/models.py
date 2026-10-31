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
