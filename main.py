from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from models import AccountEvent, FraudDecision
from agent import run_fraud_agent
from tools import log_event, check_account_history, _load_log
from otp_service import generate_otp, send_otp_email, get_final_decision

app = FastAPI(title="SIM-Swap Fraud Detection Agent")


# ── SERVE WEB UI ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def home():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ── HEALTH CHECK ──────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "ok"}


# ── MAIN FRAUD DETECTION ENDPOINT ─────────────────────────────────────
@app.post("/event", response_model=FraudDecision)
def receive_event(event: AccountEvent):
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


# ── GET ALL EVENTS (must be before /{user_id} to avoid conflict) ───────
@app.get("/events/all")
def get_all_events():
    log = _load_log()
    return {"events": log}


# ── GET USER EVENT HISTORY ─────────────────────────────────────────────
@app.get("/events/{user_id}")
def get_user_events(user_id: str):
    history = check_account_history(user_id)
    return {"user_id": user_id, "events": history}


# ── STATS ──────────────────────────────────────────────────────────────
@app.get("/stats")
def get_stats():
    entries = _load_log()
    stats = {"ALLOW": 0, "CHALLENGE": 0, "BLOCK": 0, "total": len(entries)}
    for entry in entries:
        action = entry.get("decision", {}).get("action", "")
        if action in stats:
            stats[action] += 1
    return stats


# ── SEND OTP ──────────────────────────────────────────────────────────
class OTPRequest(BaseModel):
    email: str
    user_id: str

@app.post("/send-otp")
def send_otp(req: OTPRequest):
    otp = generate_otp()
    success = send_otp_email(req.email, otp, req.user_id)
    if success:
        return {"status": "sent", "otp": otp}
    raise HTTPException(status_code=500, detail="Failed to send OTP email")


# ── VERIFY OTP — FINAL DECISION ────────────────────────────────────────
class OTPVerifyRequest(BaseModel):
    entered_otp: str
    real_otp: str
    risk_score: int
    user_id: str

@app.post("/verify-otp")
def verify_otp_endpoint(req: OTPVerifyRequest):
    """
    Final decision after OTP attempt.
    Correct OTP → ALLOW (real user confirmed)
    Wrong OTP → BLOCK (attacker caught)
    """
    verified = req.entered_otp.strip() == req.real_otp.strip()
    result = get_final_decision(verified, req.risk_score)
    return result