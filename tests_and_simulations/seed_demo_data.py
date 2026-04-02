import os
import django
import random
from datetime import timedelta
from django.utils import timezone

import sys
# Setup Django environment
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from attendance_dashboard.models import Employee, AttendanceLog, BiometricMachine, GatewayDevice # noqa: E402
from attendance_dashboard.analytics_engine import calculate_performance_score # noqa: E402

def seed_data():
    print("Seed started... Cleaning existing data...")
    AttendanceLog.objects.all().delete()
    Employee.objects.all().delete()
    
    # 1. Ensure a Gateway and Machine exists
    gateway, _ = GatewayDevice.objects.get_or_create(
        mac_address=os.getenv("GATEWAY_MAC", "00:00:00:00:00:00"),
        defaults={'name': 'Main Office Gateway'}
    )
    machine, _ = BiometricMachine.objects.get_or_create(
        ip_address=os.getenv("BIOMETRIC_MACHINE_IP", "127.0.0.1"),
        gateway=gateway,
        defaults={'name': 'Main Entrance'}
    )

    # 2. Create Employees with different patterns
    employees_data = [
        {"id": "1001", "first": "John", "last": "Doe", "type": "punctual"},
        {"id": "1002", "first": "Jane", "last": "Smith", "type": "late"},
        {"id": "1003", "first": "Alex", "last": "Johnson", "type": "irregular"},
        {"id": "1004", "first": "Maya", "last": "Williams", "type": "punctual"},
        {"id": "1005", "first": "Chris", "last": "Brown", "type": "absentee"},
    ]

    print(f"Creating {len(employees_data)} employees and 30 days of history...")
    
    now = timezone.now()
    
    for data in employees_data:
        emp = Employee.objects.create(
            biometric_id=data["id"],
            first_name=data["first"],
            last_name=data["last"],
            department="Engineering"
        )
        
        # Generate 30 days of logs
        for i in range(30):
            current_date = now - timedelta(days=i)
            # Skip weekends (simplified)
            if current_date.weekday() >= 5:
                continue
                
            # Randomize behavior based on type
            skip_day = False
            punch_time_offset = 0 # minutes after 9:00
            
            if data["type"] == "punctual":
                punch_time_offset = random.randint(-15, 4) # 8:45 to 9:04
            elif data["type"] == "late":
                punch_time_offset = random.randint(6, 20) # 9:06 to 9:20
            elif data["type"] == "irregular":
                if random.random() < 0.3: 
                    skip_day = True
                punch_time_offset = random.randint(-10, 30)
            elif data["type"] == "absentee":
                if random.random() < 0.6: 
                    skip_day = True
                punch_time_offset = random.randint(10, 60)

            if not skip_day:
                punch_datetime = current_date.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(minutes=punch_time_offset)
                AttendanceLog.objects.create(
                    employee=emp,
                    biometric_user_id=emp.biometric_id,
                    machine=machine,
                    timestamp=punch_datetime,
                    punch_type="Check-in"
                )
        
        # Trigger Analytics
        calculate_performance_score(emp)
        print(f"Created data for {emp.first_name} - Score: {emp.analytics.success_score}")

    print("Seeding complete! Admin dashboard is now populated.")

if __name__ == "__main__":
    seed_data()
