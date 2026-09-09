"""MCP URL configuration (Streamable HTTP transport)."""

from django.urls import path

from finanzas.intelligence.mcp.views import MCPStreamableHTTPView

app_name = "mcp"

urlpatterns = [
    path("", MCPStreamableHTTPView.as_view(), name="streamable_http"),
]
