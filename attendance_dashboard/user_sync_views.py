import json
import base64
import time
import hashlib
from datetime import timedelta
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .models import GatewayDevice, GatewaySession, DeviceSyncQueue, Employee
from .serializers import EncryptedPayloadSerializer

def decrypt_payload(serializer_data):
    """Refactored decryption logic used across gateway sync endpoints."""
    mac_address = serializer_data['mac_address']
    encrypted_data_b64 = serializer_data['encrypted_data']
    iv_b64 = serializer_data['iv']
    nonce = serializer_data['nonce']
    req_timestamp = serializer_data['timestamp']

    if abs(time.time() - req_timestamp) > 300:
        raise ValueError("Request timestamp outside allowed window.")

    device = GatewayDevice.objects.get(mac_address=mac_address, is_active=True)
    device.last_seen = timezone.now()
    device.save(update_fields=['last_seen'])

    session = GatewaySession.objects.get(gateway=device, nonce=nonce, is_used=False)
    if session.created_at < timezone.now() - timedelta(minutes=5):
        raise ValueError("Session nonce has expired.")

    api_key_str = str(device.api_key).replace('-', '')
    session_key = hashlib.pbkdf2_hmac(
        'sha256', 
        api_key_str.encode('utf-8'), 
        session.nonce.encode('utf-8'), 
        1000
    )[:32]

    iv = base64.b64decode(iv_b64)
    encrypted_data = base64.b64decode(encrypted_data_b64)

    cipher = AES.new(session_key, AES.MODE_CBC, iv)
    decrypted_padded = cipher.decrypt(encrypted_data)
    decrypted_json_str = unpad(decrypted_padded, AES.block_size).decode('utf-8')
    
    session.is_used = True
    session.save(update_fields=['is_used'])

    return device, json.loads(decrypted_json_str)


class DeviceCommandQueueView(APIView):
    """
    Endpoint for Raspberry Pi to fetch pending commands (Add/Delete Users).
    """
    def post(self, request):
        serializer = EncryptedPayloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            device, payload_data = decrypt_payload(serializer.validated_data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

        # In this specific view, the payload doesn't need to contain anything special, 
        # it's just proving identity to fetch the queue.
        # But wait, what if the Pi is also reporting success on previous commands?
        completed_commands = payload_data.get('completed_commands', [])
        for cmd_id in completed_commands:
            DeviceSyncQueue.objects.filter(id=cmd_id, gateway=device).update(
                is_processed=True, processed_at=timezone.now()
            )

        # Fetch pending commands
        pending = DeviceSyncQueue.objects.filter(gateway=device, is_processed=False)[:20]
        commands = []
        for cmd in pending:
            commands.append({
                'id': cmd.id,
                'action': cmd.action,
                'user_id': cmd.employee.biometric_id,
                'first_name': cmd.employee.first_name,
                'last_name': cmd.employee.last_name,
            })

        return Response({'status': 'success', 'commands': commands}, status=status.HTTP_200_OK)


class DeviceUserBackupView(APIView):
    """
    Endpoint for Raspberry Pi to upload a daily dump of all users enrolled on the hardware.
    """
    def post(self, request):
        serializer = EncryptedPayloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            device, payload_data = decrypt_payload(serializer.validated_data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

        users = payload_data.get('users', [])
        for user_data in users:
            user_id = str(user_data.get('user_id'))
            name = user_data.get('name', 'Unknown')

            # Create or update employee
            # In a real system, you might want a BiometricUser profile instead 
            # to avoid overwriting Email/Phone if Name differs slightly.
            employee, created = Employee.objects.get_or_create(
                biometric_id=user_id,
                defaults={'first_name': name, 'last_name': ''}
            )

        return Response({'status': 'success', 'synced': len(users)}, status=status.HTTP_200_OK)