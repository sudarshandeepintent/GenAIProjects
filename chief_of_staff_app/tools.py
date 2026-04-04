"""Tools for specialist agents (structured memory + coordination helpers)."""

from __future__ import annotations

import json
from typing import Any

from . import store


def _json_list(raw: str, field: str) -> tuple[list[str] | None, str | None]:
    s = (raw or "").strip()
    if not s:
        return [], None
    try:
        v = json.loads(s)
        if v is None:
            return [], None
        if not isinstance(v, list):
            return None, f"{field} must be a JSON array of strings"
        out = [str(x) for x in v]
        return out, None
    except json.JSONDecodeError as e:
        return None, f"{field} is invalid JSON: {e}"


def _json_value(raw: str) -> tuple[Any | None, str | None]:
    s = (raw or "").strip()
    if not s:
        return None, "value_json is required (JSON string, number, object, array, true, false, null)"
    try:
        return json.loads(s), None
    except json.JSONDecodeError as e:
        return None, f"value_json is invalid JSON: {e}"


def _json_object(raw: str, field: str) -> tuple[dict[str, Any] | None, str | None]:
    s = (raw or "").strip() or "{}"
    try:
        v = json.loads(s)
        if not isinstance(v, dict):
            return None, f"{field} must be a JSON object"
        return v, None
    except json.JSONDecodeError as e:
        return None, f"{field} is invalid JSON: {e}"


def create_task(
    title: str,
    description: str = "",
    due_at: str = "",
    dependencies_json: str = "[]",
    external_ref: str = "",
) -> dict:
    """Create a task. dependencies_json: JSON array of task ids, e.g. []. external_ref: Jira/Asana id."""
    deps, err = _json_list(dependencies_json, "dependencies_json")
    if err:
        return {"status": "error", "error_message": err}
    due = due_at.strip() or None
    return store.create_task(
        title=title,
        description=description,
        due_at=due,
        dependencies=deps,
        external_ref=external_ref,
    )


def list_tasks(status_filter: str = "", limit: int = 50) -> dict:
    """List tasks. status_filter: empty for all, or pending, in_progress, done, cancelled."""
    sf = status_filter.strip() or None
    return store.list_tasks(status_filter=sf, limit=limit)


def update_task_status(task_id: str, status: str) -> dict:
    """Set task status."""
    return store.update_task_status(task_id=task_id, status=status)


def create_calendar_event(
    title: str,
    start_at: str,
    end_at: str,
    location: str = "",
) -> dict:
    """Create a calendar block (ISO-8601). Sync to Google Calendar via MCP when configured."""
    return store.create_calendar_event(
        title=title, start_at=start_at, end_at=end_at, location=location
    )


def list_calendar_events(from_iso: str = "", limit: int = 50) -> dict:
    """List events. from_iso: empty for all, or ISO lower bound on start_at."""
    fi = from_iso.strip() or None
    return store.list_calendar_events(from_iso=fi, limit=limit)


def add_note(title: str, body: str, tags_json: str = "[]") -> dict:
    """Add a note. tags_json: JSON array of strings, e.g. ["slack-action"]."""
    tags, err = _json_list(tags_json, "tags_json")
    if err:
        return {"status": "error", "error_message": err}
    return store.add_note(title=title, body=body, tags=tags)


def search_notes(query: str, limit: int = 30) -> dict:
    """Search notes by title or body."""
    return store.search_notes(query=query, limit=limit)


def list_recent_notes(limit: int = 20) -> dict:
    """Recent notes."""
    return store.list_recent_notes(limit=limit)


def record_decision(agent_name: str, summary: str, details_json: str = "{}") -> dict:
    """Persist orchestration or specialist decision. details_json: JSON object, e.g. {}."""
    details, err = _json_object(details_json, "details_json")
    if err:
        return {"status": "error", "error_message": err}
    return store.record_agent_decision(
        agent_name=agent_name, summary=summary, details=details
    )


def set_preference(key: str, value_json: str) -> dict:
    """Store user preference. value_json: any JSON value, e.g. \"Europe/London\" or {\"start\":\"09:00\"}."""
    value, err = _json_value(value_json)
    if err:
        return {"status": "error", "error_message": err}
    return store.set_user_pref(key=key, value=value)


def get_preference(key: str) -> dict:
    """Read one preference by key."""
    return store.get_user_pref(key=key)


def list_pending_proactive(limit: int = 30) -> dict:
    """List proactive suggestions awaiting user action."""
    return store.list_proactive_suggestions(status_filter="pending", limit=limit)


def dismiss_proactive_suggestion(suggestion_id: str) -> dict:
    """Mark a proactive suggestion dismissed."""
    return store.update_proactive_status(suggestion_id, "dismissed")


def accept_proactive_suggestion(suggestion_id: str) -> dict:
    """Mark a proactive suggestion accepted (you acted on it)."""
    return store.update_proactive_status(suggestion_id, "accepted")


def run_proactive_engine() -> dict:
    """Scan calendar, tasks, and notes; insert new proactive suggestions. Call from cron."""
    from .proactive import run_proactive_scan

    return run_proactive_scan()
