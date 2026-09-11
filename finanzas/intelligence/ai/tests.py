"""AI foundation tests: advisory-only, offline by default."""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase, override_settings

from finanzas.intelligence.ai import (
    AIProvider,
    DisabledProvider,
    ai_enabled,
    get_provider,
)
from finanzas.intelligence.ai.base import _PROVIDER_CACHE


class AIFoundationTests(SimpleTestCase):
    def setUp(self):
        _PROVIDER_CACHE.clear()

    def test_default_provider_is_disabled(self):
        provider = get_provider()
        self.assertIsInstance(provider, DisabledProvider)
        self.assertFalse(ai_enabled())

    def test_disabled_provider_works_without_ai_key_or_internet(self):
        provider = get_provider()
        cat = provider.categorize_transaction(description="Cafe", merchant="Shop")
        self.assertEqual(cat.confidence, Decimal("0.00"))
        extracted = provider.extract_transaction(text="pago 10 usd cafe")
        self.assertEqual(extracted.confidence, Decimal("0.00"))
        insight = provider.analyze_financial_context(summary={"income": 0})
        self.assertEqual(insight.confidence, Decimal("0.00"))

    def test_provider_is_advisory_only(self):
        provider = get_provider()
        for forbidden in ("approve", "create_transaction", "set_balance",
                          "confirm_payment", "delete"):
            self.assertFalse(hasattr(provider, forbidden))

    @override_settings(MONETA_AI_PROVIDER="does.not.Exist")
    def test_bad_provider_path_falls_back_to_disabled(self):
        _PROVIDER_CACHE.clear()
        self.assertIsInstance(get_provider(), DisabledProvider)

    def test_contract_surface(self):
        self.assertTrue(issubclass(DisabledProvider, AIProvider))
        for method in ("categorize_transaction", "extract_transaction",
                       "analyze_financial_context"):
            self.assertTrue(callable(getattr(DisabledProvider, method)))
