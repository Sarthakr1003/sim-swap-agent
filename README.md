# SIM-Swap Fraud Detection Agent

An agentic AI system that detects SIM-swap fraud. A locally run LLM (Llama 3.1 8B via Ollama) receives an account-change event, decides which tools to call (account history, risk scoring, verification), and the system returns **ALLOW**, **CHALLENGE** or **BLOCK**. Step-up verification is a real email OTP sent through Gmail SMTP. All LLM inference runs on your own machine.

> The system uses LLM-driven reasoning for tool orchestration, but validates and grounds final decisions in deterministic tool outputs to mitigate hallucination.

Built by Sarthak Ramachandra (B.Tech AI & ML, Dayananda Sagar University) as an RTD / capstone project.

## How it works

1. An event reaches `POST /event` from the web UI, the CLI simulator or the carrier monitor.
2. Pydantic validates it into an `AccountEvent`.
3. Pre-checks: if the user ID or phone number is on the blocklist, the answer is BLOCK at once. If the user has 3 or more BLOCK records in the last 10 minutes, they are blocklisted.
4. `run_fraud_agent` gives the event and three tool schemas to Llama 3.1 8B. The model calls `check_account_history`, then `calculate_risk_score`, then `trigger_verification` if the score is 40 or more.
5. **Grounded decision:** the host code keeps the real output of `calculate_risk_score` and ignores the model's free text. The action comes only from that score. If the model never calls the scorer, the host calls it directly.
6. The event is stored in SQLite and the decision is returned.
7. On CHALLENGE, the client calls `/send-otp`. A 6-digit OTP is emailed, and only its SHA-256 hash is stored, with a 5-minute expiry. The user enters it and `/verify-otp` returns ALLOW (correct) or BLOCK (wrong, expired or already used). On BLOCK the user and phone are blocklisted and a security-alert email goes to the account's email address.

### Why the grounded decision matters

During testing, Llama 3.1 8B claimed a user had "5 SIM changes" when the real history tool had returned an empty list. Because the final action is computed from the tool output and never from the model's text, that hallucination cannot change the decision.

## Decision rules

| Risk score | Result |
|---|---|
| 0-39 | ALLOW |
| 40-100 | CHALLENGE (email OTP) |
| Wrong / expired / reused OTP | BLOCK + blocklist + alert email |
| User or phone already blocklisted | BLOCK |

A high score is never blocked straight away. A legitimate user changing SIM abroad at midnight can still prove who they are, which avoids that false positive.

## Risk scoring (`tools.py`)

| Factor | Points |
|---|---|
| Event hour is 11 PM to 5 AM | +25 |
| `country` given and not `IN` | +25 |
| 2 or more previous account changes for this user | +20 |
| `new_carrier` given | +15 |
| No previous account changes for this user | +10 |

The total is capped at 100. History comes from the `events` table in SQLite (OTP-verification rows are excluded).

## Test scenarios (CLI simulator)

Each preset uses a fresh user ID, so there is no history and the "no prior history" factor applies.

| # | Scenario | Score | Expected |
|---|---|---|---|
| 1 | Normal (IN, 2 PM, Airtel) | 15 + 10 = 25 | ALLOW |
| 2 | Late night (IN, 3 AM) | 25 + 15 + 10 = 50 | CHALLENGE |
| 3 | Foreign (US, 11 AM) | 25 + 15 + 10 = 50 | CHALLENGE |
| 4 | Foreign + night (US, 2:45 AM, Verizon) | 25 + 25 + 15 + 10 = 75 | CHALLENGE, BLOCK on wrong OTP |
| 5 | Foreign + night (CN, 4 AM, T-Mobile) | 25 + 25 + 15 + 10 = 75 | CHALLENGE, BLOCK on wrong OTP |

## Tech stack

Python 3.14, FastAPI + uvicorn, Pydantic, httpx, Ollama + Llama 3.1 8B, SQLite, Gmail SMTP (`smtplib` with an App Password), python-dotenv, requests, Abstract API Phone Intelligence (carrier lookup), single-file HTML/CSS/JS web UI.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | FastAPI app and all endpoints |
| `agent.py` | Agent loop: max 6 turns, duplicate-call guard, grounded decision, scorer fallback |
| `tools.py` | `check_account_history`, `calculate_risk_score`, `trigger_verification` |
| `database.py` | SQLite layer (`data/sim_swap.db`): events, OTPs, blocklist |
| `otp_service.py` | OTP generation, OTP email, block-alert email, final decision |
| `monitor.py` | Polls registered numbers for carrier changes and fires `/event` on a change |
| `simulator.py` | CLI with 5 preset scenarios and a live event with a real email OTP |
| `models.py` | Pydantic models |
| `templates/index.html` | Web UI (dark/light theme) |
| `.env.example` | Template for the secrets file |

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Web UI |
| GET | `/health` | Health check |
| POST | `/event` | Run fraud detection on an event |
| GET | `/events/all` | All stored events |
| GET | `/events/{user_id}` | Events for one user |
| GET | `/stats` | ALLOW / CHALLENGE / BLOCK counts |
| POST | `/send-otp` | Email an OTP, returns only its `otp_id` |
| POST | `/verify-otp` | Check an OTP and return the final decision |
| POST | `/register` | Register a phone number for carrier monitoring |

Example event:

```json
{
  "user_id": "user_919876543210",
  "event_type": "sim_change",
  "timestamp": "2026-07-14T03:00:00",
  "metadata": {"country": "US", "new_carrier": "Verizon", "phone": "+919876543210", "email": "you@example.com"}
}
```

## Setup (Windows)

1. Install [Ollama](https://ollama.com) and pull the model: `ollama pull llama3.1:8b`
2. Create the virtual environment and install dependencies:
   ```powershell
   cd "C:\MY PROJECTS\SIM-SWAP-AGENT"
   python -m venv venv
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your Gmail address, a Gmail App Password, and (for monitoring) an Abstract API Phone Intelligence key.

## Running

Terminal 1, the server:

```powershell
cd "C:\MY PROJECTS\SIM-SWAP-AGENT"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
venv\Scripts\Activate.ps1
uvicorn main:app --reload
```

Open http://127.0.0.1:8000 for the web UI.

Terminal 2 (same first three lines), then one of:

- `python simulator.py`: option 6 runs all presets, option 8 runs a live event with a real OTP, option 7 resets test data and the blocklist.
- `python monitor.py`: checks registered numbers every 5 minutes. `python monitor.py --once` runs a single check.

Each event takes roughly 30-90 seconds on CPU-only local inference.

## Limitations

- Real carrier SIM-swap signals need carrier partnerships. Here events come from the UI/simulator, and `monitor.py` can only notice a carrier change by polling a lookup API, not a real-time SIM swap.
- Carrier lookup cannot tell where the new SIM is used, so monitor events carry no country.
- The risk scorer is a fixed heuristic; attackers can adapt to static rules.
- Email OTP is safer than SMS OTP here (an attacker who has the SIM gets the SMS), but an authenticator app would be stronger.
- The API has no authentication, and `/verify-otp` trusts the client-supplied risk score. Fine for a local prototype, not for production.
- SQLite and a single process do not scale. CPU-only inference takes tens of seconds per event.

## Future scope

Multi-agent architecture, carrier webhook integration, authenticator-app or push verification, precision/recall/F1 evaluation on a labelled dataset, per-user trust scores, API authentication, PostgreSQL, and cloud deployment.
