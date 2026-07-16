import ollama
import json
from models import AccountEvent
from tools import calculate_risk_score, check_account_history, trigger_verification, log_event

MODEL = "llama3.1:8b"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_account_history",
            "description": "Get recent account change events for a user, to see if anything suspicious happened before. Always call this FIRST.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The user ID to check history for"}
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_risk_score",
            "description": "Calculate a fraud risk score (0-100) for the current account event based on time, location, and carrier signals. Always call this SECOND, after checking history.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_verification",
            "description": "Send a step-up verification challenge (OTP or identity check) to the user. Only call this if the risk score from calculate_risk_score was 40 or higher.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "method": {"type": "string", "description": "'otp' or 'identity_check'"}
                },
                "required": ["user_id", "method"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are a fraud detection agent monitoring account change events (like SIM swaps).

You MUST use tools to investigate - never make up or guess any data. Only refer to numbers and facts that came directly from a tool result.

Steps:
1. Call check_account_history to see real past events for this user.
2. Call calculate_risk_score to get the REAL numeric risk score. Do not invent your own score.
3. If the real risk score from the tool is 40 or higher, call trigger_verification.
4. Stop calling tools once you have done the above. Do not call any tool more than once.

Keep your reasoning brief - 2 sentences maximum. Only state facts that came from actual tool results, never invented details.
"""


def run_fraud_agent(event: AccountEvent, debug: bool = True):
    """
    The core agentic loop. The model decides which tools to call and when.
    The FINAL decision is grounded in the real calculate_risk_score result
    we captured ourselves - not the model's possibly-hallucinated text -
    so the system stays genuinely agentic but the outcome stays reliable.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"New account event:\n{event.model_dump_json()}"}
    ]

    current_event = event
    max_turns = 6
    real_risk_result = None       # we will capture the REAL score here
    verification_triggered = False
    called_tools = set()

    for turn in range(max_turns):
        response = ollama.chat(model=MODEL, messages=messages, tools=TOOLS)
        msg = response["message"]
        messages.append(msg)

        if debug:
            print(f"\n=== Model response (turn {turn+1}) ===")
            print(msg.get("content", "(no text content)"))

        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            if debug:
                print(">>> No more tool calls. Finalizing with real data.")
            break

        if debug:
            print(f"--- Turn {turn+1}: {len(tool_calls)} tool call(s) ---")

        for call in tool_calls:
            fn_name = call["function"]["name"]
            args = call["function"]["arguments"]

            if fn_name in called_tools and fn_name != "trigger_verification":
                if debug:
                    print(f"  Skipping duplicate call to {fn_name}")
                result = {"info": "already called, see previous result"}
            elif fn_name == "check_account_history":
                result = check_account_history(args.get("user_id", current_event.user_id))
                called_tools.add(fn_name)
            elif fn_name == "calculate_risk_score":
                result = calculate_risk_score(current_event)
                real_risk_result = result          # <-- capture the REAL score
                called_tools.add(fn_name)
            elif fn_name == "trigger_verification":
                result = trigger_verification(args.get("user_id", current_event.user_id), args.get("method", "otp"))
                verification_triggered = True
                called_tools.add(fn_name)
            else:
                result = {"error": f"Unknown tool {fn_name}"}

            if debug:
                print(f"  Tool: {fn_name} | args: {args} | REAL result: {result}")

            messages.append({
                "role": "tool",
                "content": json.dumps(result)
            })

    # ---- GROUND THE FINAL DECISION IN REAL DATA, not the model's free text ----
    if real_risk_result is None:
        # Model never actually called the risk scorer - calculate it ourselves as a safety net
        real_risk_result = calculate_risk_score(current_event)
        if debug:
            print(">>> Model never called calculate_risk_score. Computing it directly as a fallback.")

    score = real_risk_result["score"]
    reasons = real_risk_result["reasons"]

    if score >= 70:
        action = "BLOCK"
    elif score >= 40:
        action = "CHALLENGE"
    else:
        action = "ALLOW"

    reason_text = "; ".join(reasons) if reasons else "No risk factors detected."

    return {
        "action": action,
        "risk_score": score,
        "reason": reason_text,
        "verification_triggered": verification_triggered
    }