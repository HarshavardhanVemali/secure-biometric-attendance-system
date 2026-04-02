import json
import base64
import time
import requests
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import os

class SecureSyncClient:
    def __init__(self, server_url, gateway_mac, gateway_api_key):
        self.server_url = server_url
        self.handshake_url = server_url.replace('/sync/', '/handshake/')
        self.gateway_mac = gateway_mac
        self.gateway_api_key = gateway_api_key
        self.hardware_serial = self._get_hardware_serial()
        
    def _get_hardware_serial(self):
        """
        Extract CPU serial from Raspberry Pi.
        """
        serial = "0000000000000000"
        try:
            if os.path.exists('/proc/cpuinfo'):
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if line.startswith('Serial'):
                            serial = line.split(':')[1].strip()
            else:
                # Fallback for non-Pi environments (simulation)
                serial = f"SIM-{self.gateway_mac.replace(':', '')}"
        except Exception:
            pass
        return serial

    def perform_handshake(self):
        """
        Step 1: Get a one-time nonce from the server.
        """
        try:
            payload = {
                "mac_address": self.gateway_mac,
                "hardware_serial": self.hardware_serial
            }
            response = requests.post(self.handshake_url, json=payload, timeout=5)
            if response.status_code == 200:
                return response.json().get('nonce')
            else:
                print(f"Handshake failed [{response.status_code}]: {response.text}")
                return None
        except Exception as e:
            print(f"Handshake error: {e}")
            return None

    def derive_session_key(self, nonce):
        """
        Derive a 32-byte session key using PBKDF2(API_KEY, nonce).
        """
        api_key_str = self.gateway_api_key.replace('-', '')
        return hashlib.pbkdf2_hmac(
            'sha256',
            api_key_str.encode('utf-8'),
            nonce.encode('utf-8'),
            600000
        )[:32]

    def encrypt_payload(self, records, session_key, nonce):
        """
        Encrypt the attendance records using AES-256 CBC.
        Returns the iv, nonce, timestamp, and base64 encoded payload.
        """
        try:
            # Prepare payload
            payload_dict = {
                "logs": records
            }
            json_str = json.dumps(payload_dict)
            json_bytes = json_str.encode('utf-8')
            padded_data = pad(json_bytes, AES.block_size)
            
            # Generate random Initialization Vector
            iv = os.urandom(16)
            cipher = AES.new(session_key, AES.MODE_CBC, iv)
            encrypted_data = cipher.encrypt(padded_data)
            
            # Encode for transmission
            iv_b64 = base64.b64encode(iv).decode('utf-8')
            encrypted_b64 = base64.b64encode(encrypted_data).decode('utf-8')
            
            # Add anti-replay timestamp
            req_timestamp = time.time()
            
            return {
                "mac_address": self.gateway_mac,
                "encrypted_data": encrypted_b64,
                "iv": iv_b64,
                "nonce": nonce,
                "timestamp": req_timestamp
            }
        except Exception as e:
            print(f"Encryption error: {e}")
            return None

    def sync_to_cloud(self, records):
        """
        Takes a list of raw records, encrypts them, and sends to the Django server.
        """
        if not records:
            return False, 0

        # MFA Handshake
        nonce = self.perform_handshake()
        if not nonce:
            return False, 0
            
        session_key = self.derive_session_key(nonce)
            
        encrypted_payload = self.encrypt_payload(records, session_key, nonce)
        if not encrypted_payload:
            return False, 0
            
        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                self.server_url, 
                json=encrypted_payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                resp_data = response.json()
                print(f"Sync successful: {resp_data}")
                return True, resp_data.get('logs_processed', 0)
            else:
                print(f"Server rejected sync [{response.status_code}]: {response.text}")
                return False, 0
                
        except requests.exceptions.RequestException as e:
            print(f"Network error during sync: {e}")
            return False, 0
