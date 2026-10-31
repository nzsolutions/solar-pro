from django.db import models


class Employee(models.Model):
    id = models.BigAutoField(primary_key=True)
    company_id = models.IntegerField(default=1)
    name = models.CharField(max_length=255)
    role = models.IntegerField(null=True, blank=True)  # maps to designation_master.id
    app_username = models.CharField(max_length=100, unique=True)
    app_password = models.CharField(max_length=255)
    email = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    gender = models.CharField(max_length=20, null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    pincode = models.CharField(max_length=20, null=True, blank=True)
    joining_date = models.DateField(null=True, blank=True)
    relieving_date = models.DateField(null=True, blank=True)
    documents = models.JSONField(default=list, blank=True)
    fcm_token = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, default='active')  # active / inactive
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'employees'
        managed = True

    def __str__(self):
        return f"{self.name} ({self.app_username})"


class EmployeeOTP(models.Model):
    id = models.BigAutoField(primary_key=True)
    employee_id = models.IntegerField()
    otp = models.CharField(max_length=10)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        db_table = 'employee_otps'
        managed = True

    def __str__(self):
        return f"OTP for Emp {self.employee_id}"


class EmployeeAttendance(models.Model):
    id = models.BigAutoField(primary_key=True)
    employee_id = models.IntegerField()
    punch_in = models.DateTimeField(null=True, blank=True)
    punch_out = models.DateTimeField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    actual_worked = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    @property
    def project_id(self):
        return getattr(self, '_project_id', None)

    @project_id.setter
    def project_id(self, value):
        self._project_id = value

    class Meta:
        db_table = 'emp_attendance'
        managed = True

    def __str__(self):
        return f"Attendance {self.employee_id} - {self.punch_in}"
