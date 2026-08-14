import json
import os
from datetime import datetime
from models import AccountEvent

LOG_FILE = "data/events_log.json"


def _load_log():
    """Reads the events log file, returns empty list if it doesn't exist yet."""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        return json.load(f)


def _save_log(log):
    """Writes the events log back to the file."""
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, default=str)


def check_account_history(user_id: str):
    """
    Tool 1: Returns recent events for this user.
    The agent calls this to see what's happened on this account before.
    """
    log = _load_log()
    history = [entry for entry in log if entry.get("user_id") == user_id]
    return history


def calculate_risk_score(event: AccountEvent):
    """
    Tool 2: Heuristic risk scorer (0-100).
    The agent calls this to get a numeric risk estimate for the current event.
    """
    score = 0
    reasons = []

    hour = event.timestamp.hour
    if hour >= 23 or hour < 5:
        score += 25
        reasons.append("Event occurred at an unusual hour (11PM-5AM)")

    if event.metadata.get("country") and event.metadata.get("country") != "IN":
        score += 25
        reasons.append("Foreign country detected")

    history = check_account_history(event.user_id)
    if len(history) >= 2:
        score += 20
        reasons.append("Multiple account changes detected recently")

    if event.metadata.get("new_carrier"):
        score += 15
        reasons.append("Carrier change detected")

    if len(history) == 0:
        score += 10
        reasons.append("No prior history on this account")

    score = min(score, 100)
    return {"score": score, "reasons": reasons}


def trigger_verification(user_id: str, method: str, email: str = None):
    """
    Tool 3: Sends a real step-up verification challenge via email OTP.
    """
    from otp_service import generate_otp, send_otp_email

    otp = generate_otp()

    if email:
        success = send_otp_email(email, otp, user_id)
        if success:
            return {
                "status": "otp_sent",
                "user_id": user_id,
                "method": method,
                "otp": otp
            }

    print(f"[VERIFICATION TRIGGERED] User: {user_id} | Method: {method}")
    return {"status": "verification_sent", "user_id": user_id, "method": method, "otp": otp}


def log_event(event: AccountEvent, decision: dict):
    """
    Saves the event + final decision to the log file for audit purposes.
    """
    log = _load_log()
    log.append({
        "user_id": event.user_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp.isoformat(),
        "metadata": event.metadata,
        "decision": decision
    })
    _save_log(log)