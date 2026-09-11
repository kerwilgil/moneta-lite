"""MCP (Model Context Protocol) models: access tokens and audit log."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


SCOPE_READ = "read"
SCOPE_DRAFT = "draft"
VALID_SCOPES = (SCOPE_READ, SCOPE_DRAFT)

TOKEN_PREFIX_LEN = 8


def _pepper() -> bytes:
    """Server-side pepper for token hashing.

    Uses a dedicated setting when present, otherwise derives from ``SECRET_KEY``
    so a database leak alone never exposes usable tokens.
    """
    configured = getattr(settings, "MONETA_MCP_TOKEN_PEPPER", "") or ""
    base = configured or f"moneta-mcp::{settings.SECRET_KEY}"
    return base.encode("utf-8")


def hash_token(raw_token: str) -> str:
    """Return the peppered HMAC-SHA256 hex digest of a raw token."""
    return hmac.new(_pepper(), raw_token.encode("utf-8"), hashlib.sha256).hexdigest()


class MCPAccessToken(models.Model):
    """A per-user bearer token for the Moneta MCP server."""

    class Scope(models.TextChoices):
        READ = SCOPE_READ, _("Lectura")
        DRAFT = SCOPE_DRAFT, _("Borradores")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mcp_tokens",
    )
    name = models.CharField(max_length=100, help_text=_("Nombre legible del token"))
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    token_prefix = models.CharField(max_length=TOKEN_PREFIX_LEN, editable=False)
    scopes = models.JSONField(default=list, help_text=_("Lista de scopes concedidos"))
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "enabled"]),
            models.Index(fields=["token_prefix"]),
        ]

    def __str__(self):
        return f"MCPAccessToken({self.name} - {self.token_prefix}...)"

    # -- creation / verification ------------------------------------------- #
    @staticmethod
    def generate_raw_token() -> str:
        return "mmcp_" + secrets.token_urlsafe(32)  # ~256 bits

    @classmethod
    def issue(cls, user, name, scopes):
        """Create a token; returns ``(instance, raw_token)``.

        The raw token is returned exactly once and never stored in plaintext.
        """
        clean_scopes = [s for s in (scopes or []) if s in VALID_SCOPES]
        if not clean_scopes:
            clean_scopes = [SCOPE_READ]
        raw = cls.generate_raw_token()
        token = cls.objects.create(
            user=user,
            name=(name or "MCP token").strip()[:100],
            token_hash=hash_token(raw),
            token_prefix=raw[:TOKEN_PREFIX_LEN],
            scopes=clean_scopes,
        )
        return token, raw

    def verify(self, raw_token: str) -> bool:
        if not raw_token:
            return False
        return hmac.compare_digest(hash_token(raw_token), self.token_hash)

    @classmethod
    def resolve(cls, raw_token: str):
        """Return a valid, enabled, non-revoked token for ``raw_token`` or ``None``.

        Lookup is by the full peppered hash (indexed, unique); the comparison is
        therefore constant-time at the DB level and does not leak via prefix.
        """
        if not raw_token or not isinstance(raw_token, str):
            return None
        token = cls.objects.select_related("user").filter(
            token_hash=hash_token(raw_token),
            enabled=True,
            revoked_at__isnull=True,
            user__is_active=True,
        ).first()
        if token is None or not token.is_valid:
            return None
        return token

    @classmethod
    def refresh_valid(cls, token):
        """Reload a cached transport credential and re-check its owner."""
        if token is None or not getattr(token, "pk", None):
            return None
        return cls.objects.select_related("user").filter(
            pk=token.pk,
            token_hash=token.token_hash,
            enabled=True,
            revoked_at__isnull=True,
            user__is_active=True,
        ).first()

    # -- lifecycle -------------------------------------------------------- #
    def revoke(self):
        self.revoked_at = timezone.now()
        self.enabled = False
        self.save(update_fields=["enabled", "revoked_at", "updated_at"])

    def touch(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at", "updated_at"])

    @property
    def is_valid(self) -> bool:
        return bool(
            self.enabled
            and self.revoked_at is None
            and getattr(self.user, "is_active", False)
        )

    @property
    def scope_list(self):
        return [s for s in (self.scopes or []) if s in VALID_SCOPES]

    def has_scope(self, scope: str) -> bool:
        scopes = self.scope_list
        if scope == SCOPE_READ:
            # draft implies read
            return SCOPE_READ in scopes or SCOPE_DRAFT in scopes
        return scope in scopes

    @property
    def safe_identifier(self) -> str:
        return f"{self.token_prefix}…#{self.pk}"


class MCPAuditEvent(models.Model):
    """Audit trail for every MCP tool execution."""

    class Result(models.TextChoices):
        SUCCESS = "success", "Exito"
        FAILURE = "failure", "Fallo"
        DENIED = "denied", "Denegado"
        ERROR = "error", "Error"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mcp_audit_events",
    )
    token = models.ForeignKey(
        MCPAccessToken,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    token_identifier = models.CharField(max_length=64, blank=True)
    transport = models.CharField(max_length=16, blank=True)  # stdio | http
    tool = models.CharField(max_length=100)
    scope = models.CharField(max_length=20)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    result = models.CharField(max_length=10, choices=Result.choices)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    object_reference = models.CharField(max_length=100, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["token", "-timestamp"]),
            models.Index(fields=["tool", "-timestamp"]),
        ]

    def __str__(self):
        return f"MCPAuditEvent({self.tool} - {self.result})"

    @classmethod
    def record(cls, *, user, token, tool, scope, result, transport="",
               duration_ms=None, object_reference="", error_code="",
               client_ip=None, user_agent=""):
        return cls.objects.create(
            user=user,
            token=token,
            token_identifier=(token.safe_identifier if token else ""),
            transport=transport,
            tool=str(tool or "")[:100],
            scope=str(scope or "")[:20],
            result=result,
            duration_ms=duration_ms,
            object_reference=str(object_reference or "")[:100],
            error_code=str(error_code or "")[:50],
            client_ip=client_ip,
            user_agent=str(user_agent or "")[:300],
        )
