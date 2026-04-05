"""Chief of Staff: orchestrator + calendar, task, research, comms specialists."""

from __future__ import annotations

import os

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.tools.agent_tool import AgentTool

from . import tools
from .mcp_bridge import extra_mcp_toolsets

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

MODEL = os.environ.get("ADK_MODEL", "gemini-2.5-flash")

_calendar_tools = [
    FunctionTool(func=tools.create_calendar_event),
    FunctionTool(func=tools.list_calendar_events),
]

_task_tools = [
    FunctionTool(func=tools.create_task),
    FunctionTool(func=tools.list_tasks),
    FunctionTool(func=tools.update_task_status),
]

_research_tools = [
    FunctionTool(func=tools.add_note),
    FunctionTool(func=tools.search_notes),
    FunctionTool(func=tools.list_recent_notes),
]

_comms_tools = [
    FunctionTool(func=tools.add_note),
    FunctionTool(func=tools.search_notes),
    FunctionTool(func=tools.list_recent_notes),
]

_coordination_tools = [
    FunctionTool(func=tools.record_decision),
    FunctionTool(func=tools.set_preference),
    FunctionTool(func=tools.get_preference),
    FunctionTool(func=tools.list_pending_proactive),
    FunctionTool(func=tools.dismiss_proactive_suggestion),
    FunctionTool(func=tools.accept_proactive_suggestion),
    FunctionTool(func=tools.run_proactive_engine),
]

calendar_agent = LlmAgent(
    model=MODEL,
    name="CalendarAgent",
    description="Schedules focus blocks and meetings in the structured calendar; lists upcoming events.",
    instruction=(
        "You manage time blocks via tools only. Use ISO-8601 times. "
        "After changes, summarize ids and times. If MCP calendar tools exist, prefer them for real Google Calendar; "
        "otherwise use create_calendar_event / list_calendar_events for the local store."
    ),
    tools=_calendar_tools,
)

task_agent = LlmAgent(
    model=MODEL,
    name="TaskAgent",
    description="Prioritizes work: create tasks with dependencies, list by status, update status.",
    instruction=(
        "You own the task backlog. Break goals into tasks with clear titles; set dependencies when order matters "
        "using create_task's dependencies_json as a JSON array of task ids (e.g. []). "
        "Map external Jira/Asana ids in external_ref when known. Echo task ids from tools."
    ),
    tools=_task_tools,
)

research_agent = LlmAgent(
    model=MODEL,
    name="ResearchAgent",
    description="Captures and searches notes from Slack threads, meetings, and research snippets.",
    instruction=(
        "Use notes to summarize findings. For add_note, pass tags_json as a JSON array of strings, e.g. [\"blocker\"]. "
        "If remote MCP exposes search or Slack read tools, use them; else search_notes / add_note."
    ),
    tools=_research_tools,
)

comms_agent = LlmAgent(
    model=MODEL,
    name="CommsAgent",
    description="Drafts and tracks communication follow-ups; links Slack action items to tasks via notes.",
    instruction=(
        "Capture comms context in notes. For Slack action items, use add_note with tags_json [\"slack-action\"] "
        "so the proactive engine can flag missing Jira/Asana tasks. "
        "If Gmail/Slack MCP tools are present, use them for real send/read."
    ),
    tools=_comms_tools,
)

_orchestrator_tools: list = [
    AgentTool(agent=calendar_agent),
    AgentTool(agent=task_agent),
    AgentTool(agent=research_agent),
    AgentTool(agent=comms_agent),
]
_orchestrator_tools.extend(_coordination_tools)
_orchestrator_tools.extend(extra_mcp_toolsets())

root_agent = LlmAgent(
    model=MODEL,
    name="ChiefOfStaffOrchestrator",
    instruction="""
You are an AI Chief of Staff: you coordinate calendar, tasks, research notes, and comms so the user
does not have to manually glue systems together.

**Delegation**
1. **CalendarAgent** — focus blocks, meeting holds, conflict checks against listed events.
2. **TaskAgent** — backlog, dependencies, statuses, external ticket refs.
3. **ResearchAgent** — summarize and retrieve information stored in notes (and via MCP search if available).
4. **CommsAgent** — Slack/Gmail-aligned follow-ups; use notes with tag `slack-action` for untracked actions.

**Orchestration habits**
- For goals like "ship X by Friday": decompose with TaskAgent, check CalendarAgent for conflicts,
  pull context with ResearchAgent, ensure comms captured with CommsAgent, then **record_decision**
  with a short plan summary.
- Call **list_pending_proactive** when starting a session so you can mention open alerts.
- After substantive multi-step plans, call **run_proactive_engine** to refresh rule-based suggestions
  (or rely on Cloud Scheduler hitting /api/proactive/scan in production).

**Tool JSON (required for automatic function calling)**
- record_decision: use details_json as a JSON object string (default "{}").
- set_preference: value_json must be valid JSON (e.g. {\"focus_hours\":2} or \"Europe/London\").

**Rules**
- Never invent task or event ids; only use tool outputs.
- Prefer persisting facts via specialists over chat-only memory.
- Be concise: user-facing summary plus concrete next steps.
""".strip(),
    tools=_orchestrator_tools,
)
