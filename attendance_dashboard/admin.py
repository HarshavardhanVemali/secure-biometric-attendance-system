from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import GatewayDevice, BiometricMachine, Employee, AttendanceLog, StudentAnalytics, AlertSettings, NotificationLog
from django.utils.html import format_html

@admin.register(GatewayDevice)
class GatewayDeviceAdmin(ModelAdmin):
    list_display = ('name', 'mac_address', 'is_active', 'last_seen', 'api_key')
    search_fields = ('name', 'mac_address')
    list_filter = ('is_active',)
    readonly_fields = ('api_key', 'last_seen', 'created_at')

@admin.register(BiometricMachine)
class BiometricMachineAdmin(ModelAdmin):
    list_display = ('name', 'ip_address', 'gateway', 'is_active')
    search_fields = ('name', 'ip_address')
    list_filter = ('is_active', 'gateway')

@admin.register(StudentAnalytics)
class StudentAnalyticsAdmin(ModelAdmin):
    list_display = ('employee', 'success_score', 'risk_level_tag', 'last_calculated')
    readonly_fields = ('last_calculated',)
    change_form_template = 'admin/attendance_dashboard/employee/change_form.html'
    
    def risk_level_tag(self, obj):
        colors = {
            'LOW': ('#00d4aa', '#e6fff9'), # Green-ish
            'MEDIUM': ('#f0b429', '#fff9e6'), # Yellow-ish
            'HIGH': ('#ff4757', '#ffe6e6'), # Red-ish
        }
        color, bg = colors.get(obj.risk_level, ('gray', 'white'))
        return format_html(
            '<span style="color: {}; background: {}; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 10px;">{}</span>',
            color, bg, obj.risk_level
        )
    risk_level_tag.short_description = "Risk Level"

    def changelist_view(self, request, extra_context=None):
        import os
        from .models import AlertSettings
        
        extra_context = extra_context or {}
        alert_config = AlertSettings.objects.first()
        email_count = os.getenv('EMAIL_SENT_COUNT', '0')
        
        extra_context['alert_config'] = alert_config
        extra_context['email_sent_total'] = email_count
        
        return super().changelist_view(request, extra_context=extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        analytics = StudentAnalytics.objects.get(pk=object_id)
        
        # We need the employee to get attendance logs
        employee = analytics.employee
        
        # Get last 7 days of check-ins
        recent_logs = AttendanceLog.objects.filter(
            employee=employee,
            punch_type="Check-in"
        ).order_by('-timestamp')[:7]

        punch_labels = []
        punch_times = []
        
        for log in reversed(recent_logs):
            local_ts = log.timestamp
            punch_labels.append(local_ts.strftime("%b %d"))
            total_minutes = local_ts.hour * 60 + local_ts.minute
            punch_times.append(total_minutes)
            
        # Calculate Punctuality for Pie Chart (On-time <= 9:05 AM i.e., 545 mins)
        on_time_count = sum(1 for t in punch_times if t <= 545)
        late_count = len(punch_times) - on_time_count
            
        extra_context['punch_labels'] = punch_labels
        extra_context['punch_times'] = punch_times
        extra_context['on_time_count'] = on_time_count
        extra_context['late_count'] = late_count
        extra_context['success_score'] = analytics.success_score
        
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    class Media:
        js = ('https://cdn.jsdelivr.net/npm/chart.js',)

@admin.register(Employee)
class EmployeeAdmin(ModelAdmin):
    list_display = ('name_with_id', 'department', 'get_score', 'get_risk')
    search_fields = ('first_name', 'last_name', 'biometric_id', 'parent_email')
    list_filter = ('department',)
    change_form_template = 'admin/attendance_dashboard/employee/change_form.html'

    def name_with_id(self, obj):
        return f"{obj.first_name} {obj.last_name} (#{obj.biometric_id})"
    name_with_id.short_description = "Employee"

    def get_score(self, obj):
        if hasattr(obj, 'analytics'):
            return f"{obj.analytics.success_score}%"
        return "N/A"
    get_score.short_description = "Success Score"

    def get_risk(self, obj):
        if hasattr(obj, 'analytics'):
            colors = {'LOW': '#00d4aa', 'MEDIUM': '#f0b429', 'HIGH': '#ff4757'}
            color = colors.get(obj.analytics.risk_level, 'gray')
            return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.analytics.risk_level)
        return "N/A"
    get_risk.short_description = "Risk Status"

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        employee = Employee.objects.get(pk=object_id)
        
        # Get last 7 days of check-ins
        recent_logs = AttendanceLog.objects.filter(
            employee=employee,
            punch_type="Check-in"
        ).order_by('-timestamp')[:7]

        punch_labels = []
        punch_times = []
        
        for log in reversed(recent_logs):
            local_ts = log.timestamp # Assuming TZ is handled
            punch_labels.append(local_ts.strftime("%b %d"))
            # Calculate minutes after midnight
            total_minutes = local_ts.hour * 60 + local_ts.minute
            punch_times.append(total_minutes)
            
        # Calculate Punctuality for Pie Chart (On-time <= 9:05 AM i.e., 545 mins)
        on_time_count = sum(1 for t in punch_times if t <= 545)
        late_count = len(punch_times) - on_time_count
            
        extra_context['punch_labels'] = punch_labels
        extra_context['punch_times'] = punch_times
        extra_context['on_time_count'] = on_time_count
        extra_context['late_count'] = late_count
        extra_context['success_score'] = employee.analytics.success_score if hasattr(employee, 'analytics') else None
        
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    class Media:
        js = ('https://cdn.jsdelivr.net/npm/chart.js',)

@admin.register(AttendanceLog)
class AttendanceLogAdmin(ModelAdmin):
    list_display = ('biometric_user_id', 'employee', 'machine', 'timestamp', 'punch_type')
    search_fields = ('biometric_user_id', 'employee__first_name', 'employee__last_name')
    list_filter = ('machine', 'punch_type', 'timestamp')
    date_hierarchy = 'timestamp'
@admin.register(AlertSettings)
class AlertSettingsAdmin(ModelAdmin):
    list_display = ('alert_time', 'is_enabled', 'last_updated')
    
    def has_add_permission(self, request):
        # Singleton: only allow adding if no record exists
        from .models import AlertSettings
        return not AlertSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion to maintain the singleton
        return False

@admin.register(NotificationLog)
class NotificationLogAdmin(ModelAdmin):
    list_display = ('recipient_type', 'recipient_email', 'employee', 'subject', 'status', 'sent_at')
    list_filter = ('recipient_type', 'status', 'sent_at')
    search_fields = ('recipient_email', 'employee__first_name', 'employee__last_name', 'subject')
    readonly_fields = ('employee', 'recipient_email', 'recipient_type', 'subject', 'status', 'error_message', 'sent_at')
    
    def has_add_permission(self, request):
        return False
        
    def has_change_permission(self, request, obj=None):
        return False
