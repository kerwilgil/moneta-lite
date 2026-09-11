"""Moneta MCP server (official MCP Python SDK v2, low-level ``Server`` API).

The low-level ``Server`` is a first-class MCP SDK v2 API; it natively negotiates
the modern ``2026-07-28`` protocol, answers ``server/discover`` and works both
sessionless (modern) and via the legacy initialize handshake.

Transports (both official SDK v2):

* stdio  -> ``python manage.py moneta_mcp_stdio`` (``mcp.server.stdio.stdio_server``)
* HTTP   -> ``Server.streamable_http_app()`` mounted in :pyfile:`config/asgi.py`
           (``StreamableHTTPSessionManager`` + ``StreamableHTTPASGIApp``)

The transport authenticates and this module resolves the acting user
*exclusively* from the bearer token — from ``MONETA_MCP_TOKEN`` (stdio) or the
``Authorization`` header the HTTP transport attaches to the request context.
No client-supplied identity is ever trusted.
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

# Per-connection authenticated token for stream transports (stdio / in-memory).
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


def _bearer_from_request(request) -> str | None:
    if request is None:
        return None
    headers = getattr(request, "headers", None)
    if headers is None:
        return None
    try:
        value = headers.get("authorization") or headers.get("Authorization")
    except Exception:  # pragma: no cover - defensive
        value = None
    if value and value.lower().startswith("bearer "):
        return value[7:].strip()
    return None


async def _resolve_token(ctx):
    """Token for this request: context var (stream transports) or the HTTP
    request's ``Authorization`` header (Streamable HTTP transport)."""
    token = get_current_token()
    if token is not None:
        return await sync_to_async(
            MCPAccessToken.refresh_valid, thread_sensitive=True
        )(token)
    raw = _bearer_from_request(getattr(ctx, "request", None))
    if not raw:
        return None
    return await sync_to_async(MCPAccessToken.resolve, thread_sensitive=True)(raw)


async def _on_list_tools(ctx, _params):
    # Discovery of the tool surface still requires a valid token.
    token = await _resolve_token(ctx)
    if token is None:
        raise AuthError("Token MCP ausente, invalido o revocado.")
    tools = [
        mcp_types.Tool(
            name=spec["name"],
            description=spec["description"],
            inputSchema=spec["inputSchema"],
        )
        for spec in tool_registry.list_tool_specs()
    ]
    return mcp_types.ListToolsResult(tools=tools)


async def _on_call_tool(ctx, params):
    token = await _resolve_token(ctx)
    name = params.name
    arguments = params.arguments or {}
    transport = "http" if getattr(ctx, "request", None) is not None else "stdio"

    if token is None:
        return mcp_types.CallToolResult(
            content=[mcp_types.TextContent(
                type="text",
                text=json.dumps({"ok": False, "error_code": "unauthenticated",
                                 "error": "Token MCP ausente o invalido."}),
            )],
            is_error=True,
        )

    client_ip = None
    user_agent = ""
    req = getattr(ctx, "request", None)
    if req is not None:
        try:
            client_ip = req.client.host if req.client else None
            user_agent = req.headers.get("user-agent", "")
        except Exception:  # pragma: no cover
            pass

    try:
        data = await sync_to_async(tool_registry.execute, thread_sensitive=True)(
            token, name, arguments, transport=transport,
            client_ip=client_ip, user_agent=user_agent,
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
    """Return a configured low-level MCP :class:`Server` (modern + legacy capable)."""
    return Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        instructions="Moneta personal finance MCP server (read + draft tools).",
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
    )


def build_mcp_server_and_app(*, path: str = "/", stateless: bool = True):
    """Return ``(server, starlette_app)`` for the official SDK v2 Streamable HTTP
    transport.

    ``stateless=True`` selects the modern ``2026-07-28`` sessionless path (no
    initialize handshake, no ``Mcp-Session-Id``); the SDK still serves legacy
    clients on the same endpoint. Binds to ``127.0.0.1`` with DNS-rebinding
    protection auto-enabled by the SDK.

    When mounting ``starlette_app`` inside another ASGI app, drive
    ``server.session_manager.run()`` from that parent app's lifespan (Starlette
    does not propagate a mounted app's lifespan automatically). When the app is
    served standalone, its own lifespan handles it.
    """
    server = build_server()
    app = server.streamable_http_app(
        streamable_http_path=path,
        stateless_http=stateless,
        json_response=True,
        host="127.0.0.1",
    )
    return server, app


def build_streamable_http_app(*, path: str = "/", stateless: bool = True):
    """Standalone official SDK v2 Streamable HTTP ASGI app (its own lifespan)."""
    _server, app = build_mcp_server_and_app(path=path, stateless=stateless)
    return app
