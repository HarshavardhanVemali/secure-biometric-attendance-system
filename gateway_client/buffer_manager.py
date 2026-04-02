import sqlite3

class OfflineBuffer:
    def __init__(self, db_path='local_buffer.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initializes the SQLite database with the required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create a table for raw attendance logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                machine_ip TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                punch_type TEXT DEFAULT 'Unknown',
                verification_mode INTEGER DEFAULT 0,
                synced BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create an index to speed up sync queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_synced ON attendance_logs(synced)')
        
        conn.commit()
        conn.close()

    def add_log(self, user_id, machine_ip, timestamp_iso, punch_type="Unknown", verification_mode=0):
        """Adds a new attendance log to the local buffer."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO attendance_logs (user_id, machine_ip, timestamp, punch_type, verification_mode, synced)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (str(user_id), machine_ip, timestamp_iso, punch_type, int(verification_mode)))
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error inserting log: {e}")
            return False
        finally:
            conn.close()

    def get_unsynced_logs(self, limit=100):
        """Retrieves a batch of unsynced logs."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT id, user_id, machine_ip, timestamp, punch_type, verification_mode
                FROM attendance_logs
                WHERE synced = 0
                ORDER BY timestamp ASC
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            logs = []
            for row in rows:
                logs.append({
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "machine_ip": row["machine_ip"],
                    "timestamp": row["timestamp"],
                    "punch_type": row["punch_type"],
                    "verification": row["verification_mode"]
                })
            return logs
        except sqlite3.Error as e:
            print(f"Database error retrieving logs: {e}")
            return []
        finally:
            conn.close()

    def mark_logs_synced(self, log_ids):
        """Marks a list of log IDs as successfully synced."""
        if not log_ids:
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            placeholders = ','.join(['?'] * len(log_ids))
            cursor.execute(f'''
                UPDATE attendance_logs
                SET synced = 1
                WHERE id IN ({placeholders})
            ''', tuple(log_ids))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error updating logs: {e}")
        finally:
            conn.close()

    def cleanup_synced_logs(self, days_old=7):
        """Deletes old synced logs to save space."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(f'''
                DELETE FROM attendance_logs
                WHERE synced = 1 AND created_at <= date('now', '-{days_old} days')
            ''')
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error cleaning up logs: {e}")
        finally:
            conn.close()
