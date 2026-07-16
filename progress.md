# SIM-Swap Fraud Agent — Progress Log

**Project:** SIM-Swap Fraud Detection Agent
**AI Focus:** Agentic AI
**Stack:** Python + FastAPI + Ollama (Llama 3.1 8B) — fully local, no cloud, no API key
**Folder:** `C:\MY PROJECTS\SIM-SWAP-AGENT`
**Timeline:** 1 Week

---

## ✅ Step 1 — Project Setup (COMPLETE)

- [x] Created project folder: `C:\MY PROJECTS\SIM-SWAP-AGENT`
- [x] Created virtual environment: `python -m venv venv`
- [x] Activated venv (had to run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first to fix PowerShell script block)
- [x] Created `requirements.txt` with: `fastapi`, `uvicorn`, `pydantic`, `httpx`, `ollama`
  - (Removed `anthropic` and `python-dotenv` — going pure Ollama/local, no API key needed)
- [x] Ran `pip install -r requirements.txt` — all installed successfully
- [x] Created empty files: `main.py`, `agent.py`, `tools.py`, `models.py`, `simulator.py`
- [x] Created `data/` folder (will hold `events_log.json`)
- [x] Skipped `.env` file — not needed since no API key is used
- [x] Installed Ollama (v0.30.8) from ollama.com
- [x] Pulled model: `ollama pull llama3.1:8b` (4.9 GB, success)
- [x] Verified model works: `ollama run llama3.1:8b` → got a working response → exited with `/bye`

**Decisions made:**
- Going **pure Ollama / local-only** instead of Claude API — free, unlimited testing, no API key, runs entirely on local PC, no cloud involved.
- Project folder and venv are local-only; Ollama model itself is stored separately in Ollama's own managed folder (not inside the project folder) — this is normal and expected.

---

## ⬜ Step 2 — Data Models (`models.py`) — NEXT UP

- [ ] Define `AccountEvent` model (user_id, event_type, timestamp, metadata)
- [ ] Define `FraudDecision` model (action, risk_score, reason)
- [ ] Define `VerificationRequest` model (user_id, method)
- [ ] Test models with sample data

---

## ⬜ Step 3 — Agent Tools (`tools.py`)

- [ ] `check_account_history(user_id)` — reads recent events from `events_log.json`
- [ ] `calculate_risk_score(event)` — heuristic scorer, 0–100
- [ ] `trigger_verification(user_id, method)` — logs/simulates step-up verification
- [ ] Test each tool individually

---

## ⬜ Step 4 — The Agent (`agent.py`)

- [ ] Define tool schemas for Ollama/Llama 3.1 tool-calling format
- [ ] Write `run_fraud_agent(event)` — core agentic loop
- [ ] Loop: send event → model calls tool → run tool → send result back → repeat until decision
- [ ] Add validation/retry logic (Llama 3.1 8B tool-calling is less reliable than Claude — expect to need fallback handling)
- [ ] Test loop manually with sample events

---

## ⬜ Step 5 — FastAPI Backend (`main.py`)

- [ ] `POST /event` — run agent, return `FraudDecision`
- [ ] `GET /events/{user_id}` — return event history
- [ ] `GET /health` — status check
- [ ] Run server: `uvicorn main:app --reload`
- [ ] Test via `/docs` interactive page

---

## ⬜ Step 6 — CLI Simulator (`simulator.py`)

- [ ] Build scenario menu (1–5)
- [ ] Scenario 1: Normal SIM change → expect ALLOW
- [ ] Scenario 2: Late night SIM change → expect CHALLENGE
- [ ] Scenario 3: Foreign IP + SIM change → expect CHALLENGE
- [ ] Scenario 4: Multi-event spike (2 hrs) → expect BLOCK
- [ ] Scenario 5: Repeated SIM swaps (24h) → expect BLOCK + flag
- [ ] Use `httpx` to POST to local FastAPI server, pretty-print results

---

## ⬜ Step 7 — Testing & Polish

- [ ] Run all 5 scenarios end-to-end, verify decisions match expectations
- [ ] Add error handling throughout (agent loop, API endpoints, file reads)
- [ ] Write `README.md` (setup, how to run, sample output)
- [ ] Optional: add `GET /stats` endpoint summarizing decision counts

---

## Notes / Reminders

- Ollama must be running in the background (`ollama serve` or it auto-runs after install) before testing `agent.py` or the API.
- Model used: `llama3.1:8b` — fully local, free, no internet required after initial download.
- If Llama's tool-calling proves too unreliable during Step 4, fallback plan discussed: could test logic against Claude API temporarily (would need to re-add `anthropic` + `.env` at that point).
