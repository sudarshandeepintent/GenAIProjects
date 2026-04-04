"""Rule-based proactive checks over structured memory (cron / webhook friendly)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import store


def _parse_iso(ts: str) -> datetime | None:
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def run_proactive_scan() -> dict[str, Any]:
    """
    Detect cross-cutting gaps: meetings vs incomplete work, dense schedules, Slack notes vs tasks.
    Idempotent for duplicate *titles* while still pending.
    """
    store.init_db()
    pending_titles = store.pending_suggestion_titles()
    created: list[dict[str, Any]] = []

    now = datetime.now(timezone.utc)
    horizon = (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")

    ev_res = store.list_calendar_events(from_iso=now.strftime("%Y-%m-%dT%H:%M:%SZ"), limit=200)
    events = ev_res.get("events") or []
    tasks_res = store.list_tasks(limit=200)
    tasks = tasks_res.get("tasks") or []

    incomplete = [t for t in tasks if t.get("status") not in ("done", "cancelled")]

    # 1) Design meeting vs incomplete design/assets work
    for ev in events:
        title_ev = (ev.get("title") or "").lower()
        if "design" not in title_ev:
            continue
        related_open = [
            t
            for t in incomplete
            if "design" in (t.get("title") or "").lower()
            or "asset" in (t.get("title") or "").lower()
        ]
        if not related_open:
            continue
        sug_title = f"Meeting vs work: {ev.get('title', 'Design meeting')[:60]}"
        if sug_title not in pending_titles:
            body = (
                "You have a design-related meeting coming up but related tasks still look open. "
                "Want to reschedule the meeting, flag the owner, or block time to finish assets?"
            )
            r = store.insert_proactive_suggestion(
                "dependency",
                sug_title,
                body,
                {"event_id": ev.get("id"), "event_start": ev.get("start_at")},
            )
            if r.get("status") == "success":
                created.append(r["suggestion"])
                pending_titles.add(sug_title)

    # 2) Same-day back-to-back streak (3+ with minimal gaps)
    by_day: dict[str, list[dict]] = {}
    for ev in events:
        start = _parse_iso(ev.get("start_at") or "")
        if not start:
            continue
        day = start.date().isoformat()
        by_day.setdefault(day, []).append(ev)
    for day, day_events in by_day.items():
        day_events.sort(key=lambda e: e.get("start_at") or "")
        streak = 0
        max_streak = 0
        prev_end: datetime | None = None
        for ev in day_events:
            s = _parse_iso(ev.get("start_at") or "")
            e = _parse_iso(ev.get("end_at") or "")
            if not s or not e:
                continue
            if prev_end is None:
                streak = 1
            else:
                gap_min = (s - prev_end).total_seconds() / 60.0
                streak = streak + 1 if gap_min < 15 else 1
            max_streak = max(max_streak, streak)
            prev_end = e
        if max_streak >= 3:
            sug_title = f"Dense schedule {day}: {max_streak} tight meetings"
            if sug_title not in pending_titles:
                body = (
                    "You have several back-to-back meetings with little buffer. "
                    "Should I block 2 hours of focus time earlier that day or push one slot?"
                )
                r = store.insert_proactive_suggestion(
                    "gap",
                    sug_title,
                    body,
                    {"date": day, "streak": max_streak},
                )
                if r.get("status") == "success":
                    created.append(r["suggestion"])
                    pending_titles.add(sug_title)

    # 3) Note tagged slack-action without matching task title
    notes_res = store.list_recent_notes(limit=50)
    for note in notes_res.get("notes") or []:
        tags = note.get("tags") or []
        if "slack-action" not in tags:
            continue
        first_line = (note.get("body") or "").split("\n")[0].strip()
        if not first_line:
            continue
        key = first_line[:80]
        exists = any(key.lower() in (t.get("title") or "").lower() for t in tasks)
        if exists:
            continue
        sug_title = f"Slack action not tracked: {key[:50]}"
        if sug_title not in pending_titles:
            body = (
                "A Slack-sourced action item is captured in notes but may not be in your task list "
                "(Asana/Jira). Want me to create a task and link it?"
            )
            r = store.insert_proactive_suggestion(
                "comms",
                sug_title,
                body,
                {"note_id": note.get("id")},
            )
            if r.get("status") == "success":
                created.append(r["suggestion"])
                pending_titles.add(sug_title)

    return {
        "status": "success",
        "created_count": len(created),
        "suggestions": created,
        "scanned_until": horizon,
    }
