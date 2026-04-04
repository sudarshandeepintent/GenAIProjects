# Chief of Staff AI (“JARVIS for your work day”)

Multi-agent [Google ADK](https://google.github.io/adk-docs/) app: an **orchestrator** delegates to **calendar**, **task**, **research**, and **comms** specialists, persists **structured memory** (SQLite), and runs a **proactive engine** that can flag conflicts and gaps without the user asking.

Layout follows [google/mcp — Ops Copilot example](https://github.com/google/mcp/tree/main/examples/opscopilot): agent package + optional FastAPI shell + workspace UI.

## Architecture

- **ChiefOfStaffOrchestrator** — plans, delegates via `AgentTool`, reads/writes prefs and decisions, can refresh proactive suggestions.
- **CalendarAgent** / **TaskAgent** / **ResearchAgent** / **CommsAgent** — domain-scoped tools on the local store; real **Google Calendar / Gmail / Slack / Asana / Jira** attach through **Streamable HTTP MCP** when you set `CHIEF_OF_STAFF_MCP_URL` (see [Google MCP overview](https://docs.cloud.google.com/mcp/overview)).
- **Structured memory** — tasks (with optional dependencies + external refs), calendar blocks, notes, agent decisions, user prefs, proactive suggestion queue.
- **Proactive rules** — `POST /api/proactive/scan` (or `run_proactive_engine` tool): e.g. design meeting vs open design/asset tasks, dense same-day meetings, `slack-action` notes without matching tasks.

On **Cloud Run**, SQLite defaults to `/tmp/chief_of_staff.db` when `K_SERVICE` is set (ephemeral unless you mount storage or switch to Cloud SQL / AlloyDB later).

## Repo layout

```text
GenAIProjects/
├── chief_of_staff_app/     # ADK agent (deploy this path with adk deploy)
│   ├── agent.py            # root_agent + specialists
│   ├── tools.py
│   ├── store.py
│   ├── proactive.py
│   └── mcp_bridge.py
├── frontend/index.html     # Dashboard at /workspace/
├── main.py                 # FastAPI: ADK UI + /api/*
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Local: ADK dev UI only

```bash
cd /path/to/GenAIProjects
python3 -m venv .venv && source .venv/bin/activate
pip install -r chief_of_staff_app/requirements.txt
cd chief_of_staff_app && adk web
```

Chat with **ChiefOfStaffOrchestrator**. Example: *“I need to ship the API redesign by Friday — break it down, check my calendar for conflicts, and block focus time.”*

## Local: API + dashboard + ADK UI

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in project / Vertex or API key
export GOOGLE_CLOUD_PROJECT=your-project
export GOOGLE_GENAI_USE_VERTEXAI=True
export ADK_MODEL=gemini-2.0-flash
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

- ADK chat: `http://127.0.0.1:8080/`
- Workspace: `http://127.0.0.1:8080/workspace/`
- Summary JSON: `http://127.0.0.1:8080/api/summary`
- Proactive cron hook: `POST http://127.0.0.1:8080/api/proactive/scan`

## Deploy to Cloud Run (`adk deploy`)

From the **repository root**, with `gcloud` authenticated and APIs enabled per [ADK Cloud Run docs](https://google.github.io/adk-docs/deploy/cloud-run/):

```bash
export PROJECT_ID="your-gcp-project"
export SERVICE_ACCOUNT="your-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Agent-only deploy (matches google/mcp Ops Copilot pattern):
uvx --from google-adk==1.14.0 \
  adk deploy cloud_run \
  --project=$PROJECT_ID \
  --region=europe-west1 \
  --service_name=genaitracksecond \
  --with_ui \
  ./chief_of_staff_app \
  -- \
  --labels=dev-tutorial=codelab-adk \
  --service-account=$SERVICE_ACCOUNT
```

If your ADK version expects the whole repo as the app root, you can pass `.` instead of `./chief_of_staff_app` (same flags otherwise).

For the **custom** `main.py` stack (`/api/summary`, `/workspace`, `POST /api/proactive/scan`), build from the `Dockerfile` instead:

```bash
gcloud run deploy chief-of-staff-api \
  --source . \
  --region europe-west1 \
  --project "$PROJECT_ID" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_GENAI_USE_VERTEXAI=true,ADK_MODEL=gemini-2.0-flash"
```

Set `CHIEF_OF_STAFF_DB_PATH=/tmp/chief_of_staff.db` if you want it explicit on Cloud Run.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `ADK_MODEL` | Gemini model id (default `gemini-2.0-flash`). |
| `CHIEF_OF_STAFF_DB_PATH` | SQLite path for structured memory. |
| `CHIEF_OF_STAFF_MCP_URL` | Optional Streamable HTTP MCP URL. |
| `CHIEF_OF_STAFF_MCP_HEADERS` | Optional JSON headers for MCP. |
| `SESSION_SERVICE_URI` | Optional ADK session DB (e.g. `sqlite+aiosqlite:////tmp/adk_sessions.db`). |
| `ALLOWED_ORIGINS` | CORS for `main.py`. |

**Models:** This repo targets **Vertex AI / Gemini** via ADK, which matches `adk deploy cloud_run`. Using **Anthropic** instead would require a separate integration path (not the default ADK model stack on Cloud Run).
