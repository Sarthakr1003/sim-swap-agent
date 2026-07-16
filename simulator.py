import httpx
import json
from datetime import datetime

API_URL = "http://127.0.0.1:8000"

DECISION_COLORS = {
    "ALLOW":     "\033[92m",
    "CHALLENGE": "\033[93m",
    "BLOCK":     "\033[91m",
}
RESET = "\033[0m"
BOLD  = "\033[1m"


def get_scenarios():
    """Generate scenarios with unique user IDs each run to ensure clean history."""
    ts = datetime.now().strftime("%H%M%S")
    return {
        "1": {
            "name": "Normal SIM Change",
            "expected": "ALLOW",
            "event": {
                "user_id": f"user_001_{ts}",
                "event_type": "sim_change",
                "timestamp": "2026-06-18T14:30:00",
                "metadata": {"country": "IN", "new_carrier": "Airtel"}
            }
        },
        "2": {
            "name": "Late Night SIM Change",
            "expected": "CHALLENGE",
            "event": {
                "user_id": f"user_002_{ts}",
                "event_type": "sim_change",
                "timestamp": "2026-06-18T03:15:00",
                "metadata": {"country": "IN", "new_carrier": "Airtel"}
            }
        },
        "3": {
            "name": "Foreign IP + SIM Change",
            "expected": "CHALLENGE",
            "event": {
                "user_id": f"user_003_{ts}",
                "event_type": "sim_change",
                "timestamp": "2026-06-18T11:00:00",
                "metadata": {"country": "US", "new_carrier": "Airtel"}
            }
        },
        "4": {
            "name": "Multi-Event Spike",
            "expected": "BLOCK",
            "event": {
                "user_id": f"user_004_{ts}",
                "event_type": "sim_change",
                "timestamp": "2026-06-18T02:45:00",
                "metadata": {"country": "US", "new_carrier": "Verizon"}
            }
        },
        "5": {
            "name": "Repeated SIM Swaps",
            "expected": "BLOCK",
            "event": {
                "user_id": f"user_005_{ts}",
                "event_type": "sim_change",
                "timestamp": "2026-06-18T04:00:00",
                "metadata": {"country": "CN", "new_carrier": "T-Mobile"}
            }
        }
    }


def print_banner():
    print("\n" + "="*55)
    print(f"{BOLD}   SIM-SWAP FRAUD DETECTION AGENT - CLI SIMULATOR{RESET}")
    print("="*55)


def print_menu(scenarios):
    print(f"\n{BOLD}Select a scenario to simulate:{RESET}")
    for key, scenario in scenarios.items():
        print(f"  {key}. {scenario['name']}  (expected: {scenario['expected']})")
    print("  6. Run ALL scenarios")
    print("  7. Clear event log")
    print("  8. Custom event (live input)")
    print("  0. Exit")
    print()


def run_scenario(key, scenarios):
    scenario = scenarios[key]
    name     = scenario["name"]
    expected = scenario["expected"]
    event    = scenario["event"]

    print(f"\n" + "-"*55)
    print(f"{BOLD}Scenario: {name}{RESET}")
    print(f"User:      {event['user_id']}")
    print(f"Time:      {event['timestamp']}")
    print(f"Country:   {event['metadata'].get('country', 'N/A')}")
    print(f"Carrier:   {event['metadata'].get('new_carrier', 'N/A')}")
    print(f"Expected:  {expected}")
    print("-"*55)
    print("Sending to agent... (this may take 30-90 seconds)")

    try:
        response = httpx.post(
            f"{API_URL}/event",
            json=event,
            timeout=180.0
        )
        result = response.json()

        action     = result.get("action", "UNKNOWN")
        risk_score = result.get("risk_score", "N/A")
        reason     = result.get("reason", "No reason provided")
        color      = DECISION_COLORS.get(action, "")

        print(f"\n" + "="*55)
        print(f"  DECISION:   {color}{BOLD}{action}{RESET}")
        print(f"  RISK SCORE: {risk_score}/100")
        print(f"  REASON:     {reason}")
        match = "CORRECT" if action == expected else "UNEXPECTED"
        match_color = "\033[92m" if action == expected else "\033[91m"
        print(f"  MATCH:      {match_color}{match}{RESET}")
        print("="*55)

    except httpx.TimeoutException:
        print("\n[ERROR] Request timed out - agent took too long to respond.")
        print("Make sure uvicorn is running and Ollama is active.")
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")


def run_custom_event():
    print(f"\n{BOLD}--- Custom Live Event ---{RESET}")
    print("Enter details for your custom account event:\n")

    user_id = input("User ID (e.g. user_123): ").strip() or "user_custom"
    country = input("Country code (e.g. IN, US, CN, GB): ").strip().upper() or "IN"
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

    event = {
        "user_id": user_id,
        "event_type": "sim_change",
        "timestamp": timestamp,
        "metadata": {
            "country": country,
            "new_carrier": carrier
        }
    }

    print(f"\n{BOLD}Sending custom event to agent...{RESET}")
    print(f"User: {user_id} | Country: {country} | Carrier: {carrier} | Time: {timestamp}")
    print("(this may take 30-90 seconds)\n")

    try:
        response = httpx.post(
            f"{API_URL}/event",
            json=event,
            timeout=180.0
        )
        result = response.json()

        action     = result.get("action", "UNKNOWN")
        risk_score = result.get("risk_score", "N/A")
        reason     = result.get("reason", "No reason provided")
        color      = DECISION_COLORS.get(action, "")

        print("="*55)
        print(f"  DECISION:   {color}{BOLD}{action}{RESET}")
        print(f"  RISK SCORE: {risk_score}/100")
        print(f"  REASON:     {reason}")
        print("="*55)

    except httpx.TimeoutException:
        print("\n[ERROR] Request timed out.")
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")


def main():
    print_banner()

    while True:
        scenarios = get_scenarios()
        print_menu(scenarios)
        choice = input("Enter your choice (0-8): ").strip()

        if choice == "0":
            print("\nExiting simulator. Goodbye!\n")
            break
        elif choice in scenarios:
            run_scenario(choice, scenarios)
        elif choice == "6":
            with open("data/events_log.json", "w") as f:
                json.dump([], f)
            print(f"\n{BOLD}Log cleared. Running all 5 scenarios with fresh users...{RESET}")
            fresh = get_scenarios()
            for key in fresh:
                run_scenario(key, fresh)
            print(f"\n{BOLD}All scenarios complete.{RESET}")
        elif choice == "7":
            with open("data/events_log.json", "w") as f:
                json.dump([], f)
            print("\nLog cleared successfully.")
        elif choice == "8":
            run_custom_event()
        else:
            print("Invalid choice. Please enter 0-8.")

        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()