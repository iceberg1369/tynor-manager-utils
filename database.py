# database.py
import sqlite3
import config
import logging

logger = logging.getLogger("database")

def get_connection():
    """
    Returns a new connection to the SQLite database.
    Enable row_factory for dict-like access if needed, 
    but for now keeping it standard.
    """
    conn = sqlite3.connect(config.DB_FILE)
    # enable foreign keys if needed, though not strictly required for this single table
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """
    Initialize the database schema.
    Creates the 'firmwares' table if it doesn't exist.
    """
    schema = """
    CREATE TABLE IF NOT EXISTS firmwares (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device INTEGER,
        firmware INTEGER,
        rev INTEGER,
        download_path TEXT,
        date TEXT
    );

    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        imei TEXT,
        serial TEXT,
        firmware INTEGER,
        device INTEGER,
        rev INTEGER,
        result INTEGER,
        date TEXT,
        attr TEXT
    );
    """
    try:
        with get_connection() as conn:
            conn.executescript(schema)
            # Check if columns exist (for migration) or just rely on simple create if not exists
            # For a new project, CREATE IF NOT EXISTS is sufficient.
        print("✅ Database initialized successfully.")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        # Re-raise to stop startup if DB is critical
        raise e

def find_newer_firmware(device: int, rev: int, current_fw: int):
    """
    Find firmware where device=device, rev=rev, and firmware > current_fw.
    """
    query = "SELECT * FROM firmwares WHERE device = ? AND rev = ? AND firmware > ?"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (device, rev, current_fw))
        # Fetch one (or all? PHP loop implies it could return multiple but usually we want one)
        # PHP does while loop but outputs JSON immediately.
        # We will return list of matches or just the first one.
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            # map tuple to dict based on schema
            # id, device, firmware, rev, download_path, date
            results.append({
                "id": row[0],
                "device": row[1],
                "firmware": row[2],
                "rev": row[3],
                "download_path": row[4],
                "date": row[5]
            })
        return results

def log_fota_request(imei, serial, firmware, device, rev, result, date, attr=""):
    query = """
    INSERT INTO logs (imei, serial, firmware, device, rev, result, date, attr)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    try:
        with get_connection() as conn:
            conn.execute(query, (imei, serial, firmware, device, rev, result, date, attr))
            conn.commit()
    except Exception as e:
        print(f"❌ Failed to log FOTA request: {e}")
