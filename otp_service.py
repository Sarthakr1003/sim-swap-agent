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


def verify_otp(entered_otp: str, real_otp: str):
    """Checks if the entered OTP matches the real one."""
    return entered_otp.strip() == real_otp