import os
from flask import Flask, request
from dotenv import load_dotenv
from datetime import datetime
from buffer_manager import OfflineBuffer
from sync_client import SecureSyncClient

def get_mac_address():
    """
    Auto-detect the MAC address of the primary interface.
    """
    try:
        # On Raspberry Pi (Linux)
        with open('/sys/class/net/eth0/address', 'r') as f:
            return f.read().strip().lower()
    except Exception:
        try:
            with open('/sys/class/net/wlan0/address', 'r') as f:
                return f.read().strip().lower()
        except Exception:
            # Fallback for local simulation
            return "e4:5f:01:68:8a:a5"

# --- Load Environment Configuration ---
load_dotenv()

# --- Configuration ---
DJANGO_SERVER_URL = os.getenv("DJANGO_SERVER_URL", "http://127.0.0.1:8000/api/v1/gateway/sync/")
GATEWAY_MAC = os.getenv("GATEWAY_MAC", get_mac_address())
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY") 
FLASK_PORT = int(os.getenv("FLASK_PORT", "8080"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "local_buffer.db")

# --- Initialize Modules ---
buffer = OfflineBuffer(db_path=DATABASE_PATH)
sync_client = SecureSyncClient(DJANGO_SERVER_URL, GATEWAY_MAC, GATEWAY_API_KEY)

app = Flask(__name__)

@app.route('/iclock/cdata.aspx', methods=['GET', 'POST'])
def iclock_cdata():
    """
    Endpoint for ZKTeco/eSSL biometric devices to push attendance logs.
    """
    if request.method == 'GET':
        return "OK\n"
        
    sn = request.args.get('SN')
    device_ip = request.remote_addr
    
    if not sn:
        return "OK\n"

    try:
        body = request.get_data(as_text=True)
        
        for line in body.strip().splitlines():
            line = line.strip()
            if not line or line.startswith('OPLOG') and 'USER' in line:
                continue
                
            parts = line.split('\t')
            if len(parts) >= 2:
                # Format 1: USERID \t TIMESTAMP \t STATUS \t VERIFIED
                # Format 2: USERID \t DATE \t TIME \t STATUS \t VERIFIED
                user_id = parts[0]
                
                if ' ' in parts[1] and ':' in parts[1]: # Combined YYYY-MM-DD HH:MM:SS
                    timestamp_str = parts[1]
                    status = parts[2] if len(parts) > 2 else "0"
                    verified = parts[3] if len(parts) > 3 else "1"
                else: # Separate date and time
                    if len(parts) < 3: 
                        continue
                    timestamp_str = f"{parts[1]} {parts[2]}"
                    status = parts[3] if len(parts) > 3 else "0"
                    verified = parts[4] if len(parts) > 4 else "1"
                    
                # Map status
                punch_type = "Check-in" if status == "0" else ("Check-out" if status == "1" else "Unknown")
                
                # Verify numeric parsing
                verification_mode = int(verified) if verified.isdigit() else 1
                
                # Convert timestamp for JSON syncing
                try:
                    dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    iso_timestamp = dt.isoformat() + "Z"
                except ValueError:
                    iso_timestamp = datetime.now().isoformat() + "Z"
                    
                # Instantly save to SQLite (zero data loss)
                saved = buffer.add_log(user_id, device_ip, iso_timestamp, punch_type, verification_mode)
                if saved:
                    print(f"[Device {sn}] Buffered punch for User {user_id} at {iso_timestamp} ({punch_type})")
                else:
                    print(f"FAILED to buffer punch for User {user_id}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error processing push data: {e}")

    return "OK\n"

def process_and_sync():
    """
    1. Fetches new logs from the local database buffer.
    2. Encrypts and sends them to the Cloud Dashboard.
    3. Marks them as synced locally if successful.
    """
    unsynced_logs = buffer.get_unsynced_logs(limit=50) # Process in batches of 50
    if not unsynced_logs:
        print("No unsynced logs found in buffer.")
        return
        
    print(f"Found {len(unsynced_logs)} unsynced logs. Attempting to sync...")
    success, num_processed = sync_client.sync_to_cloud(unsynced_logs)
    
    if success:
        log_ids = [log['id'] for log in unsynced_logs]
        buffer.mark_logs_synced(log_ids)
        print(f"Successfully synced and updated local buffer. ({num_processed} accepted by Django)")
    else:
        print("Sync failed. Logs will remain in the offline buffer for the next retry.")

def cleanup_routine():
    print("Running weekly cleanup of old synced logs...")
    buffer.cleanup_synced_logs(days_old=7)

def schedule_runner():
    # Try syncing to server every 2 minutes
    schedule.every(2).minutes.do(process_and_sync)
    # Cleanup every Sunday
    schedule.every().sunday.at("02:00").do(cleanup_routine)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

import time
import threading
import schedule

if __name__ == "__main__":
    print(f"Starting Secure Biometric Gateway Service...")
    print(f"Gateway MAC: {GATEWAY_MAC}")
    print(f"Server URL: {DJANGO_SERVER_URL}")
    print(f"Listening for eSSL ADMS Pushes on port {FLASK_PORT} (/iclock/cdata.aspx)...")
    
    # Run an immediate sync on startup
    process_and_sync()
    
    import sys
    if "--test-punch" in sys.argv:
        print("Generating test punch...")
        buffer.add_log("TEST_USER", "127.0.0.1", datetime.now().isoformat() + "Z", "Check-in", 1)
        process_and_sync()
        sys.exit(0)
    scheduler_thread = threading.Thread(target=schedule_runner, daemon=True)
    scheduler_thread.start()
    
    # Start the Flask HTTP server to receive punches from eSSL hardware on LAN
    app.run(host='0.0.0.0', port=FLASK_PORT, threaded=True)
