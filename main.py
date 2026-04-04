"""
FastAPI: ADK Chief of Staff + optional workspace UI + proactive scan for Cloud Scheduler.

Deploy on Cloud Run with `adk deploy cloud_run ./chief_of_staff_app --with_ui` (see README),
or run this file with uvicorn for API + /workspace dashboard.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app

from chief_of_staff_app.proactive import run_proactive_scan
from chief_of_staff_app.store import (
    init_db,
    list_calendar_events,
    list_proactive_suggestions,
    list_recent_decisions,
    list_recent_notes,
    list_tasks,
)


def _session_uri() -> str | None:
    return os.environ.get("SESSION_SERVICE_URI") or None


_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost,http://127.0.0.1:8080,http://127.0.0.1:5173,*",
)
ALLOWED_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]

app: FastAPI = get_fast_api_app(
    agents_dir=str(ROOT),
    session_service_uri=_session_uri(),
    allow_origins=ALLOWED_ORIGINS,
    web=True,
)


@app.get("/api/health")
def api_health():
    return {"status": "ok", "service": "chief-of-staff"}


@app.get("/api/summary")
def api_summary():
    init_db()
    pending = list_proactive_suggestions(status_filter="pending", limit=50)
    return {
        "tasks": list_tasks(limit=100),
        "events": list_calendar_events(limit=50),
        "notes": list_recent_notes(limit=25),
        "proactive": pending,
        "decisions": list_recent_decisions(limit=20),
    }


@app.post("/api/proactive/scan")
def api_proactive_scan():
    """
    Run rule-based proactive checks. Wire Cloud Scheduler (cron) to POST this URL
    with IAM / auth as appropriate for production.
    """
    init_db()
    return run_proactive_scan()


_frontend = ROOT / "frontend"
if _frontend.is_dir():
    app.mount(
        "/workspace",
        StaticFiles(directory=str(_frontend), html=True),
        name="workspace",
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
