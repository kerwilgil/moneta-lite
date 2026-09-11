"""AI foundation (advisory only, disabled by default)."""

from finanzas.intelligence.ai.base import (
    AIProvider,
    CategorySuggestion,
    ContextInsight,
    DisabledProvider,
    ExtractedTransaction,
    ai_enabled,
    get_provider,
)

__all__ = [
    "AIProvider",
    "DisabledProvider",
    "CategorySuggestion",
    "ExtractedTransaction",
    "ContextInsight",
    "get_provider",
    "ai_enabled",
]
