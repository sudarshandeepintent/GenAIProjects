"""Tools for specialist agents (structured memory + coordination helpers)."""

from __future__ import annotations

from typing import Any

from . import store


def create_task(
    title: str,
    description: str = "",
    due_at: str | None = None,
    dependencies: list[str] | None = None,
    external_ref: str = "",
) -> dict:
    """Create a task. dependencies are other task ids. external_ref: Jira/Asana id if synced."""
    return store.create_task(
        title=title,
        description=description,
        due_at=due_at,
        dependencies=dependencies,
        external_ref=external_ref,
    )


def list_tasks(status_filter: str | None = None, limit: int = 50) -> dict:
    """List tasks. status_filter: pending, in_progress, done, cancelled."""
    return store.list_tasks(status_filter=status_filter, limit=limit)


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


def list_calendar_events(from_iso: str | None = None, limit: int = 50) -> dict:
    """List events; optional lower bound on start_at."""
    return store.list_calendar_events(from_iso=from_iso, limit=limit)


def add_note(title: str, body: str, tags: list[str] | None = None) -> dict:
    """Add a note. Use tag 'slack-action' for Slack thread action items to surface proactively."""
    return store.add_note(title=title, body=body, tags=tags)


def search_notes(query: str, limit: int = 30) -> dict:
    """Search notes by title or body."""
    return store.search_notes(query=query, limit=limit)


def list_recent_notes(limit: int = 20) -> dict:
    """Recent notes."""
    return store.list_recent_notes(limit=limit)


def record_decision(agent_name: str, summary: str, details: dict[str, Any] | None = None) -> dict:
    """Persist orchestration or specialist decision for audit and proactive context."""
    return store.record_agent_decision(
        agent_name=agent_name, summary=summary, details=details
    )


def set_preference(key: str, value: Any) -> dict:
    """Store user preference (timezone, focus hours, notification style)."""
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
