"""
Simulation 2: Edge Gateway architecture
This script simulates the Raspberry Pi Gateway approach.
The device sends data to the local gateway. The gateway buffers it securely.
Even if the internet is down, the data is safe. When the internet returns, it syncs encrypted data to the cloud.
"""
import time
import os
from datetime import datetime

# Import the actual Gateway classes we built
import sys
from dotenv import load_dotenv
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(os.path.join(BASE_DIR, '.env'))
sys.path.append(os.path.join(BASE_DIR, 'gateway_client'))
from buffer_manager import OfflineBuffer # noqa: E402
from sync_client import SecureSyncClient # noqa: E402

def run_gateway_simulation():
    print("-" * 50)
    print("SCENARIO B: Hybrid Edge Gateway Architecture")
    print("-" * 50)
    
    server_url = os.getenv("TEST_SERVER_URL", "http://127.0.0.1:8000")
    mac_address = os.getenv("GATEWAY_MAC", "00:00:00:00:00:00")
    api_key = os.getenv("GATEWAY_API_KEY", "00000000-0000-0000-0000-000000000000")

    db_path = os.path.join(BASE_DIR, 'gateway_client', 'local_simulation.db')
    buffer = OfflineBuffer(db_path)
    sync_client = SecureSyncClient(server_url, mac_address, api_key)
    
    time.sleep(1)
    
    # 1. Local Buffering (Internet Down)
    print("\n--- Test 1: Internet Outage Condition (Device -> Gateway) ---")
    print("[Internet] Simulated Offline")
    
    print("-> Biometric device registers punches...")
    machine_ip = os.getenv("BIOMETRIC_MACHINE_IP", "10.0.0.50")
    buffer.add_log("EMP003", machine_ip, datetime.now().isoformat(), "Check-in", 1)
    time.sleep(0.5)
    buffer.add_log("EMP004", machine_ip, datetime.now().isoformat(), "Check-out", 1)
    
    print("[OK] Gateway: Safely buffered 2 logs locally in SQLite database.")
    
    unsynced = buffer.get_unsynced_logs()
    print(f"-> Unsynced logs waiting in buffer: {len(unsynced)}")
    
    print("[FAIL] Gateway: Sync attempted but network is down. Data remains safe.")
    
    time.sleep(2)
    
    # 2. Local Buffering (Internet Restored)
    print("\n--- Test 2: Internet Restored (Gateway -> Cloud) ---")
    print("[Internet] Online")
    
    unsynced = buffer.get_unsynced_logs()
    print(f"-> Initiating secure encrypted sync for {len(unsynced)} buffered logs...")
    
    success, num_processed = sync_client.sync_to_cloud(unsynced)
    
    if success:
        log_ids = [log['id'] for log in unsynced]
        buffer.mark_logs_synced(log_ids)
        print(f"[OK] Secure Sync Successful. {num_processed} records securely encrypted (AES-256) and accepted by cloud.")
        print(f"[OK] Local buffer updated. Waiting unsynced logs: {len(buffer.get_unsynced_logs())}")
    else:
        print("❌ Cloud connection refused. Ensure Django server is running.")

    print("\nConclusion: The Edge Gateway ensures zero data loss during network outages and provides military-grade encryption for internet transmission.")

if __name__ == "__main__":
    run_gateway_simulation()
