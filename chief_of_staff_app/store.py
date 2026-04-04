"""SQLite structured memory: tasks, calendar, notes, decisions, prefs, proactive suggestions."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _db_path() -> str:
    if os.environ.get("K_SERVICE"):
        return os.environ.get("CHIEF_OF_STAFF_DB_PATH", "/tmp/chief_of_staff.db")
    default = Path(__file__).resolve().parent.parent / "data" / "chief_of_staff.db"
    return os.environ.get("CHIEF_OF_STAFF_DB_PATH", str(default))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                due_at TEXT,
                dependencies_json TEXT DEFAULT '[]',
                external_ref TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS calendar_events (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                start_at TEXT NOT NULL,
                end_at TEXT NOT NULL,
                location TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                tags TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agent_decisions (
                id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                summary TEXT NOT NULL,
                details_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_prefs (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS proactive_suggestions (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                context_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_events_start ON calendar_events(start_at);
            CREATE INDEX IF NOT EXISTS idx_proactive_status ON proactive_suggestions(status);
            """
        )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except json.JSONDecodeError:
        return []


# --- Tasks ---


def create_task(
    title: str,
    description: str = "",
    due_at: str | None = None,
    dependencies: list[str] | None = None,
    external_ref: str = "",
) -> dict[str, Any]:
    init_db()
    tid = str(uuid.uuid4())
    now = _utc_now()
    deps = json.dumps(dependencies or [])
    with _connect() as conn:
        conn.execute(
            """INSERT INTO tasks (id, title, description, status, due_at,
               dependencies_json, external_ref, created_at, updated_at)
               VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)""",
            (
                tid,
                title.strip(),
                (description or "").strip(),
                due_at,
                deps,
                (external_ref or "").strip(),
                now,
                now,
            ),
        )
        conn.commit()
    return get_task(tid)


def get_task(task_id: str) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        return {"status": "error", "error_message": f"Task not found: {task_id}"}
    d = _row_to_dict(row)
    d["dependencies"] = _parse_json_list(d.pop("dependencies_json", "[]"))
    return {"status": "success", "task": d}


def list_tasks(status_filter: str | None = None, limit: int = 50) -> dict[str, Any]:
    init_db()
    limit = max(1, min(limit, 200))
    with _connect() as conn:
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status_filter, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    out = []
    for r in rows:
        d = _row_to_dict(r)
        d["dependencies"] = _parse_json_list(d.pop("dependencies_json", "[]"))
        out.append(d)
    return {"status": "success", "tasks": out, "count": len(out)}


def update_task_status(task_id: str, status: str) -> dict[str, Any]:
    init_db()
    allowed = {"pending", "in_progress", "done", "cancelled"}
    if status not in allowed:
        return {
            "status": "error",
            "error_message": f"Invalid status. Use one of: {sorted(allowed)}",
        }
    now = _utc_now()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, task_id),
        )
        conn.commit()
    if cur.rowcount == 0:
        return {"status": "error", "error_message": f"Task not found: {task_id}"}
    return get_task(task_id)


# --- Calendar ---


def create_calendar_event(
    title: str,
    start_at: str,
    end_at: str,
    location: str = "",
) -> dict[str, Any]:
    init_db()
    eid = str(uuid.uuid4())
    now = _utc_now()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO calendar_events (id, title, start_at, end_at, location, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (eid, title.strip(), start_at, end_at, (location or "").strip(), now),
        )
        conn.commit()
    return get_calendar_event(eid)


def get_calendar_event(event_id: str) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM calendar_events WHERE id = ?", (event_id,)
        ).fetchone()
    if not row:
        return {"status": "error", "error_message": f"Event not found: {event_id}"}
    return {"status": "success", "event": _row_to_dict(row)}


def list_calendar_events(from_iso: str | None = None, limit: int = 50) -> dict[str, Any]:
    init_db()
    limit = max(1, min(limit, 200))
    with _connect() as conn:
        if from_iso:
            rows = conn.execute(
                """SELECT * FROM calendar_events
                   WHERE start_at >= ? ORDER BY start_at ASC LIMIT ?""",
                (from_iso, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM calendar_events ORDER BY start_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return {"status": "success", "events": [_row_to_dict(r) for r in rows], "count": len(rows)}


# --- Notes ---


def add_note(title: str, body: str, tags: list[str] | None = None) -> dict[str, Any]:
    init_db()
    nid = str(uuid.uuid4())
    now = _utc_now()
    tag_json = json.dumps(tags or [])
    with _connect() as conn:
        conn.execute(
            """INSERT INTO notes (id, title, body, tags, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (nid, title.strip(), body.strip(), tag_json, now),
        )
        conn.commit()
    return get_note(nid)


def get_note(note_id: str) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not row:
        return {"status": "error", "error_message": f"Note not found: {note_id}"}
    d = _row_to_dict(row)
    try:
        d["tags"] = json.loads(d["tags"] or "[]")
    except json.JSONDecodeError:
        d["tags"] = []
    return {"status": "success", "note": d}


def search_notes(query: str, limit: int = 30) -> dict[str, Any]:
    init_db()
    limit = max(1, min(limit, 100))
    q = f"%{(query or '').strip()}%"
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM notes
               WHERE title LIKE ? OR body LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (q, q, limit),
        ).fetchall()
    out = []
    for r in rows:
        d = _row_to_dict(r)
        try:
            d["tags"] = json.loads(d["tags"] or "[]")
        except json.JSONDecodeError:
            d["tags"] = []
        out.append(d)
    return {"status": "success", "notes": out, "count": len(out)}


def list_recent_notes(limit: int = 20) -> dict[str, Any]:
    init_db()
    limit = max(1, min(limit, 100))
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM notes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        d = _row_to_dict(r)
        try:
            d["tags"] = json.loads(d["tags"] or "[]")
        except json.JSONDecodeError:
            d["tags"] = []
        out.append(d)
    return {"status": "success", "notes": out, "count": len(out)}


# --- Agent memory ---


def record_agent_decision(
    agent_name: str,
    summary: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db()
    did = str(uuid.uuid4())
    now = _utc_now()
    payload = json.dumps(details or {})
    with _connect() as conn:
        conn.execute(
            """INSERT INTO agent_decisions (id, agent_name, summary, details_json, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (did, agent_name.strip(), summary.strip(), payload, now),
        )
        conn.commit()
    return {
        "status": "success",
        "decision": {
            "id": did,
            "agent_name": agent_name,
            "summary": summary,
            "details": details or {},
            "created_at": now,
        },
    }


def list_recent_decisions(limit: int = 30) -> dict[str, Any]:
    init_db()
    limit = max(1, min(limit, 100))
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_decisions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        d = _row_to_dict(r)
        try:
            d["details"] = json.loads(d.get("details_json") or "{}")
        except json.JSONDecodeError:
            d["details"] = {}
        del d["details_json"]
        out.append(d)
    return {"status": "success", "decisions": out, "count": len(out)}


def set_user_pref(key: str, value: Any) -> dict[str, Any]:
    init_db()
    now = _utc_now()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO user_prefs (key, value_json, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json,
               updated_at = excluded.updated_at""",
            (key.strip(), json.dumps(value), now),
        )
        conn.commit()
    return {"status": "success", "key": key, "value": value}


def get_user_pref(key: str) -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM user_prefs WHERE key = ?", (key,)).fetchone()
    if not row:
        return {"status": "success", "found": False, "key": key, "value": None}
    try:
        val = json.loads(row["value_json"])
    except json.JSONDecodeError:
        val = row["value_json"]
    return {"status": "success", "found": True, "key": key, "value": val}


# --- Proactive ---


def insert_proactive_suggestion(
    kind: str,
    title: str,
    body: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_db()
    sid = str(uuid.uuid4())
    now = _utc_now()
    ctx = json.dumps(context or {})
    with _connect() as conn:
        conn.execute(
            """INSERT INTO proactive_suggestions
               (id, kind, title, body, status, context_json, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?)""",
            (sid, kind, title.strip(), body.strip(), ctx, now),
        )
        conn.commit()
    return {
        "status": "success",
        "suggestion": {
            "id": sid,
            "kind": kind,
            "title": title,
            "body": body,
            "status": "pending",
            "context": context or {},
            "created_at": now,
        },
    }


def list_proactive_suggestions(
    status_filter: str | None = "pending",
    limit: int = 50,
) -> dict[str, Any]:
    init_db()
    limit = max(1, min(limit, 100))
    with _connect() as conn:
        if status_filter:
            rows = conn.execute(
                """SELECT * FROM proactive_suggestions
                   WHERE status = ? ORDER BY created_at DESC LIMIT ?""",
                (status_filter, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM proactive_suggestions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    out = []
    for r in rows:
        d = _row_to_dict(r)
        try:
            d["context"] = json.loads(d.pop("context_json", "{}"))
        except json.JSONDecodeError:
            d["context"] = {}
        out.append(d)
    return {"status": "success", "suggestions": out, "count": len(out)}


def update_proactive_status(suggestion_id: str, status: str) -> dict[str, Any]:
    init_db()
    allowed = {"pending", "dismissed", "accepted"}
    if status not in allowed:
        return {
            "status": "error",
            "error_message": f"Invalid status. Use one of: {sorted(allowed)}",
        }
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE proactive_suggestions SET status = ? WHERE id = ?",
            (status, suggestion_id),
        )
        conn.commit()
    if cur.rowcount == 0:
        return {"status": "error", "error_message": f"Suggestion not found: {suggestion_id}"}
    return {"status": "success", "id": suggestion_id, "new_status": status}


def pending_suggestion_titles() -> set[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT title FROM proactive_suggestions WHERE status = 'pending'"
        ).fetchall()
    return {r["title"] for r in rows}
