# Devise: Agentic Government Council

## 🏛️ Project overview
Devise (Agentic Government Council) is a small developer tool that helps you understand, visualize, and debug multi-step agent executions. It runs a ReAct-style agent, captures a full execution trace (thoughts, tool calls, tool observations, and final answers), displays that trace in a lightweight frontend, and provides critic-style analysis to locate which message or step "caused" a wrong or surprising decision.

Why this exists
- Agentic systems are powerful but opaque. Devise makes the agent’s decisions visible so you can debug wrong answers, tool misuses, and unexpected behaviour.
- It provides structured output (optional) and tooling to point to likely "culprit" messages so you can iterate faster.

How it works (high level)
- The Flask backend runs a GovAgent (see [`backend.llm_utils.GovAgent`](backend/llm_utils.py)) that wraps a ReAct-style agent built with the local react agent helper (see [`core.react_agent.create_agent.create_react_agent`](core/react_agent/create_agent.py)).
- The backend exposes an endpoint to generate traces ([`backend/app.generate_trace`](backend/app.py)), stores the trace, and returns a JSON-serializable representation for the UI.

Key files and symbols
- Agent code / utilities: [`backend/llm_utils.py`](backend/llm_utils.py) (contains `Agent` and `GovAgent`, plus tool implementations and Langfuse integration).
- Trace generation endpoint: [`backend/app.py`](backend/app.py) (POST /api/generate-trace).
- Local React agent implementation: [`core/react_agent/create_agent.py`](core/react_agent/create_agent.py) (factory: `create_react_agent`).
- Structured output schema: [`core/react_agent/output_schema.py`](core/react_agent/output_schema.py).
- Frontend UI: [frontend/templates/index.html](frontend/templates/index.html) and [frontend/static/app.js](frontend/static/app.js).
- Helpful run notes: [RUNNING.md](RUNNING.md) and convenience scripts `./run_backend.sh` and `./run_frontend.sh`.

## 🚀 Setup instructions
1. Clone the repo and open the project root.
2. Create and activate a Python virtual environment.
   - Example:
     - python3 -m venv .venv
     - source .venv/bin/activate
3. Install dependencies:
   - Install top-level deps:
     - pip install -r requirements.txt
   - There are extra helper packages referenced in notebooks and code (LangGraph / LangChain / Pydantic). If you hit import errors, re-check `core/requirements.txt` and `requirements.txt`.
4. Environment variables and API keys
   - The project expects some keys for model backends and monitoring:
     - HOLISTIC_AI_TEAM_ID and HOLISTIC_AI_API_TOKEN — for Holistic AI / Bedrock helper used by [`backend.llm_utils.GovAgent`](backend/llm_utils.py).
     - OPENAI_API_KEY — optional fallback if Bedrock credentials are not set.
     - LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY — optional, used in [`backend/llm_utils.py`](backend/llm_utils.py) to initialize Langfuse instrumentation.
   - You can put these into a `.env` file at the repo root (the code loads ../.env from some notebook contexts). The repo includes examples that print status when keys are missing; see the top of [`backend/llm_utils.py`](backend/llm_utils.py) for details.

## ▶️ How to run/test
There are convenience scripts and manual options.

Quick (recommended)
- Start backend:
  - ./run_backend.sh
  - This runs the Flask backend which exposes the trace generation API (see [`backend/app.py`](backend/app.py)).
- Start frontend:
  - ./run_frontend.sh
  - Open http://localhost:5000 (or follow the URL printed by the script). The UI is the static app in [frontend/templates/index.html](frontend/templates/index.html) / [frontend/static/app.js](frontend/static/app.js).

Manual
- Backend
  - Activate venv and run the Flask app module (or run the script the backend uses). The backend serves the API that the frontend calls:
    - POST /api/generate-trace — implemented in [`backend/app.py`](backend/app.py).
  - You can also run example flows from `main.py`:
    - python main.py --example
    - This will run a pre-baked example trace and print analysis output to the console (see `main.py` for how example traces and the critic analysis are invoked).
- Frontend
  - The frontend is static and can be served by any HTTP server. The convenience script runs a small server and points the browser to [frontend/index_standalone.html](frontend/index_standalone.html).

Testing flow (end-to-end)
1. Start backend and frontend per the Quick section.
2. Open the UI and submit a user query (e.g., "I would like to book the community center for a 30-person event on December 10th.").
3. The frontend hits the backend endpoint in [`backend/app.py`](backend/app.py) which creates a `GovAgent` (`[`backend.llm_utils.GovAgent`](backend/llm_utils.py)`) to run the query and return a trace.
4. The UI visualizes the trace and shows analysis results (culprit candidates and summary). The front-end logic that drives the generation button and basic UI state is in [frontend/static/app.js](frontend/static/app.js).

Enjoy exploring agent traces — Devise should help you answer the crucial question: "Why did the agent do that?"