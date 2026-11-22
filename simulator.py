"""
CLI simulator for the SIM-Swap Fraud Detection Agent.

Sends events to the running FastAPI server (uvicorn main:app). OTPs are sent
and checked through the same /send-otp and /verify-otp endpoints the web UI
uses, so the OTP is hashed in SQLite, expires after 5 minutes and is single-use.
"""
import httpx
from datetime import datetime

API_URL = "http://127.0.0.1:8000"

DECISION_COLORS = {
    "ALLOW":     "\033[92m",
    "CHALLENGE": "\033[93m",
    "BLOCK":     "\033[91m",
}
RESET = "\033[0m"
BOLD  = "\033[1m"

# Preset scenario user IDs start with this prefix, so option 7 can remove them
PRESET_PREFIX = "sim_user_"


def get_scenarios():
    # A fresh suffix per run gives each preset a clean account history,
    # which keeps the expected scores reproducible.
    ts = datetime.now().strftime("%H%M%S")
    return {
        "1": {
            "name": "Normal SIM Change",
            "expected": "ALLOW",
            "event": {
                "user_id": f"{PRESET_PREFIX}001_{ts}",
                "event_type": "sim_change",
                "timestamp": "2026-06-18T14:30:00",
                "metadata": {"country": "IN", "new_carrier": "Airtel"}
            }
        },
        "2": {
            "name": "Late Night SIM Change",
            "expected": "CHALLENGE",
            "event": {
                "user_id": f"{PRESET_PREFIX}002_{ts}",
                "event_type": "sim_change",
                "timestamp": "2026-06-18T03:15:00",
                "metadata": {"country": "IN", "new_carrier": "Airtel"}
            }
        },
        "3": {
            "name": "Foreign IP + SIM Change",
            "expected": "CHALLENGE",
            "event": {
                "user_id": f"{PRESET_PREFIX}003_{ts}",
                "event_type": "sim_change",
                "timestamp": "2026-06-18T11:00:00",
                "metadata": {"country": "US", "new_carrier": "Airtel"}
            }
        },
        "4": {
            "name": "Multi-Signal Spike (foreign + night + carrier)",
            "expected": "CHALLENGE",
            "event": {
                "user_id": f"{PRESET_PREFIX}004_{ts}",
                "event_type": "sim_change",
                "timestamp": "2026-06-18T02:45:00",
                "metadata": {"country": "US", "new_carrier": "Verizon"}
            }
        },
        "5": {
            "name": "High-Risk Swap (CN, 4 AM)",
            "expected": "CHALLENGE",
            "event": {
                "user_id": f"{PRESET_PREFIX}005_{ts}",
                "event_type": "sim_change",
                "timestamp": "2026-06-18T04:00:00",
                "metadata": {"country": "CN", "new_carrier": "T-Mobile"}
            }
        }
    }


def print_banner():
    print("\n" + "=" * 55)
    print(f"{BOLD}   SIM-SWAP FRAUD DETECTION AGENT - CLI{RESET}")
    print("=" * 55)


def print_menu(scenarios):
    print(f"\n{BOLD}Select an option:{RESET}")
    for key, scenario in scenarios.items():
        print(f"  {key}. {scenario['name']}  (expected: {scenario['expected']})")
    print("  6. Run ALL scenarios")
    print("  7. Reset test data (preset events, OTPs, blocklist)")
    print("  8. Custom live event (real OTP via email)")
    print("  0. Exit")
    print()
    print("  Note: score 40+ is always CHALLENGE. BLOCK happens only after a")
    print("  failed/expired OTP, or if the user/phone is already blocklisted.")
    print()


def print_decision(action, result):
    color = DECISION_COLORS.get(action, "")
    print("\n" + "=" * 55)
    print(f"  DECISION:   {color}{BOLD}{action}{RESET}")
    print(f"  RISK SCORE: {result.get('risk_score', 'N/A')}/100")
    print(f"  REASON:     {result.get('reason', 'No reason provided')}")
    print("=" * 55)


def run_otp_challenge(user_id, email, phone, risk_score):
    """Sends a real OTP via the API, asks for it, and verifies it via the API."""
    print(f"\n{BOLD}Step-up verification required.{RESET}")
    try:
        sent = httpx.post(f"{API_URL}/send-otp",
                          json={"email": email, "user_id": user_id}, timeout=60.0)
        if sent.status_code != 200:
            print("[ERROR] Could not send OTP email. SIM change denied for safety.")
            return
        otp_id = sent.json()["otp_id"]
        print(f"An OTP has been sent to {email} (valid for 5 minutes).")
        entered = input("Enter the OTP you received: ").strip()

        verify = httpx.post(f"{API_URL}/verify-otp", json={
            "otp_id": otp_id,
            "entered_otp": entered,
            "risk_score": risk_score,
            "user_id": user_id,
            "phone": phone,
            "email": email,
        }, timeout=60.0)
        final = verify.json()
        action = final.get("action", "UNKNOWN")
        color = DECISION_COLORS.get(action, "")
        print(f"\n  FINAL DECISION: {color}{BOLD}{action}{RESET}")
        print(f"  {final.get('reason', '')}")
    except httpx.HTTPError as e:
        print(f"\n[ERROR] {e}")


def run_scenario(key, scenarios):
    scenario = scenarios[key]
    event = scenario["event"]
    expected = scenario["expected"]

    print("\n" + "-" * 55)
    print(f"{BOLD}Scenario: {scenario['name']}{RESET}")
    print(f"User:      {event['user_id']}")
    print(f"Time:      {event['timestamp']}")
    print(f"Country:   {event['metadata'].get('country', 'N/A')}")
    print(f"Carrier:   {event['metadata'].get('new_carrier', 'N/A')}")
    print(f"Expected:  {expected}")
    print("-" * 55)
    print("Sending to agent... (this may take 30-90 seconds)")

    try:
        response = httpx.post(f"{API_URL}/event", json=event, timeout=180.0)
        result = response.json()
        action = result.get("action", "UNKNOWN")
        print_decision(action, result)
        ok = action == expected
        color = "\033[92m" if ok else "\033[91m"
        print(f"  MATCH: {color}{'CORRECT' if ok else 'UNEXPECTED'}{RESET}")
        return ok
    except httpx.TimeoutException:
        print("\n[ERROR] Request timed out.")
    except Exception as e:
        print(f"\n[ERROR] {e}")
    return False


def run_custom_event():
    print(f"\n{BOLD}--- Custom Live Event (Real OTP) ---{RESET}")
    print("Enter your details:\n")

    phone = input("Phone number: ").strip()
    email = input("Email address (OTP will be sent here): ").strip()
    country = input("Country code (e.g. IN, US, CN): ").strip().upper() or "IN"
    carrier = input("New carrier name (e.g. Airtel, Verizon): ").strip() or "Airtel"

    print("\nChoose event time:")
    print("  1. Business hours (2 PM)")
    print("  2. Late night (3 AM)")
    print("  3. Evening (8 PM)")
    time_choice = input("Enter 1, 2 or 3: ").strip()

    time_map = {
        "1": "2026-07-14T14:00:00",
        "2": "2026-07-14T03:00:00",
        "3": "2026-07-14T20:00:00",
    }
    timestamp = time_map.get(time_choice, "2026-07-14T14:00:00")
    # Same ID scheme as the web UI: one stable ID per phone number
    user_id = "user_" + "".join(ch for ch in phone if ch.isdigit())

    event = {
        "user_id": user_id,
        "event_type": "sim_change",
        "timestamp": timestamp,
        "metadata": {"country": country, "new_carrier": carrier, "phone": phone, "email": email}
    }

    print(f"\n{BOLD}Sending to agent...{RESET} (this may take 30-90 seconds)\n")

    try:
        response = httpx.post(f"{API_URL}/event", json=event, timeout=180.0)
        result = response.json()
        action = result.get("action", "UNKNOWN")
        print_decision(action, result)
        if action == "CHALLENGE":
            run_otp_challenge(user_id, email, phone, result.get("risk_score", 0))
        elif action == "ALLOW":
            print(f"\n{DECISION_COLORS['ALLOW']}{BOLD}SIM change approved.{RESET}")
        elif action == "BLOCK":
            print(f"\n{DECISION_COLORS['BLOCK']}{BOLD}SIM change blocked. Account flagged.{RESET}")
    except httpx.TimeoutException:
        print("\n[ERROR] Request timed out.")
    except Exception as e:
        print(f"\n[ERROR] {e}")


def reset_test_data():
    """Removes preset-scenario events and clears OTPs and the blocklist."""
    confirm = input("This deletes preset events, ALL OTP records and the whole "
                    "blocklist. Type 'yes' to continue: ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
        return
    from database import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM events WHERE user_id LIKE ?", (PRESET_PREFIX + "%",))
    events_removed = cur.rowcount
    cur.execute("DELETE FROM otp_attempts")
    cur.execute("DELETE FROM blocked_users")
    conn.commit()
    conn.close()
    print(f"\nRemoved {events_removed} preset event(s), cleared OTPs and blocklist.")


def main():
    print_banner()

    while True:
        scenarios = get_scenarios()
        print_menu(scenarios)
        choice = input("Enter your choice (0-8): ").strip()

        if choice == "0":
            print("\nExiting. Goodbye!\n")
            break
        elif choice in scenarios:
            run_scenario(choice, scenarios)
        elif choice == "6":
            print(f"\n{BOLD}Running all 5 scenarios...{RESET}")
            correct = sum(run_scenario(key, scenarios) for key in scenarios)
            print(f"\n{BOLD}All scenarios complete: {correct}/{len(scenarios)} matched expected.{RESET}")
        elif choice == "7":
            reset_test_data()
        elif choice == "8":
            run_custom_event()
        else:
            print("Invalid choice. Please enter 0-8.")

        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
