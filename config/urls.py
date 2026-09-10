from django.contrib import admin
from django.urls import include, path

from finanzas.views import login_view

# NOTE: the MCP server's Streamable HTTP transport is NOT a Django view. It is the
# official MCP SDK v2 ASGI app mounted at /mcp in config/asgi.py. Serve with an
# ASGI server (uvicorn config.asgi:application). The stdio transport is the
# `moneta_mcp_stdio` management command.

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", login_view, name="login"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("importaciones/", include("finanzas.intelligence.imports.urls")),
    path("configuracion/integraciones/", include("finanzas.intelligence.mcp.ui_urls")),
    path("ayuda/", include("finanzas.help_urls")),
    path("", include("finanzas.urls")),
]
