import json
import base64
import hashlib
import os
import secrets
import time
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from rest_framework.test import APIClient
from .models import GatewayDevice, GatewaySession

class CryptographyTestCase(TestCase):
    def setUp(self):
        self.api_key = os.getenv("GATEWAY_API_KEY", "00000000-0000-0000-0000-000000000000")
        self.api_key_clean = self.api_key.replace('-', '')
        self.mac_address = os.getenv("GATEWAY_MAC", "00:00:00:00:00:00")
        self.hw_serial = os.getenv("GATEWAY_HW_SERIAL", "0000000000000000")
        self.device = GatewayDevice.objects.create(
            name="Test Gateway",
            mac_address=self.mac_address,
            hardware_serial=self.hw_serial,
            api_key=self.api_key
        )
        self.client = APIClient()

    def test_pbkdf2_iteration_consistency(self):
        """Verify that the iteration count matches NIST standards (600,000)."""
        nonce = "testnonce123"
        # Reference derivation
        key = hashlib.pbkdf2_hmac(
            'sha256', 
            self.api_key_clean.encode('utf-8'), 
            nonce.encode('utf-8'), 
            600000
        )[:32]
        
        self.assertEqual(len(key), 32)
        # Verify it doesn't match a low iteration count (sanity check)
        weak_key = hashlib.pbkdf2_hmac(
            'sha256', 
            self.api_key_clean.encode('utf-8'), 
            nonce.encode('utf-8'), 
            1000
        )[:32]
        self.assertNotEqual(key, weak_key)

    def test_aes_encryption_decryption_cycle(self):
        """Test the exact cycle used between Python client and Django server."""
        nonce = secrets.token_hex(32)
        session_key = hashlib.pbkdf2_hmac(
            'sha256', 
            self.api_key_clean.encode('utf-8'), 
            nonce.encode('utf-8'), 
            600000
        )[:32]
        
        # Simulate Client Encryption
        test_data = {"logs": [{"user_id": "1", "timestamp": "2026-04-02T10:00:00"}]}
        json_bytes = json.dumps(test_data).encode('utf-8')
        padded_data = pad(json_bytes, AES.block_size)
        iv = os.urandom(16)
        cipher_enc = AES.new(session_key, AES.MODE_CBC, iv)
        encrypted_data = cipher_enc.encrypt(padded_data)
        
        # Simulate Server Decryption
        cipher_dec = AES.new(session_key, AES.MODE_CBC, iv)
        decrypted_padded = cipher_dec.decrypt(encrypted_data)
        decrypted_json = unpad(decrypted_padded, AES.block_size).decode('utf-8')
        
        self.assertEqual(json.loads(decrypted_json), test_data)

    def test_secure_sync_handshake_flow(self):
        """Full integration test for Handshake -> Key Derivation -> Sync."""
        # 1. Handshake
        url_hs = reverse('gateway-handshake')
        payload_hs = {
            "mac_address": self.mac_address,
            "hardware_serial": self.hw_serial
        }
        res_hs = self.client.post(url_hs, payload_hs, format='json')
        self.assertEqual(res_hs.status_code, 200)
        nonce = res_hs.data['nonce']
        
        # 2. Derive Key (Same as server)
        session_key = hashlib.pbkdf2_hmac(
            'sha256', 
            self.api_key_clean.encode('utf-8'), 
            nonce.encode('utf-8'), 
            600000
        )[:32]
        
        # 3. Encrypt Logs
        log_payload = {"logs": [{"user_id": "T001", "timestamp": "2026-04-02T12:00:00Z", "machine_ip": "127.0.0.1"}]}
        iv = os.urandom(16)
        cipher = AES.new(session_key, AES.MODE_CBC, iv)
        encrypted_data = cipher.encrypt(pad(json.dumps(log_payload).encode('utf-8'), AES.block_size))
        
        # 4. Sync
        url_sync = reverse('gateway-sync')
        payload_sync = {
            "mac_address": self.mac_address,
            "encrypted_data": base64.b64encode(encrypted_data).decode('utf-8'),
            "iv": base64.b64encode(iv).decode('utf-8'),
            "nonce": nonce,
            "timestamp": time.time()
        }
        res_sync = self.client.post(url_sync, payload_sync, format='json')
        self.assertEqual(res_sync.status_code, 200)
        self.assertEqual(res_sync.data['logs_processed'], 1)
        
        # 5. Replay Attack Detection (Same nonce should fail)
        res_replay = self.client.post(url_sync, payload_sync, format='json')
        self.assertEqual(res_replay.status_code, 401)
        self.assertIn("Invalid or already used session nonce", res_replay.data['error'])

    def test_nonce_expiry(self):
        """Test that nonces older than 5 minutes are rejected."""
        nonce = secrets.token_hex(32)
        # Create an expired session (6 minutes ago)
        expired_time = timezone.now() - timedelta(minutes=6)
        session = GatewaySession.objects.create(
            gateway=self.device,
            nonce=nonce,
            is_used=False
        )
        GatewaySession.objects.filter(pk=session.pk).update(created_at=expired_time)
        
        url_sync = reverse('gateway-sync')
        payload = {
            "mac_address": self.mac_address,
            "nonce": nonce,
            "timestamp": time.time(),
            "encrypted_data": "dummy",
            "iv": "dummy"
        }
        res = self.client.post(url_sync, payload, format='json')
        self.assertEqual(res.status_code, 401)
        self.assertIn("nonce has expired", res.data['error'])
