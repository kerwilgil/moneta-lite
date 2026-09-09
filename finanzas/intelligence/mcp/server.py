"""Moneta MCP server (official MCP Python SDK v2, low-level ``Server`` API).

The transport authenticates and supplies an :class:`MCPAccessToken`; the server
never trusts client-supplied identity.  The same tool registry
(:mod:`finanzas.intelligence.mcp.tools`) backs stdio and Streamable HTTP.

* stdio -> :pyfile:`finanzas/management/commands/moneta_mcp_stdio.py`
* HTTP  -> :class:`finanzas.intelligence.mcp.views.MCPStreamableHTTPView`
"""

from __future__ import annotations

import contextvars
import json
import logging

from asgiref.sync import sync_to_async

from mcp.server.lowlevel import Server
import mcp.types as mcp_types

from finanzas.intelligence.mcp import tools as tool_registry
from finanzas.intelligence.mcp.models import MCPAccessToken

logger = logging.getLogger("moneta.mcp")

SERVER_NAME = "moneta"
SERVER_VERSION = "0.3.0"

# Per-connection authenticated token (set by the transport before serving).
_current_token: contextvars.ContextVar = contextvars.ContextVar(
    "moneta_mcp_token", default=None
)


class AuthError(Exception):
    pass


def set_current_token(token):
    return _current_token.set(token)


def get_current_token():
    return _current_token.get()


def resolve_env_token(raw_token):
    """Resolve a raw token string to a valid :class:`MCPAccessToken` or ``None``."""
    if not raw_token:
        return None
    return MCPAccessToken.resolve(str(raw_token).strip())


async def _on_list_tools(_ctx, _params):
    tools = [
        mcp_types.Tool(
            name=spec["name"],
            description=spec["description"],
            inputSchema=spec["inputSchema"],
        )
        for spec in tool_registry.list_tool_specs()
    ]
    return mcp_types.ListToolsResult(tools=tools)


async def _on_call_tool(_ctx, params):
    token = get_current_token()
    name = params.name
    arguments = params.arguments or {}

    if token is None:
        return mcp_types.CallToolResult(
            content=[mcp_types.TextContent(
                type="text",
                text=json.dumps({"ok": False, "error_code": "unauthenticated",
                                 "error": "Token MCP ausente o invalido."}),
            )],
            is_error=True,
        )

    try:
        data = await sync_to_async(tool_registry.execute, thread_sensitive=True)(
            token, name, arguments, transport="stdio",
        )
    except tool_registry.MCPToolError as exc:
        return mcp_types.CallToolResult(
            content=[mcp_types.TextContent(
                type="text",
                text=json.dumps({"ok": False, "error_code": exc.code,
                                 "error": str(exc)}, ensure_ascii=False),
            )],
            is_error=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("MCP tool %s failed", name)
        return mcp_types.CallToolResult(
            content=[mcp_types.TextContent(
                type="text",
                text=json.dumps({"ok": False, "error_code": type(exc).__name__,
                                 "error": "error interno"}),
            )],
            is_error=True,
        )

    payload = json.dumps({"ok": True, "data": data}, ensure_ascii=False, default=str)
    return mcp_types.CallToolResult(
        content=[mcp_types.TextContent(type="text", text=payload)],
        structured_content=data,
        is_error=False,
    )


def build_server() -> Server:
    """Return a configured low-level MCP :class:`Server`."""
    return Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        instructions="Moneta personal finance MCP server (read + draft tools).",
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
    )
