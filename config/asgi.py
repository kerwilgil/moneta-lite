"""ASGI config.

Serves the Django app plus the Moneta MCP server over the official MCP SDK v2
Streamable HTTP transport, mounted at ``/mcp``.

Run in production with an ASGI server, e.g.::

    uvicorn config.asgi:application --host 127.0.0.1 --port 8001

The MCP endpoint is bound to loopback (the SDK enables DNS-rebinding
protection); front it with an authenticating reverse proxy to expose it further.
The stdio transport is ``python manage.py moneta_mcp_stdio``.
"""

import os
from contextlib import asynccontextmanager

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application  # noqa: E402

django_application = get_asgi_application()

from starlette.applications import Starlette  # noqa: E402
from starlette.routing import Mount  # noqa: E402

from finanzas.intelligence.mcp.server import build_mcp_server_and_app  # noqa: E402

_mcp_server, _mcp_app = build_mcp_server_and_app(path="/", stateless=True)


@asynccontextmanager
async def _lifespan(_app):
    # Starlette does not run a mounted app's lifespan, so drive the official
    # StreamableHTTPSessionManager here.
    async with _mcp_server.session_manager.run():
        yield


application = Starlette(
    routes=[
        Mount("/mcp", app=_mcp_app),
        Mount("", app=django_application),
    ],
    lifespan=_lifespan,
)
