\# SIM-Swap Fraud Detection Agent



An Agentic AI system that monitors account change events, detects SIM-swap

fraud in real time, and triggers step-up verification workflows autonomously.

Runs 100% locally — no cloud, no API key, no cost.



\---



\## Tech Stack



\- \*\*Python 3.10+\*\*

\- \*\*FastAPI\*\* — REST API backend

\- \*\*Ollama + Llama 3.1 8B\*\* — local LLM agent (no cloud)

\- \*\*Pydantic\*\* — data validation

\- \*\*httpx\*\* — HTTP client for CLI simulator



\---



\## Project Structure

sim-swap-agent/



├── main.py              # FastAPI app — API endpoints



├── agent.py             # Agentic loop — tool calling + decision grounding



├── tools.py             # 3 callable agent tools



├── models.py            # Pydantic data models



├── simulator.py         # CLI demo — 5 fraud scenarios



├── data/



│   └── events\_log.json  # Auto-generated audit log



└── requirements.txt     # Python dependencies





\## Setup Instructions



\### 1. Install Ollama

Download from https://ollama.com/download and install.

Then pull the model:

ollama pull llama3.1:8b



\### 2. Place all project files in a folder called sim-swap-agent



\### 3. Create virtual environment

python -m venv venv



Activate on Windows PowerShell:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass



venv\\Scripts\\Activate.ps1



Activate on Mac/Linux:

source venv/bin/activate



\### 4. Install dependencies

pip install -r requirements.txt



\---



\## Running the Project



\### Step 1 — Start the FastAPI server

Open a terminal, activate venv, then run:

uvicorn main:app --reload

Server runs at: http://127.0.0.1:8000

Interactive API docs: http://127.0.0.1:8000/docs



\### Step 2 — Run the CLI Simulator

Open a SECOND terminal, activate venv, then run:

python simulator.py

Select a scenario (1-5) or run all with option 6.



\---



\## API Endpoints



| Method | Endpoint | Description |

|--------|----------|-------------|

| POST | /event | Submit account event, get fraud decision |

| GET | /events/{user\_id} | Get event history for a user |

| GET | /health | Health check |



\---



\## Risk Scoring Logic



| Risk Factor | Points |

|-------------|--------|

| SIM change between 11PM-5AM | +25 |

| Foreign country detected | +25 |

| 2+ changes in 24 hours | +20 |

| New carrier detected | +15 |

| 3+ SIM swaps in 24 hours | +15 |

| No prior account history | +10 |



Decision Thresholds:

\- Score 0-39   → ALLOW

\- Score 40-69  → CHALLENGE (step-up verification triggered)

\- Score 70-100 → BLOCK



\---



\## Test Scenarios and Expected Results



| # | Scenario | Expected Decision |

|---|----------|-------------------|

| 1 | Normal SIM change, business hours, home country | ALLOW |

| 2 | Late night SIM change at 3 AM | CHALLENGE |

| 3 | SIM change with foreign country IP | CHALLENGE |

| 4 | SIM and device change within 2 hours | BLOCK |

| 5 | 3 or more SIM swaps in 24 hours | BLOCK |



\---



\## Key Design Decision



This system uses LLM-driven reasoning for tool orchestration, but validates

and grounds final decisions in deterministic tool outputs to mitigate

hallucination risk in smaller local models. The agent autonomously decides

which tools to call and when (genuinely agentic), while the final

ALLOW/CHALLENGE/BLOCK decision is always based on the real, verified output

of calculate\_risk\_score() — never on the model's free-text reasoning alone.



\---



\## AI Focus

Agentic AI — autonomous tool-calling reasoning loop using a fully local

LLM (Llama 3.1 8B via Ollama). No cloud dependency. No API key required.





