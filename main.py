from fastapi import FastAPI, HTTPException
from models import AccountEvent, FraudDecision
from agent import run_fraud_agent
from tools import log_event, check_account_history, _load_log

app = FastAPI(title="SIM-Swap Fraud Detection Agent")


@app.get("/health")
def health_check():
    """Simple check to confirm the API is running."""
    return {"status": "ok"}


@app.post("/event", response_model=FraudDecision)
def receive_event(event: AccountEvent):
    """
    Main endpoint: receives an account change event,
    runs it through the fraud detection agent, logs the result,
    and returns the final decision.
    """
    try:
        decision = run_fraud_agent(event, debug=False)
        log_event(event, decision)
        return FraudDecision(
            action=decision["action"],
            risk_score=decision["risk_score"],
            reason=decision["reason"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events/{user_id}")
def get_user_events(user_id: str):
    """Returns the logged event history for a given user."""
    history = check_account_history(user_id)
    return {"user_id": user_id, "events": history}


@app.get("/stats")
def get_stats():
    """Returns a summary count of all decisions made so far."""
    entries = _load_log()
    stats = {"ALLOW": 0, "CHALLENGE": 0, "BLOCK": 0, "total": len(entries)}
    for entry in entries:
        action = entry.get("decision", {}).get("action", "")
        if action in stats:
            stats[action] += 1
    return stats