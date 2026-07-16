from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class AccountEvent(BaseModel):
    user_id: str
    event_type: str          # e.g. "sim_change", "device_change", "location_change"
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class FraudDecision(BaseModel):
    action: str               # "ALLOW", "CHALLENGE", or "BLOCK"
    risk_score: int            # 0 to 100
    reason: str


class VerificationRequest(BaseModel):
    user_id: str
    method: str                # "otp" or "identity_check"