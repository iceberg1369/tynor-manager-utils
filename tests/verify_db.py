from database import init_db
import os
import sqlite3

try:
    if os.path.exists("traccar.db"):
        os.remove("traccar.db")
    
    init_db()
    
    if os.path.exists("traccar.db"):
        print("✅ DB file created.")
        conn = sqlite3.connect("traccar.db")
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(firmwares)")
        columns_fw = [row[1] for row in cursor.fetchall()]
        print("Firmwares Columns:", columns_fw)
        
        cursor.execute("PRAGMA table_info(logs)")
        columns_logs = [row[1] for row in cursor.fetchall()]
        print("Logs Columns:", columns_logs)

        expected_fw = ['id', 'device', 'firmware', 'rev', 'download_path', 'date']
        expected_logs = ['id', 'imei', 'serial', 'firmware', 'device', 'rev', 'result', 'date', 'attr']
        
        if all(c in columns_fw for c in expected_fw) and all(c in columns_logs for c in expected_logs):
            print("✅ Schema matches.")
        else:
            print("❌ Schema mismatch.")
        conn.close()
    else:
        print("❌ DB file not found.")

except Exception as e:
    print(f"❌ Verification failed: {e}")
