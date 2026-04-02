from celery import shared_task
from django.core.management import call_command
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule, ClockedSchedule, SolarSchedule
import logging
import json
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task(name="attendance_dashboard.tasks.sync_alert_schedule")
def sync_alert_schedule():
    """
    Synchronizes the AlertSettings.alert_time with the Celery Beat PeriodicTask.
    """
    from .models import AlertSettings
    settings = AlertSettings.objects.first()
    if not settings:
        return "No AlertSettings found"

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=settings.alert_time.minute,
        hour=settings.alert_time.hour,
        day_of_week='*',
        day_of_month='*',
        month_of_year='*',
    )

    task, created = PeriodicTask.objects.update_or_create(
        name='Daily Morning Safety Check',
        defaults={
            'crontab': schedule,
            'task': 'attendance_dashboard.tasks.run_daily_safety_check',
            'enabled': settings.is_enabled,
            'description': f'Triggered daily at {settings.alert_time}'
        }
    )
    
    status = "created" if created else "updated"
    logger.info(f"Celery Beat schedule {status} for {settings.alert_time}")
    return f"Schedule {status} (Enabled: {settings.is_enabled})"

@shared_task(name="attendance_dashboard.tasks.run_daily_safety_check")
def run_daily_safety_check():
    """
    Celery task to trigger the morning safety check (Absence Analysis).
    Scheduled via Crontab to run every day at 9:30 AM.
    """
    logger.info("Starting Daily Safety Check task...")
    try:
        call_command('daily_safety_check')
        logger.info("Daily Safety Check task completed successfully.")
    except Exception as e:
        logger.error(f"Error in Daily Safety Check task: {e}")
        raise e


# =====================================================================
# SAMPLE CASE 1: INTERVAL SCHEDULE
# Syncs biometric attendance logs every 5 minutes throughout the day.
# =====================================================================

@shared_task(name="attendance_dashboard.tasks.sync_biometric_logs")
def sync_biometric_logs():
    """
    INTERVAL TASK: Runs every 5 minutes.
    Recalculates AI performance scores for employees with recent new logs.
    """
    from .models import AttendanceLog, Employee
    from .analytics_engine import calculate_performance_score
    import datetime

    five_minutes_ago = timezone.now() - datetime.timedelta(minutes=5)
    recent_employee_ids = AttendanceLog.objects.filter(
        created_at__gte=five_minutes_ago
    ).values_list('employee_id', flat=True).distinct()

    count = 0
    for emp_id in recent_employee_ids:
        try:
            emp = Employee.objects.get(pk=emp_id)
            calculate_performance_score(emp)
            count += 1
        except Employee.DoesNotExist:
            pass

    logger.info(f"[INTERVAL] Recalculated AI scores for {count} employees.")
    return f"Updated {count} employee scores."

def register_interval_task():
    """
    Registers the biometric sync as an every-5-minute interval task.
    Call this once from Django shell or a data migration:
        from attendance_dashboard.tasks import register_interval_task
        register_interval_task()
    """
    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=5,
        period=IntervalSchedule.MINUTES
    )
    PeriodicTask.objects.update_or_create(
        name='Biometric Log Sync (Every 5 Min)',
        defaults={
            'interval': schedule,
            'task': 'attendance_dashboard.tasks.sync_biometric_logs',
            'enabled': True,
            'description': 'Recalculates AI scores every 5 minutes for new attendance punches.'
        }
    )
    logger.info("[INTERVAL] Biometric sync task registered.")


# =====================================================================
# SAMPLE CASE 2: CLOCKED SCHEDULE
# Fires ONCE at a specific date/time — e.g., an exam day alert.
# =====================================================================

@shared_task(name="attendance_dashboard.tasks.send_exam_day_alert")
def send_exam_day_alert():
    """
    CLOCKED TASK: Runs ONCE at a configured exam date/time.
    Sends a reminder to all parents that today is an exam day.
    """
    from .models import Employee
    from django.core.mail import send_mail
    from django.conf import settings as django_settings

    employees = Employee.objects.filter(parent_email__isnull=False).exclude(parent_email='')
    count = 0
    for emp in employees:
        try:
            send_mail(
                subject=f"Exam Day Reminder — {emp.first_name} {emp.last_name}",
                message=f"Dear Parent, today is an exam day for {emp.first_name}. Please ensure they arrive on time.",
                from_email=django_settings.AWS_SES_FROM_EMAIL,
                recipient_list=[emp.parent_email],
                fail_silently=True,
            )
            count += 1
        except Exception as e:
            logger.error(f"Failed to send exam alert to {emp.parent_email}: {e}")

    logger.info(f"[CLOCKED] Sent exam day alerts to {count} parents.")
    return f"Sent {count} exam day alerts."

def register_clocked_task(run_at_datetime):
    """
    Registers a one-time exam day alert at a specific datetime.

    Usage (Django shell):
        import datetime
        from django.utils import timezone
        from attendance_dashboard.tasks import register_clocked_task
        exam_time = timezone.make_aware(datetime.datetime(2026, 3, 15, 7, 30))
        register_clocked_task(exam_time)
    """
    clocked, _ = ClockedSchedule.objects.get_or_create(clocked_time=run_at_datetime)
    PeriodicTask.objects.update_or_create(
        name='Exam Day Alert (One-Time)',
        defaults={
            'clocked': clocked,
            'task': 'attendance_dashboard.tasks.send_exam_day_alert',
            'one_off': True,   # Fires ONCE then auto-disables
            'enabled': True,
            'description': f'One-time exam day reminder for {run_at_datetime}'
        }
    )
    logger.info(f"[CLOCKED] Exam day task registered for {run_at_datetime}.")


# =====================================================================
# SAMPLE CASE 3: SOLAR EVENT SCHEDULE
# Triggers at SUNSET daily based on campus GPS coordinates.
# Campus: Hyderabad, India (17.3850° N, 78.4867° E)
# =====================================================================

@shared_task(name="attendance_dashboard.tasks.evening_security_lockdown")
def evening_security_lockdown():
    """
    SOLAR TASK: Runs at SUNSET every day.
    Flags employees who checked in today but never checked out (still on campus).
    """
    from .models import AttendanceLog

    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    checked_in_ids = set(AttendanceLog.objects.filter(
        timestamp__gte=today, punch_type="Check-in"
    ).values_list('employee_id', flat=True))

    checked_out_ids = set(AttendanceLog.objects.filter(
        timestamp__gte=today, punch_type="Check-out"
    ).values_list('employee_id', flat=True))

    still_on_campus = checked_in_ids - checked_out_ids
    logger.warning(f"[SOLAR] {len(still_on_campus)} employee(s) still on campus after sunset!")
    return f"{len(still_on_campus)} employees still on campus at sunset."

def register_solar_task():
    """
    Registers the security lockdown to fire at sunset every day.
    Campus GPS: Hyderabad (17.3850° N, 78.4867° E)

    Usage (Django shell):
        from attendance_dashboard.tasks import register_solar_task
        register_solar_task()
    """
    solar, _ = SolarSchedule.objects.get_or_create(
        event='sunset',
        latitude=17.3850,
        longitude=78.4867,
    )
    PeriodicTask.objects.update_or_create(
        name='Evening Campus Security (Sunset)',
        defaults={
            'solar': solar,
            'task': 'attendance_dashboard.tasks.evening_security_lockdown',
            'enabled': True,
            'description': 'Fires at sunset daily; detects employees still on campus.'
        }
    )
    logger.info("[SOLAR] Evening security lockdown task registered.")

@shared_task(name="attendance_dashboard.tasks.process_post_sync_analytics")
def process_post_sync_analytics(device_id, payload, affected_employee_ids):
    """
    Background task to recalculate AI analytics after a successful gateway sync.
    Triggered via Celery after each batch of attendance logs is processed.
    """
    from .models import Employee
    from .analytics_engine import calculate_performance_score
    
    logger.info(f"Processing post-sync analytics for Gateway ID {device_id}...")
    
    count = 0
    for emp_id in affected_employee_ids:
        try:
            emp = Employee.objects.get(pk=emp_id)
            calculate_performance_score(emp)
            count += 1
        except Employee.DoesNotExist:
            logger.warning(f"Employee ID {emp_id} not found during analytics recalc.")
            
    logger.info(f"Completed post-sync analytics: {count} AI scores updated.")
    return f"Processed {count} employees."
