"""AI provider foundation for Moneta v0.3.0.

This layer is **completely independent from MCP**.  It defines a narrow,
advisory contract.  AI output is never authoritative: it may propose a category,
extract fields from noisy text, or summarise context, but it can never approve a
draft, mutate a balance, or create a final :class:`FinancialTransaction`.

Moneta ships with :class:`DisabledProvider` as the default, so the product runs
fully **without AI, without an API key and without internet access**.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass(frozen=True)
class CategorySuggestion:
    category_id: int | None = None
    label: str = ""
    confidence: Decimal = Decimal("0.00")
    rationale: str = ""


@dataclass(frozen=True)
class ExtractedTransaction:
    merchant: str = ""
    description: str = ""
    amount: Decimal | None = None
    currency: str = ""
    transaction_date: str = ""
    transaction_type: str = ""
    confidence: Decimal = Decimal("0.00")
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ContextInsight:
    summary: str = ""
    observations: list = field(default_factory=list)
    confidence: Decimal = Decimal("0.00")


class AIProvider(abc.ABC):
    """Advisory-only AI contract.  Implementations must never mutate finance."""

    name = "base"
    #: Set to ``True`` only by providers that actually reach an AI model.
    is_enabled = False

    @abc.abstractmethod
    def categorize_transaction(self, *, description: str, merchant: str = "",
                               amount: Decimal | None = None,
                               candidates: list | None = None) -> CategorySuggestion:
        ...

    @abc.abstractmethod
    def extract_transaction(self, *, text: str,
                            hints: dict | None = None) -> ExtractedTransaction:
        ...

    @abc.abstractmethod
    def analyze_financial_context(self, *, summary: dict) -> ContextInsight:
        ...

    # Guardrail helpers -------------------------------------------------------
    def assert_advisory_only(self) -> None:
        """Structural reminder that providers hold no financial authority."""
        forbidden = {"approve", "create_transaction", "delete", "set_balance",
                     "confirm_payment"}
        offending = forbidden & {m for m in dir(self) if not m.startswith("_")}
        if offending:  # pragma: no cover - defensive
            raise RuntimeError(
                f"AIProvider {self.name} expone metodos con autoridad financiera: {offending}"
            )


class DisabledProvider(AIProvider):
    """Default provider: returns empty, zero-confidence advisory results.

    Never raises, never performs I/O, works offline.
    """

    name = "disabled"
    is_enabled = False

    def categorize_transaction(self, **_kwargs) -> CategorySuggestion:
        return CategorySuggestion(confidence=Decimal("0.00"),
                                  rationale="IA deshabilitada")

    def extract_transaction(self, *, text: str = "", **_kwargs) -> ExtractedTransaction:
        return ExtractedTransaction(confidence=Decimal("0.00"),
                                    raw={"note": "IA deshabilitada"})

    def analyze_financial_context(self, *, summary: dict) -> ContextInsight:
        return ContextInsight(summary="Analisis IA deshabilitado.",
                              confidence=Decimal("0.00"))


_PROVIDER_CACHE: dict[str, AIProvider] = {}


def get_provider() -> AIProvider:
    """Return the configured provider instance (``DisabledProvider`` by default).

    Controlled by ``settings.MONETA_AI_PROVIDER`` (dotted path).  Any import or
    construction failure falls back to :class:`DisabledProvider` so the app
    never breaks because of AI configuration.
    """
    path = getattr(settings, "MONETA_AI_PROVIDER", "") or ""
    if not path:
        return _PROVIDER_CACHE.setdefault("disabled", DisabledProvider())
    if path in _PROVIDER_CACHE:
        return _PROVIDER_CACHE[path]
    try:
        provider_cls = import_string(path)
        provider = provider_cls()
        if not isinstance(provider, AIProvider):  # pragma: no cover
            raise TypeError("MONETA_AI_PROVIDER no es un AIProvider")
        provider.assert_advisory_only()
    except Exception:  # noqa: BLE001 - never let AI config break the app
        provider = DisabledProvider()
    _PROVIDER_CACHE[path] = provider
    return provider


def ai_enabled() -> bool:
    return bool(get_provider().is_enabled)
