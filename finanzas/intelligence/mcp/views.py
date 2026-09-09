"""MCP Streamable HTTP transport (JSON-RPC 2.0 over a single POST endpoint).

Real tool execution: authenticates the Bearer token, then delegates to
:func:`finanzas.intelligence.mcp.tools.execute`, which enforces scope, tenant
isolation, validation, pagination, rate limiting and audit.

Default network binding is inherited from the Django/WSGI server (``runserver``
binds ``127.0.0.1``); this view adds no listener of its own and must never be
exposed on ``0.0.0.0`` without an authenticating proxy.
"""

from __future__ import annotations

import json

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from finanzas.intelligence.mcp import tools as tool_registry
from finanzas.intelligence.mcp.models import MCPAccessToken

PROTOCOL_VERSION = "2025-06-18"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
UNAUTHORIZED = -32001


def _client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@method_decorator(csrf_exempt, name="dispatch")
class MCPStreamableHTTPView(View):
    """Single-endpoint MCP Streamable HTTP handler."""

    def _err(self, rid, code, message, http_status=200):
        return JsonResponse(
            {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}},
            status=http_status,
        )

    def _ok(self, rid, result):
        return JsonResponse({"jsonrpc": "2.0", "id": rid, "result": result})

    def _authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            return None
        return MCPAccessToken.resolve(header[7:].strip())

    def get(self, request):
        # SSE stream open is not required for the request/response tool flow.
        return JsonResponse({"status": "ok", "transport": "streamable-http"})

    def post(self, request):
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return self._err(None, PARSE_ERROR, "JSON invalido", 400)

        rid = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") or {}

        if payload.get("jsonrpc") != "2.0" or not method:
            return self._err(rid, INVALID_REQUEST, "Peticion JSON-RPC invalida", 400)

        if method == "initialize":
            return self._ok(rid, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "moneta", "version": "0.3.0"},
            })
        if method in ("notifications/initialized", "initialized"):
            return JsonResponse({}, status=202)
        if method == "ping":
            return self._ok(rid, {})

        token = self._authenticate(request)
        if token is None:
            return self._err(rid, UNAUTHORIZED, "Token Bearer ausente o invalido", 401)

        if method == "tools/list":
            return self._ok(rid, {"tools": tool_registry.list_tool_specs()})

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if not name:
                return self._err(rid, INVALID_PARAMS, "Falta 'name'")
            try:
                data = tool_registry.execute(
                    token, name, arguments, transport="http",
                    client_ip=_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
            except tool_registry.ScopeDenied as exc:
                return self._ok(rid, {
                    "isError": True,
                    "content": [{"type": "text", "text": str(exc)}],
                    "_meta": {"error_code": exc.code},
                })
            except tool_registry.ToolNotFound as exc:
                return self._err(rid, METHOD_NOT_FOUND, str(exc))
            except (tool_registry.InputInvalid, tool_registry.RateLimited) as exc:
                return self._ok(rid, {
                    "isError": True,
                    "content": [{"type": "text", "text": str(exc)}],
                    "_meta": {"error_code": exc.code},
                })
            except Exception:  # noqa: BLE001
                return self._err(rid, INTERNAL_ERROR, "Error interno ejecutando la herramienta")
            return self._ok(rid, {
                "content": [{"type": "text",
                             "text": json.dumps(data, ensure_ascii=False, default=str)}],
                "structuredContent": data,
                "isError": False,
            })

        return self._err(rid, METHOD_NOT_FOUND, f"Metodo no soportado: {method}")
