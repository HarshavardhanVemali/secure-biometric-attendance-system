import requests
import json
import time
import hashlib
import base64
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from datetime import datetime

# --- Configuration ---
from dotenv import load_dotenv
load_dotenv()

SERVER_URL = os.getenv("TEST_SERVER_URL", "http://localhost:8000")
MAC_ADDRESS = os.getenv("GATEWAY_MAC", "00:00:00:00:00:00")
API_KEY = os.getenv("GATEWAY_API_KEY", "00000000-0000-0000-0000-000000000000")
HW_SERIAL = os.getenv("GATEWAY_HW_SERIAL", "0000000000000000")

def print_result(case_name, response):
    status = "[PASS] (Rejected)" if response.status_code in [401, 403] else "[FAIL] (Accepted or Other Error)"
    if response.status_code == 200:
        status = "[PASS] (Accepted)" if "SUCCESS" in case_name else "[FAIL] (Accepted Invalid Request)"
    
    print(f"[{case_name}]")
    print(f"  Status Code: {response.status_code}")
    print(f"  Response: {response.json()}")
    print(f"  Verdict: {status}\n")

def derive_key(api_key, nonce):
    api_key_str = str(api_key).replace('-', '')
    return hashlib.pbkdf2_hmac('sha256', api_key_str.encode('utf-8'), nonce.encode('utf-8'), 600000)[:32]

def encrypt_payload(data, key):
    iv = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(json.dumps(data).encode('utf-8'), AES.block_size)
    encrypted = cipher.encrypt(padded_data)
    return base64.b64encode(encrypted).decode('utf-8'), base64.b64encode(iv).decode('utf-8')

# --- Simulation Suite ---

print("--- Security Tamper & Attack Simulation ---\n")

# 1. SUCCESS CASE: Standard Handshake + Sync
print("[Step] Performing valid handshake...")
hs_res = requests.post(f"{SERVER_URL}/api/v1/gateway/handshake/", json={
    "mac_address": MAC_ADDRESS,
    "hardware_serial": HW_SERIAL
})
nonce = hs_res.json().get('nonce')
session_key = derive_key(API_KEY, nonce)
payload = {"logs": [{"user_id": "SIM_AUTO", "timestamp": datetime.now().isoformat()}]}
enc_data, iv = encrypt_payload(payload, session_key)

sync_body = {
    "mac_address": MAC_ADDRESS,
    "nonce": nonce,
    "timestamp": time.time(),
    "encrypted_data": enc_data,
    "iv": iv
}
res_success = requests.post(f"{SERVER_URL}/api/v1/gateway/sync/", json=sync_body)
print_result("SUCCESS_EXPECTED", res_success)

# 2. FAIL: No Handshake (Missing Nonce)
res_no_nonce = requests.post(f"{SERVER_URL}/api/v1/gateway/sync/", json={
    "mac_address": MAC_ADDRESS,
    "timestamp": time.time(),
    "encrypted_data": enc_data,
    "iv": iv,
    "nonce": ""
})
print_result("FAIL_MISSING_NONCE", res_no_nonce)

# 3. FAIL: Invalid Nonce (Fake ID)
res_fake_nonce = requests.post(f"{SERVER_URL}/api/v1/gateway/sync/", json={
    "mac_address": MAC_ADDRESS,
    "timestamp": time.time(),
    "encrypted_data": enc_data,
    "iv": iv,
    "nonce": "fake-nonce-123"
})
print_result("FAIL_INVALID_NONCE", res_fake_nonce)

# 4. FAIL: Replay Attack (Using previous Nonce)
print("[Step] Attempting to replay the successful nonce...")
res_replay = requests.post(f"{SERVER_URL}/api/v1/gateway/sync/", json=sync_body)
print_result("FAIL_REPLAY_ATTACK", res_replay)

# 5. FAIL: Tampered Timestamp (Anti-Replay Window)
print("[Step] Attempting sync with an old timestamp (expired window)...")
sync_body_old = sync_body.copy()
sync_body_old['timestamp'] = time.time() - 600 # 10 mins ago
res_old_ts = requests.post(f"{SERVER_URL}/api/v1/gateway/sync/", json=sync_body_old)
print_result("FAIL_EXPIRED_TIMESTAMP", res_old_ts)

# 6. FAIL: MFA Failure (Wrong Hardware Serial)
print("[Step] Attempting handshake with wrong Hardware Serial...")
res_bad_serial = requests.post(f"{SERVER_URL}/api/v1/gateway/handshake/", json={
    "mac_address": MAC_ADDRESS,
    "hardware_serial": "WRONG_SERIAL_NUMBER"
})
print_result("FAIL_MFA_HARDWARE_ATTESTATION", res_bad_serial)

print("--- Simulation Complete ---")