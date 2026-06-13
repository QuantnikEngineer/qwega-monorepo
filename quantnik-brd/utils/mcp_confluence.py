"""utils/mcp_confluence.py

Google ADK ↔ mcp-atlassian Confluence integration.

Provides a lazily-initialised ``McpToolset`` that connects to the
``mcp-atlassian`` MCP server (stdio transport).  The toolset exposes
Confluence read/write tools (search, get_page, update_page, create_page,
get_page_children, etc.) to any Google ADK ``LlmAgent``.

Usage in an agent definition:

    from utils.mcp_confluence import get_confluence_toolset

    agent = LlmAgent(
        ...
        tools=[get_confluence_toolset()],
    )

Environment variables consumed (via .env / os.environ):
    CONFLUENCE_PARENT_PAGE_URL – full Confluence page URL (preferred)
    CONFLUENCE_EMAIL           – Atlassian account email
    CONFLUENCE_API_TOKEN       – API token
"""
from __future__ import annotations

import logging
import os
import sys
import threading

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_toolset import StdioConnectionParams
from mcp import StdioServerParameters

from utils.confluence_config import load_confluence_settings

logger = logging.getLogger(__name__)

# Singleton — created once, reused across agents.
_toolset: McpToolset | None = None
_toolset_lock = threading.Lock()


def _resolve_mcp_command() -> tuple[str, list[str]]:
    """Build the command + args to launch mcp-atlassian in stdio mode.

    Prefers the venv-installed ``mcp-atlassian`` executable.  Falls back
    to running via ``python -c`` if the executable is not found.
    """
    # Look for entry-point script next to the current Python interpreter
    venv_scripts = os.path.dirname(sys.executable)
    exe_name = "mcp-atlassian.exe" if sys.platform == "win32" else "mcp-atlassian"
    exe_path = os.path.join(venv_scripts, exe_name)

    if os.path.isfile(exe_path):
        return exe_path, []

    # Fallback: run via python module invocation
    return sys.executable, ["-c", "from mcp_atlassian import main; main()"]


def get_confluence_toolset() -> McpToolset:
    """Return a reusable ``McpToolset`` wired to the mcp-atlassian server.
    
    Thread-safe: uses double-checked locking to ensure only one toolset
    is created even under concurrent access.
    """
    global _toolset
    if _toolset is not None:
        return _toolset

    with _toolset_lock:
        # Double-check after acquiring lock
        if _toolset is not None:
            return _toolset

        cfg = load_confluence_settings()

        command, base_args = _resolve_mcp_command()

        args = base_args + [
            "--transport", "stdio",
            "--confluence-url", cfg.base_url,
            "--confluence-username", cfg.email,
            "--confluence-token", cfg.api_token,
        ]

        logger.info(
            "Creating MCP Confluence toolset: command=%s, url=%s, user=%s",
            command, cfg.base_url, cfg.email,
        )

        _toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=command,
                    args=args,
                ),
                timeout=30,
            ),
        )

        logger.info("MCP Confluence toolset created successfully.")
        return _toolset
