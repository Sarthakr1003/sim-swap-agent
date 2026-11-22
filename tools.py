"""
Deterministic tools the LLM agent can call.

The agent decides WHICH tools to call and in what order, but the numbers it
reasons about always come from these functions, never from the model itself.
"""
from models import AccountEvent
from database import get_user_events_db

# Rows written by /verify-otp are verification outcomes, not account changes,
# so they are left out of the history the risk scorer looks at.
NON_CHANGE_EVENT_TYPES = {"otp_verification"}


def check_account_history(user_id: str):
    """
    Tool 1: Returns previous account-change events for this user from SQLite
    (newest first). The agent calls this to see what happened on this account
    before the current event.
    """
    rows = get_user_events_db(user_id)
    return [
        {
            "event_type": r["event_type"],
            "timestamp": r["timestamp"],
            "country": r["country"],
            "new_carrier": r["new_carrier"],
            "risk_score": r["risk_score"],
            "action": r["action"],
        }
        for r in rows
        if r["event_type"] not in NON_CHANGE_EVENT_TYPES
    ]


def calculate_risk_score(event: AccountEvent):
    """
    Tool 2: Heuristic risk scorer (0-100), five factors.
    The agent calls this to get a numeric risk estimate for the current event.
    """
    score = 0
    reasons = []

    hour = event.timestamp.hour
    if hour >= 23 or hour < 5:
        score += 25
        reasons.append("Event occurred at an unusual hour (11PM-5AM)")

    country = event.metadata.get("country")
    if country and country != "IN":
        score += 25
        reasons.append("Foreign country detected")

    history = check_account_history(event.user_id)
    if len(history) >= 2:
        score += 20
        reasons.append(f"Multiple prior account changes on record ({len(history)})")

    if event.metadata.get("new_carrier"):
        score += 15
        reasons.append("Carrier change detected")

    if len(history) == 0:
        score += 10
        reasons.append("No prior history on this account")

    score = min(score, 100)
    return {"score": score, "reasons": reasons}


def trigger_verification(user_id: str, method: str):
    """
    Tool 3: Flags that step-up verification is required for this user.

    The agent only records the request here. The real OTP is generated,
    hashed into SQLite and emailed by the /send-otp endpoint, which the
    web UI and CLI simulator call once /event returns CHALLENGE. Keeping
    OTP generation out of the LLM loop means the model never sees the code.
    """
    print(f"[VERIFICATION REQUESTED] User: {user_id} | Method: {method}")
    return {"status": "verification_required", "user_id": user_id, "method": method}
