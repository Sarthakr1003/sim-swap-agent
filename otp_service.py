import smtplib
import random
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


def generate_otp():
    """Generates a random 6-digit OTP."""
    return str(random.randint(100000, 999999))


def send_otp_email(to_email: str, otp: str, user_id: str):
    """Sends the OTP to the user's email address."""
    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = "SIM-Swap Verification OTP"

        body = f"""
Dear User ({user_id}),

A SIM swap request has been detected on your account.

Your One-Time Password (OTP) for verification is:

    {otp}

This OTP is valid for 5 minutes. If you did not request this SIM swap, please contact your carrier immediately.

Regards,
SIM-Swap Fraud Detection System
        """

        msg.attach(MIMEText(body, "plain"))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
        server.quit()
        print(f"\n[OTP SENT] Verification email sent to {to_email}")
        return True

    except Exception as e:
        print(f"\n[ERROR] Failed to send email: {str(e)}")
        return False


def send_block_alert_email(to_email: str, user_id: str, phone: str, risk_score: int):
    """
    Sends an alert email to the real user when their account gets BLOCKED.
    This warns them that someone tried to swap their SIM and failed verification.
    """
    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = "SECURITY ALERT: SIM Swap Attempt Blocked on Your Account"

        body = f"""
SECURITY ALERT

Dear User ({user_id}),

We detected a suspicious SIM swap attempt on your account and have BLOCKED it.

Details:
- Phone Number: {phone}
- Risk Score: {risk_score}/100
- Status: BLOCKED — SIM change was NOT completed

What happened:
Someone requested a SIM swap for your phone number. Our fraud detection system
flagged this as suspicious and sent an OTP for verification. The OTP was entered
incorrectly, so the SIM change was blocked.

What you should do:
1. Contact your mobile carrier immediately to ensure your SIM is secure
2. Change your email and banking passwords as a precaution
3. Enable additional security on your accounts
4. If you requested this SIM swap yourself, please contact your carrier directly

If you did NOT request a SIM swap, someone may be attempting to steal your identity.
Please act immediately.

This is an automated alert from your SIM-Swap Fraud Detection System.

Stay safe,
SIM-Swap Fraud Detection System
        """

        msg.attach(MIMEText(body, "plain"))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, to_email, msg.as_string())
        server.quit()
        print(f"\n[ALERT SENT] Block alert email sent to {to_email}")
        return True

    except Exception as e:
        print(f"\n[ERROR] Failed to send alert email: {str(e)}")
        return False


def verify_otp(entered_otp: str, real_otp: str):
    """Checks if the entered OTP matches the real one."""
    return entered_otp.strip() == real_otp


def get_final_decision(otp_verified: bool, original_score: int):
    """
    Returns the FINAL decision after OTP verification attempt.
    Verified -> ALLOW (real user confirmed)
    Failed -> BLOCK (attacker caught)
    """
    if otp_verified:
        return {
            "action": "ALLOW",
            "reason": "OTP verified — real user confirmed. SIM change approved."
        }
    else:
        return {
            "action": "BLOCK",
            "reason": f"OTP verification failed. Risk score was {original_score}/100. SIM change blocked — possible fraud."
        }