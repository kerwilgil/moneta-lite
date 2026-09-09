"""Integrations settings routes (Moneta MCP token lifecycle UI)."""

from django.urls import path

from finanzas.intelligence.mcp import ui

app_name = "integrations"

urlpatterns = [
    path("mcp/", ui.mcp_settings, name="mcp"),
    path("mcp/tokens/nuevo/", ui.mcp_token_create, name="mcp_token_create"),
    path("mcp/tokens/<int:pk>/regenerar/", ui.mcp_token_regenerate, name="mcp_token_regenerate"),
    path("mcp/tokens/<int:pk>/revocar/", ui.mcp_token_revoke, name="mcp_token_revoke"),
    path("mcp/tokens/<int:pk>/estado/", ui.mcp_token_toggle, name="mcp_token_toggle"),
]
