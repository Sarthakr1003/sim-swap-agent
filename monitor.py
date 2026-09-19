import os
import time
import sqlite3
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN")
ABSTRACT_API_KEY   = os.getenv("ABSTRACT_API_KEY")
API_URL            = "http://127.0.0.1:8000"
CHECK_INTERVAL     = 300  # check every 5 minutes
DB_PATH            = "data/sim_swap.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_monitor_table():
    """Creates the monitored_numbers table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS monitored_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL,
            user_id TEXT NOT NULL,
            last_carrier TEXT,
            last_checked TEXT,
            registered_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()
    print("[MONITOR] Monitor table ready.")


def register_number(phone: str, email: str, user_id: str):
    """Registers a phone number for monitoring."""
    carrier = lookup_carrier(phone)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO monitored_numbers
        (phone, email, user_id, last_carrier, last_checked)
        VALUES (?, ?, ?, ?, ?)
    """, (phone, email, user_id, carrier, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    print(f"[MONITOR] Registered {phone} — current carrier: {carrier}")
    return carrier


def lookup_carrier_abstract(phone: str):
    """Uses Abstract Phone Intelligence API to get carrier info — supports Indian numbers."""
    try:
        url = f"https://phoneintelligence.abstractapi.com/v1?api_key={ABSTRACT_API_KEY}&phone={phone}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            carrier = data.get("phone_carrier", {}).get("name", None)
            if carrier:
                print(f"[MONITOR] Abstract API: {phone} -> {carrier}")
                return carrier
            else:
                print(f"[MONITOR] Abstract API: no carrier info for {phone}")
                return None
        else:
            print(f"[MONITOR] Abstract API failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"[MONITOR] Abstract API error: {e}")
        return None


def lookup_carrier_twilio(phone: str):
    """Uses Twilio Lookup API — works for US/international numbers."""
    try:
        url = f"https://lookups.twilio.com/v1/PhoneNumbers/{phone}?Type=carrier"
        response = requests.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=10)
        if response.status_code == 200:
            data = response.json()
            carrier = data.get("carrier", {}).get("name", None)
            if carrier:
                print(f"[MONITOR] Twilio: {phone} -> {carrier}")
                return carrier
        return None
    except Exception as e:
        print(f"[MONITOR] Twilio error: {e}")
        return None


def lookup_carrier(phone: str):
    """
    Smart carrier lookup — tries Abstract API first (supports IN),
    falls back to Twilio for other regions.
    """
    if ABSTRACT_API_KEY:
        carrier = lookup_carrier_abstract(phone)
        if carrier:
            return carrier

    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        carrier = lookup_carrier_twilio(phone)
        if carrier:
            return carrier

    return None


def get_monitored_numbers():
    """Returns all registered phone numbers."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM monitored_numbers")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_carrier(phone: str, new_carrier: str):
    """Updates the last known carrier for a phone number."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE monitored_numbers
        SET last_carrier = ?, last_checked = ?
        WHERE phone = ?
    """, (new_carrier, datetime.now().isoformat(), phone))
    conn.commit()
    conn.close()


def fire_event(phone: str, email: str, user_id: str, old_carrier: str, new_carrier: str):
    """Automatically fires a SIM swap event to the fraud detection API."""
    print(f"[MONITOR] CARRIER CHANGE DETECTED for {phone}!")
    print(f"[MONITOR] {old_carrier} -> {new_carrier}")
    print(f"[MONITOR] Firing automatic fraud detection event...")

    event = {
        "user_id": user_id,
        "event_type": "sim_change",
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "phone": phone,
            "email": email,
            "country": "AUTO_DETECTED",
            "new_carrier": new_carrier,
            "old_carrier": old_carrier,
            "detection_method": "automatic_carrier_monitoring"
        }
    }

    try:
        response = requests.post(f"{API_URL}/event", json=event, timeout=180)
        result = response.json()
        print(f"[MONITOR] Agent decision: {result.get('action')} (score: {result.get('risk_score')})")
        print(f"[MONITOR] Reason: {result.get('reason')}")
        return result
    except Exception as e:
        print(f"[MONITOR] Failed to fire event: {e}")
        return None


def check_all_numbers():
    """Checks all monitored numbers for carrier changes."""
    numbers = get_monitored_numbers()
    if not numbers:
        print("[MONITOR] No numbers registered for monitoring.")
        return

    print(f"[MONITOR] Checking {len(numbers)} registered number(s)...")
    for entry in numbers:
        phone        = entry["phone"]
        email        = entry["email"]
        user_id      = entry["user_id"]
        last_carrier = entry["last_carrier"]

        current_carrier = lookup_carrier(phone)
        if current_carrier is None:
            print(f"[MONITOR] Could not check {phone} — skipping.")
            continue

        print(f"[MONITOR] {phone}: {last_carrier} -> {current_carrier}")

        if last_carrier and current_carrier != last_carrier:
            fire_event(phone, email, user_id, last_carrier, current_carrier)

        update_carrier(phone, current_carrier)


def run_monitor():
    """Main monitoring loop — runs forever, checking every 5 minutes."""
    print("[MONITOR] Starting phone number monitoring service...")
    print(f"[MONITOR] Checking every {CHECK_INTERVAL} seconds ({CHECK_INTERVAL//60} minutes)")
    init_monitor_table()

    while True:
        print(f"\n[MONITOR] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — Running checks...")
        check_all_numbers()
        print(f"[MONITOR] Next check in {CHECK_INTERVAL//60} minutes.")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    run_monitor()