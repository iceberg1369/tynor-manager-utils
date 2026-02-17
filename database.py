# database.py
import sqlite3
import config
import logging
import json
import os

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
    Reads from 'firmwares.json' in the same directory.
    """
    try:
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'firmwares.json')
        with open(json_path, 'r') as f:
            firmwares = json.load(f)
            
        results = [
            fw for fw in firmwares 
            if fw.get("device") == device 
            and fw.get("rev") == rev 
            and fw.get("firmware") > current_fw
        ]
        
        return results
    except Exception as e:
        logger.error(f"Failed to load firmware from JSON: {e}")
        return []

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
