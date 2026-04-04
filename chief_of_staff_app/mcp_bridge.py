"""Optional Streamable HTTP MCP toolsets (Workspace, Slack, Jira, etc.)."""

from __future__ import annotations

import json
import os
from typing import Any


def extra_mcp_toolsets() -> list[Any]:
    """
    If CHIEF_OF_STAFF_MCP_URL is set, attach one remote MCP server.

    Optional JSON headers in CHIEF_OF_STAFF_MCP_HEADERS.

    For multiple backends in production, use a single MCP gateway or compose
    tool servers per https://github.com/google/mcp — e.g. Google Workspace
    (Calendar/Gmail), Asana/Jira, Slack.
    """
    url = os.getenv("CHIEF_OF_STAFF_MCP_URL", "").strip()
    if not url:
        return []

    try:
        from google.adk.tools.mcp_tool.mcp_session_manager import (
            StreamableHTTPConnectionParams,
        )
        from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
    except ImportError:
        return []

    headers: dict[str, str] = {}
    raw = os.getenv("CHIEF_OF_STAFF_MCP_HEADERS", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                headers = {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError:
            headers = {}

    toolset = MCPToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=url,
            headers=headers,
            timeout=30.0,
            sse_read_timeout=300.0,
        )
    )
    return [toolset]
