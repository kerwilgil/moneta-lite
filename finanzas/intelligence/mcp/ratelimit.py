"""Server-side rate limiting for MCP tool execution.

Fixed-window counters kept in the Django cache, keyed by ``(user, tool-bucket)``.
Limits are configurable through ``settings.MONETA_MCP_RATE_LIMITS``.
"""

from __future__ import annotations

import time

from django.conf import settings
from django.core.cache import cache


DEFAULT_LIMITS = {
    "__all__": (120, 60),
    "default": (120, 60),
    "moneta.create_import_batch": (30, 60),
    "moneta.create_transaction_draft": (60, 60),
    "moneta.search_transactions": (60, 60),
}


class RateLimitExceeded(Exception):
    def __init__(self, tool, limit, window):
        self.tool = tool
        self.limit = limit
        self.window = window
        super().__init__(
            f"Rate limit excedido para '{tool}': {limit} llamadas / {window}s."
        )


def _limits():
    configured = getattr(settings, "MONETA_MCP_RATE_LIMITS", None) or {}
    merged = dict(DEFAULT_LIMITS)
    merged.update(configured)
    return merged


def limit_for(tool: str):
    limits = _limits()
    return limits.get(tool, limits["default"])


def check(user_id: int, tool: str) -> None:
    """Increment the window counter for ``user_id``/``tool``; raise if over."""
    max_calls, window = limit_for(tool)
    if max_calls <= 0:
        return
    now = int(time.time())
    bucket = now // window
    key = f"mcp-rl:{user_id}:{tool}:{bucket}"
    try:
        added = cache.add(key, 1, timeout=window + 5)
        current = 1 if added else cache.incr(key)
    except ValueError:
        # key expired between add and incr
        cache.set(key, 1, timeout=window + 5)
        current = 1
    if current > max_calls:
        raise RateLimitExceeded(tool, max_calls, window)


def should_audit_global_limit(user_id: int) -> bool:
    """Return true once per global window so denied-call auditing stays bounded."""
    _, window = limit_for("__all__")
    bucket = int(time.time()) // window
    key = f"mcp-rl-audit:{user_id}:{bucket}"
    return cache.add(key, 1, timeout=window + 5)


def reset(user_id: int, tool: str) -> None:
    """Test helper: clear every window for this user/tool pair."""
    now = int(time.time())
    _, window = limit_for(tool)
    for bucket in (now // window, now // window - 1, now // window + 1):
        cache.delete(f"mcp-rl:{user_id}:{tool}:{bucket}")
        if tool == "__all__":
            cache.delete(f"mcp-rl-audit:{user_id}:{bucket}")
