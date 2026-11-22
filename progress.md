# SIM-Swap Fraud Detection Agent: Full Progress Log

**Student:** Sarthak Ramachandra | **USN:** ENG23AM0185 | B.Tech AI & ML, Dayananda Sagar University, 2023-2027
**Project type:** Agentic AI (RTD / capstone-style project)
**Repo:** https://github.com/Sarthakr1003/sim-swap-agent (branch `main`)
**Project folder (Windows):** `C:\MY PROJECTS\SIM-SWAP-AGENT`
**Log last updated:** 22 Nov 2026 (code cleanup)

> Redaction note: API keys, passwords, tokens and phone numbers from the chat are deliberately NOT written here, because this file lives inside the git repo. See "Security" below.

---

## 1. What the project is

An agentic AI system that detects SIM-swap fraud. A locally-run LLM (Llama 3.1 8B via Ollama) receives an account-change event, autonomously calls tools (account history, risk scoring, verification), and the system issues ALLOW / CHALLENGE / BLOCK. Step-up verification is a real email OTP via Gmail SMTP. Everything runs locally with no cloud inference.

**One-line expected outcome:** A working local agentic fraud detection system that classifies SIM-swap events into ALLOW / CHALLENGE / BLOCK, with a hallucination-mitigation strategy (grounded decisions).

**Key presentation line:** "The system uses LLM-driven reasoning for tool orchestration, but validates and grounds final decisions in deterministic tool outputs to mitigate hallucination."

## 2. Tech stack

Python 3.14, FastAPI + uvicorn, Pydantic, httpx, Ollama + Llama 3.1 8B (4.9 GB, local), SQLite, Gmail SMTP (`smtplib`, App Password), `python-dotenv`, `requests`, Abstract API Phone Intelligence (carrier lookup), HTML/CSS/JS web UI (single file). `twilio` is installed but Twilio is not used in the final flow. Jinja2 was installed then removed.

## 3. File map

| File | Purpose |
|---|---|
| `models.py` | Pydantic models: `AccountEvent` (user_id, event_type, timestamp auto-parsed to datetime, metadata dict), `FraudDecision` (action, risk_score, reason), `VerificationRequest` |
| `tools.py` | `check_account_history`, `calculate_risk_score`, `trigger_verification(user_id, method, email=None)`, `log_event`, `_load_log/_save_log` (JSON, legacy) |
| `agent.py` | Agentic loop (max 6 turns, duplicate-call guard, grounded decision via `real_risk_result`, fallback if the model never calls the scorer) |
| `main.py` | FastAPI app and endpoints (see section 7) |
| `database.py` | SQLite layer (`data/sim_swap.db`): events, otp_attempts, blocked_users + helpers |
| `otp_service.py` | `generate_otp`, `send_otp_email`, `send_block_alert_email`, `verify_otp` (legacy string compare), `get_final_decision` |
| `monitor.py` | Carrier-change monitor: `monitored_numbers` table, Abstract API lookup (Twilio fallback), polls every 300 s, fires `/event` on change |
| `simulator.py` | CLI: 5 preset scenarios, run-all, clear log, custom live event with real email OTP |
| `templates/index.html` | Web UI (dark/light toggle) |
| `.env` | Secrets (git-ignored); `.env.example` is the committed template |
| `.gitignore` | venv/, __pycache__/, *.pyc, .env, data/ (the SQLite DB is no longer tracked) |
| `progress.md`, `README.md`, `requirements.txt` | Docs/deps |

## 4. How it works (data flow)

1. Event arrives at `POST /event` (from web form, CLI simulator, or `monitor.py`).
2. Pydantic validates it into an `AccountEvent`.
3. Pre-checks: blocklist (user_id OR phone) returns BLOCK/100 immediately; rate limit (3+ BLOCK rows for the user_id in 10 min) permanently blocks.
4. `run_fraud_agent` sends the event to Llama 3.1 8B with tool schemas. The model calls `check_account_history`, then `calculate_risk_score`, then (if score >= 40) `trigger_verification`.
5. The host code captures the real scorer output in `real_risk_result` and ignores the model's free text. Final action comes only from this score.
6. Event is logged to SQLite and returned.
7. If CHALLENGE, the web UI calls `/send-otp` (real email, hashed OTP stored with 5-minute expiry), the user enters the OTP, and `/verify-otp` returns ALLOW (correct) or BLOCK (wrong/expired/used). BLOCK adds the user to `blocked_users` and sends a security alert email.

## 5. Decision logic, and how it evolved

- **Original:** 0-39 ALLOW, 40-69 CHALLENGE, 70-100 BLOCK (direct).
- **Problem raised by the student:** a legitimate user swapping SIM at midnight abroad would be blocked with no way to prove identity (false positive).
- **Fix (current):** 0-39 ALLOW; 40-100 CHALLENGE; BLOCK only after failed/expired OTP (or blocklist/rate-limit). Standard step-up authentication pattern.

## 6. Risk scoring (actual code in `tools.py`)

| Factor | Points |
|---|---|
| Event hour >= 23 or < 5 | +25 |
| `country` present and != "IN" | +25 |
| 2+ prior events in history | +20 |
| `new_carrier` present | +15 |
| No prior history | +10 |

Capped at 100. History is read from the SQLite `events` table (OTP-verification rows excluded). With exactly one prior event neither the +20 nor the +10 applies. Test scenario math: S1 15+10=25; S2 25+15+10=50; S3 25+15+10=50; S4 25+25+15+10=75; S5 25+25+15+10=75.
(An earlier draft also listed "3+ swaps in 24h (+15)". That rule does NOT exist in the code.)

## 7. API endpoints (current `main.py`)

`GET /` (web UI via `open()`), `GET /health`, `POST /event`, `GET /events/all` (must be declared before the `{user_id}` route), `GET /events/{user_id}`, `GET /stats`, `POST /send-otp` (returns only `otp_id`), `POST /verify-otp` (OTP must belong to the same user_id; single-use, even when wrong), `POST /register` (phone monitoring registration).
Early revision answer for the "3 endpoints" question: `GET /health`, `POST /event`, `GET /events/{user_id}`.

## 8. Database (SQLite, `data/sim_swap.db`)

- `events`: id, user_id, phone, event_type, timestamp, country, new_carrier, risk_score, action, reason, otp_verified, created_at
- `otp_attempts`: id, user_id, otp_hash (SHA-256), expires_at, used, created_at
- `blocked_users`: id, user_id, phone, reason, blocked_at
- `monitored_numbers` (created by `monitor.py`): phone (unique), email, user_id, last_carrier, last_checked, registered_at

## 9. Test results

**5 preset scenarios, 5/5 correct (100%):**

| # | Scenario | Score | Decision |
|---|---|---|---|
| 1 | Normal (IN, 2 PM, Airtel) | 25 | ALLOW |
| 2 | Late night (IN, 3 AM) | 50 | CHALLENGE |
| 3 | Foreign (US, 11 AM) | 50 | CHALLENGE |
| 4 | Multi-event (US, 3 AM, Verizon) | 75 | CHALLENGE, then BLOCK on wrong OTP |
| 5 | Repeated swaps (CN, 4 AM, T-Mobile) | 75 | CHALLENGE, then BLOCK on wrong OTP |

**Live manual tests that passed:** real OTP email arrived and a correct OTP gave ALLOW; a wrong OTP gave BLOCK plus a security-alert email; expired/used OTP handling; blocklist re-block on the same phone; Abstract API returned Airtel for an Indian number; registration stored the carrier. Web UI showed stats (e.g. 20 total / 7 allow / 8 challenge / 5 block at one point) and the history table.

## 10. Build timeline (chronological)

1. **Setup:** venv, deps, Ollama + Llama 3.1 8B, folders. PowerShell needs `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in every new window.
2. **Models, tools, agent loop, FastAPI, CLI simulator**, all tested.
3. **Key engineering finding (hallucination):** Llama 3.1 8B claimed "5 SIM changes" when the real tool result was `[]`. Found by printing real tool output against model text. Fixed with the **grounded decision pattern**.
4. **First project review presented** (status: went well). The professor asked for improvements by the next review.
5. **GitHub:** repo already existed locally; first commit pushed (see section 12).
6. **Real email OTP** (Gmail App Password in `.env`), replacing the simulated verification.
7. **Web frontend** (dark/light), `/events/all`, `/send-otp`.
8. **False-positive fix:** BLOCK only after failed OTP; `/verify-otp` endpoint; `get_final_decision`.
9. **SQLite database, OTP expiry (5 min), rate limiting, blocklist**, OTP countdown timer in UI, verify button disabled after success.
10. **Phone monitoring:** Twilio Lookup returned carrier `None` for Indian numbers (error 10002 on trial), so switched to Abstract **Phone Intelligence** API (`phoneintelligence.abstractapi.com/v1`, response field `phone_carrier.name`). Registration then showed Airtel.
11. **Alert email on BLOCK** (`send_block_alert_email`), working after passing `email` from the UI to `/verify-otp`.
12. **Documents:** research paper and patent drafted (see section 14).

## 11. Problems hit and how they were fixed

- `tools.py` edit "didn't save": pasted full file instead of partial edits.
- Files created in the wrong folder (`C:\Users\sarth`): always `cd` into the project and activate venv first.
- Garbled characters (`â€”`) when running `type`: PowerShell display only, harmless.
- `simulator.py` / `index.html` truncated or SyntaxError after Notepad paste: re-sent complete files; later generated `index.html` as a downloadable file instead.
- Jinja2 `TypeError: cannot use 'tuple' as a dict key` on Python 3.14: removed Jinja2, serve HTML with `open()`.
- `main.py` still importing Jinja2 after uninstall: replaced with the clean version.
- Route clash `/events/all` vs `/events/{user_id}`: declare `/events/all` first.
- Verify clicked twice gave BLOCK (OTP already used): button disabled after success.
- Blocklist blocked the next test on the same phone: cleared `blocked_users`/`otp_attempts` with a short Python snippet (use a different phone number or clear the table).
- `.env` key name mismatch (`ABSTRACT_API` vs `ABSTRACT_API_KEY`): renamed.
- Abstract API 401: the dashboard key belonged to the Phone Intelligence product, not Phone Validation; use the Phone Intelligence endpoint.
- Twilio free trial could not provide a phone number (India) and Lookup carrier unsupported for IN.
- Security alert email missing: frontend wasn't sending `email` in the verify request; fixed.

## 12. Git / GitHub

Commits pushed: `b2a26c7` (initial, 9 files), `c4ddc11` (real email OTP), `33d471c` (web frontend), `302f4d3` (BLOCK only after failed OTP), then later pushes for SQLite/OTP expiry/rate limiting, verify-button fix, and alert email/phone monitoring. Standard flow: `git add .` -> `git commit -m "..."` -> `git push`. The LF/CRLF warning is harmless. (`git commit` saves locally; `git push` uploads.)

## 13. Design decisions and discussion points (for viva)

- **Local vs cloud LLM:** Llama 3.1 8B via Ollama is free, private, offline, no API key. Ollama is the runtime; Llama 3.1 8B (Meta) is the model. One agent with three tools (single-agent, multi-tool). Multi-agent is future scope.
- **Why email OTP instead of SMS:** an attacker who has swapped the SIM receives SMS but not email, so email OTP is safer at detection time. The attack chain is SIM swap -> SMS OTP intercepted -> Gmail reset -> email OTP intercepted; real-time detection must stop it at step 1. Real banks also use authenticator apps, biometrics, callbacks.
- **Why a database:** concurrency, queries, OTP expiry, rate limiting, blocklist, trust scores.
- **"Why simulator?":** the agent, tools, backend and OTP are real; only the event source is manual, because carrier webhooks need business partnerships.
- **Making it real:** carrier webhook to `/event`, SMS/authenticator, PostgreSQL, API auth, cloud deployment (Ollama won't run on free tiers; options: Claude API mode, smaller model, tunnel, GPU rental), compliance.
- **Frontend/backend:** FastAPI backend; frontend was a CLI, now a web UI. PowerShell is used only because the dev machine is Windows.
- **Revision answers given:** GET vs POST (GET = just asking; POST = sending + asking); Pydantic = data validation of structure/types, not relevance; Twilio = SMS/phone API.

## 14. Presentation and documents produced

- Review PPT (10 slides, follows the required format: Title, Problem Statement, Objectives, Literature Survey, Methodology, Expected Outcomes, Demonstration, plus Future Scope and Thank You), with name and USN on slide 1. Earlier PPTs: progress PPT (9 slides), future-scope slide.
- 15-20 second per-slide speech, demo order (option 6, then option 8), proof-it's-local tips (127.0.0.1, `ollama.exe` in Task Manager, WiFi off).
- Cross-question prep PDF; 1-page and 4-page synopsis PDFs; Word synopsis pages; earlier progress.md.
- Evaluation rubric (10 marks): problem identification 2, literature survey and gap 2, objectives/methodology/technical understanding 2, presentation 2, demo/documentation/Q&A 2.
- Real papers/patents were NOT added to the PPT literature slide (fabricated references were declined). Slide 4 frames it as industry-approach survey plus gap.
- **Research paper:** `Research_Paper_SIM_Swap.docx` (Springer *Discover Computing* style; template was the QuantumEarthNet paper). **Needs corrections, see section 16.**
- **Patent Complete Specifications:** `Patent_CompleteSpecifications.docx` (filled from the provided template). **Needs corrections, see section 16.**

## 15. RTD submission requirements (from the faculty notice)

Final Project Report (departmental Capstone template; template NOT yet received), Research Paper, Patent document (Abstract, Complete Specification, Diagrams), plagiarism/similarity report. The submission form asks for: Project Report (PDF/doc, max 10 MB), GitHub link, Research Paper (PDF/doc, max 10 MB), NVIDIA certificate (optional upload). Documents must be technically consistent with the actual work done.

## 16. Known issues / honest discrepancies (fix before submitting)

**Code bugs/mismatches: all fixed on 22 Nov 2026 (branch `fix/final-cleanup`), see section 21.**

**Document inaccuracies I introduced (must remove or replace)**
- Research paper: invented hardware (Intel i7, 16 GB RAM, Windows 11, Q4_K_M), invented timings (47 s average, 31-78 s range, 312 ms API latency), "fallback triggered in 1 of 5 runs / ~15%", "variance = 0" style claims, and a sixth scoring factor that doesn't exist. Replace with supportable wording (CPU-only local inference, roughly 30-90 seconds per event as shown in the app).
- Research paper references that don't fit or are weak: word2vec (Mikolov), Anthropic model specification, Llama 2 as a stand-in. Replace with verified, relevant sources.
- Patent: the three US patent numbers (US10785326B2, US20190373466A1, US20200364729A1) and the "Nassiri et al." reference are unverified, probably wrong; replace with verified prior art. The 6-factor risk description in claim 2 should match the real 5-factor code. Claim wording about auto SIM-swap detection should stay limited to carrier-change polling.
- **Patent contact number:** it currently shows a number the student said belongs to someone very close to them (not necessarily theirs). Confirm the correct contact number before submission.

## 17. Security (do this before submitting the repo)

Credentials were pasted into the chat during development (Gmail App Password, Twilio Auth Token, Abstract API key, and Twilio SID visible in a screenshot). **Rotate all of them:** delete/recreate the Gmail App Password, regenerate the Twilio Auth Token, regenerate the Abstract API key. `.env` is in `.gitignore`; confirm on the GitHub repo page that no `.env` or database file is tracked. This progress.md is tracked by git, so never paste secrets or personal phone numbers into it.

## 18. Remaining work (priority order)

1. ~~Fix history lookup (SQLite) plus `requirements.txt` and README.~~ Done 22 Nov 2026.
2. Correct research paper and patent (remove invented numbers, fix references, match real code, fix contact number).
3. Get the departmental Project Report template, then write the Project Report.
4. Plagiarism/similarity report.
5. NVIDIA certificate (student uploads it).
6. Rotate keys. README is now accurate and the DB is untracked, but old commits still contain `data/sim_swap.db` (see section 21).
7. Optional enhancements (only claim them once built): multi-agent architecture, cloud deployment (Claude API mode), SMS/authenticator OTP, carrier webhook, precision/recall/F1 metrics, trust score, tune monitor events.
8. Finish revision: topics still pending are the data-flow explanation in the student's own words, future scope and limitations; then a mock Q&A.

## 19. Quick run guide

Terminal 1 (server):
```
cd "C:\MY PROJECTS\SIM-SWAP-AGENT"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
venv\Scripts\Activate.ps1
uvicorn main:app --reload
```
Open http://127.0.0.1:8000. Terminal 2 (same first three lines), then `python simulator.py` or `python monitor.py`. Ollama must be running with `llama3.1:8b` pulled. To reset blocks during testing: delete rows from `blocked_users` and `otp_attempts` in `data/sim_swap.db`.

## 20. Real-world limitations (for the report and viva)

Carrier API access needs partnerships; SMS OTP is the attack target (email is better here, authenticator best); static heuristics degrade as attackers adapt; no cross-institution visibility; LLM explainability for regulators; CPU-only latency (tens of seconds per event); SQLite and single process do not scale; the phone-lookup API detects carrier changes by polling, not true real-time swap events.

## 21. Code cleanup, 22 Nov 2026 (branch `fix/final-cleanup`)

- `tools.py`: `check_account_history` now reads SQLite via `get_user_events_db`, so the +20 / +10 history factors work for real. Old JSON log functions removed. `trigger_verification` only flags that verification is required; the OTP is generated and emailed by `/send-otp`, so the LLM never sees it.
- `main.py` / `database.py`: `/send-otp` no longer returns the OTP. `verify_otp_db` checks the OTP belongs to the submitting user_id, marks it used on any attempt, and compares hashes in constant time. BLOCK reasons now say why (wrong / expired / already used).
- `otp_service.py`: OTPs come from `secrets` instead of `random`; legacy `verify_otp` removed.
- Web UI: user_id is `user_<phone digits>` (stable per phone), so history and the rate limit carry over between events. The browser no longer holds the OTP.
- `simulator.py`: uses `/send-otp` and `/verify-otp` (same SQLite flow as the UI). Presets 4 and 5 now expect CHALLENGE (they were wrongly marked BLOCK). Option 7 resets preset events, OTPs and the blocklist (asks for confirmation). Option 6 prints an N/5 summary.
- `monitor.py`: no more fake `AUTO_DETECTED` country (it always added +25). `python monitor.py --once` runs one check cycle.
- `requirements.txt` pinned to the installed versions (adds python-dotenv, requests); `.env.example` added; README rewritten to match the code.
- `data/sim_swap.db` removed from git tracking and `data/` ignored. It still exists in commits `253b97f` and `4dfbad0` on GitHub, so the phone numbers/emails in it are still public in history until the history is rewritten.
- Tested with a fake LLM and fake email on a throwaway DB: history scoring 75/65/85 over three events, OTP not exposed, other user's OTP rejected, correct OTP ALLOW, wrong OTP BLOCK plus alert, blocklist re-block. Not yet re-run against real Ollama and Gmail.

