import json
import base64
import time
import hashlib
import secrets
from datetime import datetime, timedelta
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from .models import GatewayDevice, BiometricMachine, Employee, AttendanceLog, StudentAnalytics, GatewaySession
from .serializers import EncryptedPayloadSerializer

class GatewayHandshakeView(APIView):
    """
    Initial handshake to provide a one-time nonce for the next sync operation.
    Requires hardware attestation (MAC + Hardware Serial).
    """
    def post(self, request):
        mac_address = request.data.get('mac_address')
        hardware_serial = request.data.get('hardware_serial')

        if not mac_address or not hardware_serial:
            return Response({'error': 'MAC and Hardware Serial required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            device = GatewayDevice.objects.get(mac_address=mac_address, is_active=True)
            
            # Initial provisioning: if hardware_serial is not set, set it now
            if not device.hardware_serial:
                device.hardware_serial = hardware_serial
                device.save(update_fields=['hardware_serial'])
            
            # MFA-like hardware attestation
            if device.hardware_serial != hardware_serial:
                return Response({'error': 'Hardware attestation failed. Device identity mismatch.'}, status=status.HTTP_403_FORBIDDEN)

            # Generate a 64-character hex nonce
            nonce = secrets.token_hex(32)
            GatewaySession.objects.create(gateway=device, nonce=nonce)

            return Response({
                'nonce': nonce,
                'status': 'authorized',
                'server_time': time.time()
            }, status=status.HTTP_200_OK)

        except GatewayDevice.DoesNotExist:
            return Response({'error': 'Unauthorized gateway.'}, status=status.HTTP_401_UNAUTHORIZED)


class SecureSyncView(APIView):
    """
    Endpoint for Raspberry Pi Gateways to sync their buffered logs.
    Expects a payload with AES encrypted attendance data.
    """
    MAX_TIMESTAMP_DIFF = 300 

    def post(self, request, *args, **kwargs):
        serializer = EncryptedPayloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        mac_address = serializer.validated_data['mac_address']
        encrypted_data_b64 = serializer.validated_data['encrypted_data']
        iv_b64 = serializer.validated_data['iv']
        nonce = serializer.validated_data['nonce']
        req_timestamp = serializer.validated_data['timestamp']

        # 1. Anti-Replay Check
        current_time = time.time()
        if abs(current_time - req_timestamp) > self.MAX_TIMESTAMP_DIFF:
            return Response({'error': 'Request timestamp is outside the allowed window (Replay mitigation)'}, status=status.HTTP_403_FORBIDDEN)

        # 2. Retrieve Authenticated Gateway Device
        try:
            device = GatewayDevice.objects.get(mac_address=mac_address, is_active=True)
            device.last_seen = timezone.now()
            device.save(update_fields=['last_seen'])
        except GatewayDevice.DoesNotExist:
            return Response({'error': 'Unauthorized or inactive gateway device.'}, status=status.HTTP_401_UNAUTHORIZED)

        # 3. Session & Nonce Validation
        try:
            # Validate the specific nonce provided by the client
            session = GatewaySession.objects.get(
                gateway=device, 
                nonce=nonce,
                is_used=False
            )
            # Check 5-minute validity window
            if session.created_at < timezone.now() - timedelta(minutes=5):
                 return Response({'error': 'Session nonce has expired.'}, status=status.HTTP_401_UNAUTHORIZED)
        except GatewaySession.DoesNotExist:
            return Response({'error': 'Invalid or already used session nonce.'}, status=status.HTTP_401_UNAUTHORIZED)

        # 4. Decrypt the Payload using Dynamic Session Key
        # Session Key = PBKDF2(API_KEY, Nonce)
        api_key_str = str(device.api_key).replace('-', '')
        session_key = hashlib.pbkdf2_hmac(
            'sha256', 
            api_key_str.encode('utf-8'), 
            session.nonce.encode('utf-8'), 
            600000
        )[:32]
        
        try:
            iv = base64.b64decode(iv_b64)
            encrypted_data = base64.b64decode(encrypted_data_b64)

            cipher = AES.new(session_key, AES.MODE_CBC, iv)
            decrypted_padded = cipher.decrypt(encrypted_data)
            decrypted_json_bytes = unpad(decrypted_padded, AES.block_size)
            decrypted_json_str = decrypted_json_bytes.decode('utf-8')
            
            payload_data = json.loads(decrypted_json_str)

            # Mark session as used ONLY IF decryption succeeds
            session.is_used = True
            session.save(update_fields=['is_used'])
        except Exception as e:
            return Response({'error': f'Decryption failed: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Process the Attendance Logs
        logs_processed = 0
        logs_ignored_duplicates = 0
        new_records = []
        affected_employee_ids = set()

        for log_entry in payload_data.get('logs', []):
            try:
                emp_id = log_entry['user_id']
                log_time_str = log_entry['timestamp']
                machine_ip = log_entry['machine_ip']
                
                machine = BiometricMachine.objects.filter(gateway=device, ip_address=machine_ip).first()
                if not machine:
                    machine = BiometricMachine.objects.create(name=f"Unknown-{machine_ip}", gateway=device, ip_address=machine_ip)

                log_datetime = datetime.fromisoformat(log_time_str)
                if timezone.is_naive(log_datetime):
                    log_datetime = timezone.make_aware(log_datetime)

                employee = Employee.objects.filter(biometric_id=emp_id).first()

                _, created = AttendanceLog.objects.get_or_create(
                    biometric_user_id=emp_id,
                    machine=machine,
                    timestamp=log_datetime,
                    defaults={
                        'employee': employee,
                        'punch_type': log_entry.get('punch_type', 'Unknown'),
                        'verification_mode': log_entry.get('verification', 0)
                    }
                )

                if created:
                    logs_processed += 1
                    new_records.append({
                        "emp_id": emp_id,
                        "timestamp": log_time_str,
                        "type": log_entry.get('punch_type', 'Unknown')
                    })
                    if employee:
                        affected_employee_ids.add(employee.id)
                else:
                    logs_ignored_duplicates += 1

            except Exception as e:
                print(f"Error processing log: {e}")
                pass

        # 5. Trigger AI Analytics Recalculation (Celery Background Task)
        if logs_processed > 0:
            from .tasks import process_post_sync_analytics
            
            # Send to Celery instead of manual threading
            process_post_sync_analytics.delay(
                device_id=device.id,
                payload={
                    "event": "new_attendance_batch",
                    "gateway_name": device.name,
                    "gateway_mac": device.mac_address,
                    "total_new_logs": logs_processed,
                    "logs": new_records
                },
                affected_employee_ids=list(affected_employee_ids)
            )

        return Response({
            'status': 'success',
            'logs_processed': logs_processed,
            'logs_ignored_duplicates': logs_ignored_duplicates,
            'server_time': current_time
        }, status=status.HTTP_200_OK)
def index(request):
    analytics = StudentAnalytics.objects.select_related('employee').all()
    
    # Prepare data for Chart.js
    labels = [f"{a.employee.first_name} {a.employee.last_name}" for a in analytics]
    scores = [a.success_score for a in analytics]
    risk_levels = [a.risk_level for a in analytics]
    
    # Count risks for pie chart
    risk_counts = {
        'LOW': sum(1 for r in risk_levels if r == 'LOW'),
        'MEDIUM': sum(1 for r in risk_levels if r == 'MEDIUM'),
        'HIGH': sum(1 for r in risk_levels if r == 'HIGH'),
    }

    context = {
        'analytics_data': analytics,
        'labels': labels,
        'scores': scores,
        'risk_counts': [risk_counts['LOW'], risk_counts['MEDIUM'], risk_counts['HIGH']],
    }
    return render(request, 'biometric_simulation_report.html', context)

def dashboard_stats(request):
    analytics = StudentAnalytics.objects.select_related('employee').all()
    labels = [f"{a.employee.first_name} {a.employee.last_name}" for a in analytics]
    scores = [a.success_score for a in analytics]
    risk_levels = [a.risk_level for a in analytics]
    
    risk_counts = {
        'LOW': sum(1 for r in risk_levels if r == 'LOW'),
        'MEDIUM': sum(1 for r in risk_levels if r == 'MEDIUM'),
        'HIGH': sum(1 for r in risk_levels if r == 'HIGH'),
    }

    return JsonResponse({
        'labels': labels,
        'scores': scores,
        'risk_counts': [risk_counts['LOW'], risk_counts['MEDIUM'], risk_counts['HIGH']],
    })
