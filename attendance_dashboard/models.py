from django.db import models
from django.contrib.auth.models import User
import uuid

class GatewayDevice(models.Model):
    name = models.CharField(max_length=100)
    mac_address = models.CharField(max_length=17, unique=True, help_text="MAC Address of the Raspberry Pi")
    hardware_serial = models.CharField(max_length=50, blank=True, null=True, help_text="Unique hardware ID (e.g., CPU Serial)")
    api_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.mac_address})"

class GatewaySession(models.Model):
    gateway = models.ForeignKey(GatewayDevice, on_delete=models.CASCADE, related_name='sessions')
    nonce = models.CharField(max_length=64, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session for {self.gateway.name} - {self.nonce[:8]}"

class BiometricMachine(models.Model):
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(help_text="Local IP address of the machine")
    port = models.IntegerField(default=4370)
    gateway = models.ForeignKey(GatewayDevice, on_delete=models.CASCADE, related_name='machines')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} at {self.ip_address}"

class Employee(models.Model):
    biometric_id = models.CharField(max_length=50, unique=True, help_text="ID used in the biometric machine")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True, help_text="Student email")
    parent_phone = models.CharField(max_length=15, blank=True, null=True, help_text="For automated SMS alerts")
    parent_email = models.EmailField(blank=True, null=True, help_text="For automated absence email alerts")
    faculty_email = models.EmailField(blank=True, null=True, help_text="For faculty absence alerts")
    department = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.biometric_id})"

class AttendanceLog(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_logs', null=True, blank=True)
    biometric_user_id = models.CharField(max_length=50, help_text="Raw user ID from the machine")
    machine = models.ForeignKey(BiometricMachine, on_delete=models.SET_NULL, null=True, related_name='logs')
    timestamp = models.DateTimeField(help_text="Exact time of the punch")
    punch_type = models.CharField(max_length=20, default="Unknown", help_text="Check-in, Check-out, etc.")
    verification_mode = models.IntegerField(default=0, help_text="E.g., 0=Password, 1=Fingerprint, 15=Face")
    is_synced = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('biometric_user_id', 'machine', 'timestamp')

    def __str__(self):
        return f"{self.biometric_user_id} at {self.timestamp}"

class StudentAnalytics(models.Model):
    RISK_LEVELS = (
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
    )
    
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='analytics')
    success_score = models.IntegerField(default=100, help_text="0-100 Performance Score")
    punctuality_rate = models.FloatField(default=100.0, help_text="Percentage of on-time check-ins")
    attendance_consistency = models.FloatField(default=100.0, help_text="Frequency of attendance")
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS, default='LOW')
    last_calculated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Analytics for {self.employee.first_name} - Score: {self.success_score}"

class AlertSettings(models.Model):
    alert_time = models.TimeField(default="09:30", help_text="Time to trigger the daily safety check")
    email_subject_template = models.CharField(
        max_length=255, 
        default="Absence Alert: {first_name} {last_name}",
        help_text="Available placeholders: {first_name}, {last_name}, {biometric_id}, {date}"
    )
    email_message_template = models.TextField(
        default="Dear Parent,\n\nThis is an automated alert. {first_name} {last_name} (ID: {biometric_id}) has not checked in as of {alert_time} today ({date}).\n\nPlease verify their safety.\n\nBest Regards,\nAttendance Team",
        help_text="Available placeholders: {first_name}, {last_name}, {biometric_id}, {date}, {alert_time}"
    )
    is_enabled = models.BooleanField(default=True, help_text="Enable or disable automated alerts")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Alert Configuration"
        verbose_name_plural = "Alert Configuration"

    def __str__(self):
        return f"Alert Settings (Enabled: {self.is_enabled})"

    def save(self, *args, **kwargs):
        # Singleton pattern: ensure only one record exists
        if not self.pk and AlertSettings.objects.exists():
            return
        super().save(*args, **kwargs)
        
        # Trigger Celery Beat sync
        from .tasks import sync_alert_schedule
        sync_alert_schedule.apply_async()

class NotificationLog(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    recipient_email = models.EmailField()
    recipient_type = models.CharField(max_length=50, help_text="e.g., Student, Parent, Faculty")
    subject = models.CharField(max_length=255)
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="Sent", choices=[("Sent", "Sent"), ("Failed", "Failed")])
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.recipient_type} Notification to {self.recipient_email} at {self.sent_at.strftime('%Y-%m-%d %H:%M')}"
