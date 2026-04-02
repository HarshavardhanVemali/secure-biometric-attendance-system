from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import AttendanceLog, Employee, GatewayDevice
from django.utils import timezone
from datetime import timedelta

class DashboardMetricsView(APIView):
    def get(self, request):
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        total_employees = Employee.objects.count()
        total_gateways = GatewayDevice.objects.count()
        active_gateways = GatewayDevice.objects.filter(is_active=True).count()
        total_logs_today = AttendanceLog.objects.filter(timestamp__gte=today).count()
        
        # Calculate trend (logs today vs yesterday)
        yesterday = today - timedelta(days=1)
        logs_yesterday = AttendanceLog.objects.filter(timestamp__gte=yesterday, timestamp__lt=today).count()
        
        trend = 0
        if logs_yesterday > 0:
            trend = ((total_logs_today - logs_yesterday) / logs_yesterday) * 100

        data = {
            "total_employees": total_employees,
            "total_gateways": total_gateways,
            "active_gateways": active_gateways,
            "total_logs_today": total_logs_today,
            "trend_percentage": round(trend, 1)
        }
        return Response(data, status=status.HTTP_200_OK)

class RecentLogsView(APIView):
    def get(self, request):
        # Fetch the most recent 50 logs
        recent_logs = AttendanceLog.objects.select_related('employee', 'machine').order_by('-timestamp')[:50]
        data = []
        for log in recent_logs:
            emp_name = "Unknown"
            if log.employee:
                emp_name = f"{log.employee.first_name} {log.employee.last_name}".strip()
            
            data.append({
                "id": log.id,
                "biometric_user_id": log.biometric_user_id,
                "employee_name": emp_name,
                "machine_name": log.machine.name if log.machine else "Unknown",
                "timestamp": log.timestamp.isoformat(),
                "punch_type": log.punch_type,
                "verification_mode": log.verification_mode
            })
        return Response(data, status=status.HTTP_200_OK)

class GatewayStatusView(APIView):
    def get(self, request):
        gateways = GatewayDevice.objects.all().order_by('-last_seen')
        data = []
        now = timezone.now()
        
        for gw in gateways:
            # Consider a gateway "offline" if not seen in 15 minutes
            is_online = False
            if gw.last_seen and (now - gw.last_seen).total_seconds() < 900:
                is_online = True
                
            data.append({
                "id": gw.id,
                "name": gw.name,
                "mac_address": gw.mac_address,
                "is_online": is_online,
                "last_seen": gw.last_seen.isoformat() if gw.last_seen else None
            })
        return Response(data, status=status.HTTP_200_OK)
