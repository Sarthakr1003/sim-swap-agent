import sqlite3
import os

DB_PATH = "data/sim_swap.db"


def get_connection():
    """Returns a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Creates the database tables if they don't exist."""
    os.makedirs("data", exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            phone TEXT,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            country TEXT,
            new_carrier TEXT,
            risk_score INTEGER,
            action TEXT,
            reason TEXT,
            otp_verified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            otp_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blocked_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            phone TEXT,
            reason TEXT,
            blocked_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")


def log_event_db(user_id, phone, event_type, timestamp, country,
                 new_carrier, risk_score, action, reason):
    """Saves an event to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO events
        (user_id, phone, event_type, timestamp, country, new_carrier, risk_score, action, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, phone, event_type, timestamp, country,
          new_carrier, risk_score, action, reason))
    conn.commit()
    conn.close()


def get_user_events_db(user_id: str):
    """Returns all events for a specific user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM events WHERE user_id = ? ORDER BY created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_events_db():
    """Returns all events."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_stats_db():
    """Returns decision counts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT action, COUNT(*) as count FROM events GROUP BY action
    """)
    rows = cursor.fetchall()
    conn.close()
    stats = {"ALLOW": 0, "CHALLENGE": 0, "BLOCK": 0, "total": 0}
    for row in rows:
        action = row["action"]
        count = row["count"]
        if action in stats:
            stats[action] = count
        stats["total"] += count
    return stats


def save_otp_db(user_id: str, otp: str, expires_minutes: int = 5):
    """Saves OTP hash with expiry to database."""
    import hashlib
    from datetime import datetime, timedelta
    otp_hash = hashlib.sha256(otp.encode()).hexdigest()
    expires_at = (datetime.now() + timedelta(minutes=expires_minutes)).isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO otp_attempts (user_id, otp_hash, expires_at)
        VALUES (?, ?, ?)
    """, (user_id, otp_hash, expires_at))
    conn.commit()
    otp_id = cursor.lastrowid
    conn.close()
    return otp_id


def verify_otp_db(otp_id: int, entered_otp: str):
    """
    Verifies OTP against database.
    Returns True if correct and not expired.
    Returns False if wrong or expired.
    """
    import hashlib
    from datetime import datetime
    entered_hash = hashlib.sha256(entered_otp.encode()).hexdigest()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM otp_attempts WHERE id = ? AND used = 0
    """, (otp_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return False, "OTP not found or already used"

    # Check expiry
    expires_at = datetime.fromisoformat(row["expires_at"])
    if datetime.now() > expires_at:
        conn.close()
        return False, "OTP expired"

    # Check hash
    if row["otp_hash"] != entered_hash:
        conn.close()
        return False, "Wrong OTP"

    # Mark as used
    cursor.execute("UPDATE otp_attempts SET used = 1 WHERE id = ?", (otp_id,))
    conn.commit()
    conn.close()
    return True, "OTP verified"


def block_user_db(user_id: str, phone: str, reason: str):
    """Adds a user to the blocked list."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO blocked_users (user_id, phone, reason)
        VALUES (?, ?, ?)
    """, (user_id, phone, reason))
    conn.commit()
    conn.close()


def is_user_blocked(user_id: str, phone: str):
    """Checks if a user or phone number is blocked."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM blocked_users
        WHERE user_id = ? OR phone = ?
    """, (user_id, phone))
    row = cursor.fetchone()
    conn.close()
    return row is not None


def get_recent_failures_db(user_id: str, minutes: int = 10):
    """Returns number of failed OTP attempts in the last N minutes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) as count FROM events
        WHERE user_id = ?
        AND action = 'BLOCK'
        AND created_at >= datetime('now', ?)
    """, (user_id, f'-{minutes} minutes'))
    row = cursor.fetchone()
    conn.close()
    return row["count"]


# Initialize database when this module is imported
init_db()