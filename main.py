from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from models import AccountEvent, FraudDecision
from agent import run_fraud_agent
from otp_service import generate_otp, send_otp_email, send_block_alert_email, get_final_decision
from database import (
    init_db, log_event_db, get_user_events_db,
    get_all_events_db, get_stats_db, save_otp_db,
    verify_otp_db, block_user_db, is_user_blocked,
    get_recent_failures_db
)

app = FastAPI(title="SIM-Swap Fraud Detection Agent")
init_db()


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
        phone = event.metadata.get("phone", "")
        user_id = event.user_id

        if is_user_blocked(user_id, phone):
            return FraudDecision(
                action="BLOCK",
                risk_score=100,
                reason="This user/phone is permanently blocked due to repeated fraud attempts."
            )

        recent_failures = get_recent_failures_db(user_id, minutes=10)
        if recent_failures >= 3:
            block_user_db(user_id, phone, "Repeated OTP failures — possible brute force attack")
            return FraudDecision(
                action="BLOCK",
                risk_score=100,
                reason="Too many failed verification attempts. Account blocked for security."
            )

        decision = run_fraud_agent(event, debug=False)

        log_event_db(
            user_id=user_id,
            phone=phone,
            event_type=event.event_type,
            timestamp=event.timestamp.isoformat(),
            country=event.metadata.get("country", ""),
            new_carrier=event.metadata.get("new_carrier", ""),
            risk_score=decision["risk_score"],
            action=decision["action"],
            reason=decision["reason"]
        )

        return FraudDecision(
            action=decision["action"],
            risk_score=decision["risk_score"],
            reason=decision["reason"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── GET ALL EVENTS ─────────────────────────────────────────────────────
@app.get("/events/all")
def get_all_events():
    events = get_all_events_db()
    return {"events": events}


# ── GET USER EVENT HISTORY ─────────────────────────────────────────────
@app.get("/events/{user_id}")
def get_user_events(user_id: str):
    events = get_user_events_db(user_id)
    return {"user_id": user_id, "events": events}


# ── STATS ──────────────────────────────────────────────────────────────
@app.get("/stats")
def get_stats():
    return get_stats_db()


# ── SEND OTP ──────────────────────────────────────────────────────────
class OTPRequest(BaseModel):
    email: str
    user_id: str

@app.post("/send-otp")
def send_otp(req: OTPRequest):
    otp = generate_otp()
    success = send_otp_email(req.email, otp, req.user_id)
    if success:
        otp_id = save_otp_db(req.user_id, otp, expires_minutes=5)
        return {"status": "sent", "otp_id": otp_id, "otp": otp}
    raise HTTPException(status_code=500, detail="Failed to send OTP email")


# ── VERIFY OTP — FINAL DECISION ────────────────────────────────────────
class OTPVerifyRequest(BaseModel):
    otp_id: int
    entered_otp: str
    risk_score: int
    user_id: str
    phone: str = ""
    email: str = ""

@app.post("/verify-otp")
def verify_otp_endpoint(req: OTPVerifyRequest):
    verified, message = verify_otp_db(req.otp_id, req.entered_otp)
    result = get_final_decision(verified, req.risk_score)

    log_event_db(
        user_id=req.user_id,
        phone=req.phone,
        event_type="otp_verification",
        timestamp=__import__('datetime').datetime.now().isoformat(),
        country="",
        new_carrier="",
        risk_score=req.risk_score,
        action=result["action"],
        reason=result["reason"]
    )

    if result["action"] == "BLOCK":
        block_user_db(req.user_id, req.phone, result["reason"])
        # Send security alert email to warn the real user
        if req.email:
            send_block_alert_email(req.email, req.user_id, req.phone, req.risk_score)

    return result


# ── REGISTER PHONE FOR MONITORING ─────────────────────────────────────
class RegisterRequest(BaseModel):
    phone: str
    email: str
    user_id: str

@app.post("/register")
def register_phone(req: RegisterRequest):
    try:
        from monitor import register_number, init_monitor_table
        init_monitor_table()
        carrier = register_number(req.phone, req.email, req.user_id)
        return {
            "status": "registered",
            "phone": req.phone,
            "current_carrier": carrier,
            "message": f"Phone registered. Current carrier: {carrier}. Monitoring active."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))