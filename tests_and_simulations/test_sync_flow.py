import os
import time
import json
from datetime import datetime
from buffer_manager import OfflineBuffer
from sync_client import SecureSyncClient

def run_simulation():
    print("--- Secure Biometric Gateway Simulation ---")
    
    # Load test config
    config_path = 'test_config.json'
    if not os.path.exists(config_path):
        print("Error: test_config.json not found. Did you run setup_test_env.py first?")
        return
        
    with open(config_path, 'r') as f:
        config = json.load(f)
        
    server_url = config['DJANGO_SERVER_URL']
    mac_address = config['GATEWAY_MAC']
    api_key = config['GATEWAY_API_KEY']
    
    # Initialize modules
    buffer = OfflineBuffer()
    sync_client = SecureSyncClient(server_url, mac_address, api_key)
    
    print("\n[1] Simulating 3 new biometric records being added (Network is UP)...")
    now_iso = str(datetime.now().isoformat())
    buffer.add_log("EMP1001", "192.168.1.100", now_iso, "Check-in", 1) # Fingerprint
    buffer.add_log("EMP1002", "192.168.1.100", now_iso, "Check-in", 15) # Face
    buffer.add_log("EMP1003", "192.168.1.100", now_iso, "Check-in", 0) # Password
    
    unsynced = buffer.get_unsynced_logs()
    print(f"Total unsynced logs in local DB: {len(unsynced)}")
    
    print("\n[2] Attempting secure AES sync to Django Cloud Backend...")
    success, processed_count = sync_client.sync_to_cloud(unsynced)
    
    if success:
        # Update local buffer
        buffer.mark_logs_synced([log['id'] for log in unsynced])
        print(f"Sync successful! Marked {len(unsynced)} logs as synced locally.")
    else:
        print("Sync failed! Check Django server console.")

    print("\n[3] Checking local buffer status...")
    remaining = buffer.get_unsynced_logs()
    print(f"Remaining unsynced logs: {len(remaining)}")
    print("Simulation complete.")

if __name__ == '__main__':
    run_simulation()
