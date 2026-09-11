"""Settings UI: Configuracion -> Integraciones -> Moneta MCP.

Manages the lifecycle of :class:`MCPAccessToken` rows for the current user.
The raw token is shown exactly once in the POST response and is never stored.
"""

from __future__ import annotations

import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from finanzas.intelligence.mcp.models import MCPAccessToken, VALID_SCOPES


REVEAL_NONCE_SESSION_KEY = "mcp_reveal_nonce"


def _new_reveal_nonce(request):
    nonce = secrets.token_urlsafe(32)
    request.session[REVEAL_NONCE_SESSION_KEY] = nonce
    return nonce


def _consume_reveal_nonce(request):
    expected = request.session.pop(REVEAL_NONCE_SESSION_KEY, "")
    supplied = request.POST.get("reveal_nonce", "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))

def _render_settings(request, revealed=None):
    tokens = MCPAccessToken.objects.filter(user=request.user).order_by("-created_at")
    context = {
        "tokens": tokens,
        "revealed": revealed,
        "valid_scopes": VALID_SCOPES,
        "http_endpoint": request.build_absolute_uri("/mcp/"),
        "stdio_command": "python manage.py moneta_mcp_stdio",
        "reveal_nonce": _new_reveal_nonce(request),
    }
    return render(request, "finanzas/mcp_settings.html", context)


@login_required
@never_cache
def mcp_settings(request):
    return _render_settings(request)


@login_required
@never_cache
@require_http_methods(["POST"])
def mcp_token_create(request):
    if not _consume_reveal_nonce(request):
        messages.error(request, _("Formulario expirado. Intenta de nuevo."))
        return redirect(reverse("integrations:mcp"))
    name = (request.POST.get("name") or "").strip() or _("Token MCP")
    scopes = request.POST.getlist("scopes") or ["read"]
    scopes = [s for s in scopes if s in VALID_SCOPES] or ["read"]
    token, raw = MCPAccessToken.issue(request.user, name, scopes)
    revealed = {
        "raw": raw, "prefix": token.token_prefix, "name": token.name,
        "scopes": token.scope_list,
    }
    messages.success(
        request,
        _("Token creado. Copialo ahora: no se volvera a mostrar."),
    )
    return _render_settings(request, revealed)


@login_required
@never_cache
@require_http_methods(["POST"])
def mcp_token_regenerate(request, pk):
    if not _consume_reveal_nonce(request):
        messages.error(request, _("Formulario expirado. Intenta de nuevo."))
        return redirect(reverse("integrations:mcp"))
    old = get_object_or_404(MCPAccessToken, pk=pk, user=request.user)
    name, scopes = old.name, old.scope_list
    old.revoke()
    token, raw = MCPAccessToken.issue(request.user, name, scopes)
    revealed = {
        "raw": raw, "prefix": token.token_prefix, "name": token.name,
        "scopes": token.scope_list,
    }
    messages.success(request, _("Token regenerado. El anterior quedo revocado."))
    return _render_settings(request, revealed)


@login_required
@require_http_methods(["POST"])
def mcp_token_revoke(request, pk):
    token = get_object_or_404(MCPAccessToken, pk=pk, user=request.user)
    token.revoke()
    messages.success(request, _("Token revocado."))
    return redirect(reverse("integrations:mcp"))


@login_required
@require_http_methods(["POST"])
def mcp_token_toggle(request, pk):
    token = get_object_or_404(MCPAccessToken, pk=pk, user=request.user)
    if token.revoked_at is not None:
        messages.error(request, _("Un token revocado no se puede reactivar."))
        return redirect(reverse("integrations:mcp"))
    token.enabled = not token.enabled
    token.save(update_fields=["enabled", "updated_at"])
    messages.success(
        request,
        _("Token habilitado.") if token.enabled else _("Token deshabilitado."),
    )
    return redirect(reverse("integrations:mcp"))
