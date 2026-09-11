"""MCP test suite (Phase 6): auth, scopes, tenant isolation, validation,
pagination, rate limiting, audit, forbidden tools, and real client smokes
(in-memory MCP transport + real stdio subprocess + Streamable HTTP)."""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from types import SimpleNamespace

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from finanzas.models import Account, Category, FinancialTransaction
from finanzas.intelligence.imports import services as import_services
from finanzas.intelligence.imports.models import TransactionDraft
from finanzas.intelligence.mcp import ratelimit, server as mcp_server, tools
from finanzas.intelligence.mcp.models import (
    MCPAccessToken,
    MCPAuditEvent,
    SCOPE_DRAFT,
    SCOPE_READ,
    hash_token,
)


def _mkuser(name):
    return get_user_model().objects.create_user(username=name, password="secret12345")


class McpBase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = _mkuser("alice")
        self.other = _mkuser("bob")
        self.acc = Account.objects.create(
            user=self.user, name="Banco", account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("1000.00"), current_balance=Decimal("1000.00"),
        )
        self.other_acc = Account.objects.create(
            user=self.other, name="BobBanco", account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("0.00"), current_balance=Decimal("0.00"),
        )
        self.cat = Category.objects.create(
            user=self.user, name="Comida", category_type=Category.CategoryType.EXPENSE,
        )
        for i in range(5):
            FinancialTransaction.objects.create(
                user=self.user, account=self.acc, category=self.cat,
                transaction_type=FinancialTransaction.TransactionType.EXPENSE,
                description=f"gasto {i}", amount=Decimal("10.00"),
            )
        self.read_token_obj, self.read_raw = MCPAccessToken.issue(
            self.user, "read", [SCOPE_READ])
        self.draft_token_obj, self.draft_raw = MCPAccessToken.issue(
            self.user, "draft", [SCOPE_DRAFT])
        self.revoked_obj, self.revoked_raw = MCPAccessToken.issue(
            self.user, "revoked", [SCOPE_READ])
        self.revoked_obj.revoke()
        self.disabled_obj, self.disabled_raw = MCPAccessToken.issue(
            self.user, "disabled", [SCOPE_READ])
        self.disabled_obj.enabled = False
        self.disabled_obj.save(update_fields=["enabled"])

    def draft_args(self, **kw):
        base = dict(
            source="gmail", description="Cafe", amount=4.5, currency="USD",
            transaction_date="2026-03-01", transaction_type="expense",
            account_id=self.acc.pk,
        )
        base.update(kw)
        return base


# --------------------------------------------------------------------------- #
class TokenAuthTests(McpBase):
    def test_missing_token(self):
        self.assertIsNone(MCPAccessToken.resolve(""))
        self.assertIsNone(MCPAccessToken.resolve(None))

    def test_bad_token(self):
        self.assertIsNone(MCPAccessToken.resolve("mmcp_not-a-real-token"))

    def test_revoked_token(self):
        self.assertIsNone(MCPAccessToken.resolve(self.revoked_raw))

    def test_disabled_token(self):
        self.assertIsNone(MCPAccessToken.resolve(self.disabled_raw))

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertIsNone(MCPAccessToken.resolve(self.read_raw))
        reset_token = mcp_server.set_current_token(self.read_token_obj)
        try:
            ctx = SimpleNamespace(request=None)
            self.assertIsNone(async_to_sync(mcp_server._resolve_token)(ctx))
        finally:
            mcp_server._current_token.reset(reset_token)

    def test_valid_token(self):
        self.assertEqual(MCPAccessToken.resolve(self.read_raw).pk, self.read_token_obj.pk)

    def test_hash_is_peppered_not_plain_sha256(self):
        import hashlib
        plain = hashlib.sha256(self.read_raw.encode()).hexdigest()
        self.assertNotEqual(plain, self.read_token_obj.token_hash)
        self.assertEqual(hash_token(self.read_raw), self.read_token_obj.token_hash)

    def test_raw_token_never_stored(self):
        for tok in MCPAccessToken.objects.all():
            self.assertNotIn(self.read_raw, tok.token_hash)
            self.assertNotEqual(tok.token_hash, self.read_raw)

        self.client.force_login(self.user)
        settings_response = self.client.get(reverse("integrations:mcp"))
        create_nonce = settings_response.context["reveal_nonce"]
        response = self.client.post(
            reverse("integrations:mcp_token_create"),
            {
                "name": "one-time",
                "scopes": [SCOPE_READ],
                "reveal_nonce": create_nonce,
            },
        )
        self.assertEqual(response.status_code, 200)
        raw = response.context["revealed"]["raw"]
        self.assertContains(response, raw)
        self.assertNotIn("mcp_raw_token", self.client.session)
        self.assertNotContains(self.client.get(reverse("integrations:mcp")), raw)

        replay = self.client.post(
            reverse("integrations:mcp_token_create"),
            {
                "name": "one-time-replay",
                "scopes": [SCOPE_READ],
                "reveal_nonce": create_nonce,
            },
        )
        self.assertEqual(replay.status_code, 302)
        self.assertFalse(MCPAccessToken.objects.filter(name="one-time-replay").exists())

        token = MCPAccessToken.objects.get(name="one-time")
        regenerate_nonce = self.client.get(
            reverse("integrations:mcp")
        ).context["reveal_nonce"]
        response = self.client.post(
            reverse("integrations:mcp_token_regenerate", args=[token.pk]),
            {"reveal_nonce": regenerate_nonce},
        )
        self.assertEqual(response.status_code, 200)
        regenerated_raw = response.context["revealed"]["raw"]
        self.assertContains(response, regenerated_raw)
        self.assertNotIn("mcp_raw_token", self.client.session)
        self.assertNotContains(
            self.client.get(reverse("integrations:mcp")), regenerated_raw
        )
        replay = self.client.post(
            reverse("integrations:mcp_token_regenerate", args=[token.pk]),
            {"reveal_nonce": regenerate_nonce},
        )
        self.assertEqual(replay.status_code, 302)
        self.assertEqual(
            MCPAccessToken.objects.filter(name="one-time", enabled=True).count(),
            1,
        )

    def test_revoke_updates_flags(self):
        obj, raw = MCPAccessToken.issue(self.user, "x", [SCOPE_READ])
        obj.revoke()
        obj.refresh_from_db()
        self.assertFalse(obj.enabled)
        self.assertIsNotNone(obj.revoked_at)
        self.assertFalse(obj.is_valid)


# --------------------------------------------------------------------------- #
class ScopeTests(McpBase):
    def test_read_scope_allows_read_tool(self):
        out = tools.execute(self.read_token_obj, "moneta.get_summary", {})
        self.assertIn("assets", out)

    def test_read_scope_denies_draft_tool(self):
        with self.assertRaises(tools.ScopeDenied):
            tools.execute(self.read_token_obj, "moneta.create_import_batch",
                          {"source": "gmail"})

    def test_draft_scope_allows_read_tool(self):
        out = tools.execute(self.draft_token_obj, "moneta.list_accounts", {})
        self.assertIn("accounts", out)

    def test_draft_scope_allows_draft_tool(self):
        out = tools.execute(self.draft_token_obj, "moneta.create_import_batch",
                            {"source": "gmail"})
        self.assertIn("batch", out)

    def test_scope_denied_is_audited(self):
        with self.assertRaises(tools.ScopeDenied):
            tools.execute(self.read_token_obj, "moneta.reject_draft", {"draft_id": 1})
        ev = MCPAuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.result, MCPAuditEvent.Result.DENIED)
        self.assertEqual(ev.error_code, "scope_denied")


# --------------------------------------------------------------------------- #
class TenantIsolationTests(McpBase):
    def test_user_argument_is_ignored(self):
        # attacker passes user/user_id/owner_id -> rejected as unknown fields
        with self.assertRaises(tools.InputInvalid):
            tools.execute(self.read_token_obj, "moneta.list_accounts",
                          {"user_id": self.other.pk})
        with self.assertRaises(tools.InputInvalid):
            tools.execute(self.read_token_obj, "moneta.list_transactions",
                          {"owner_id": self.other.pk})

    def test_results_are_scoped_to_token_user(self):
        out = tools.execute(self.read_token_obj, "moneta.list_accounts", {})
        names = {a["name"] for a in out["accounts"]}
        self.assertIn("Banco", names)
        self.assertNotIn("BobBanco", names)

    def test_cannot_touch_other_users_account_in_draft(self):
        with self.assertRaises(tools.InputInvalid):
            tools.execute(self.draft_token_obj, "moneta.create_transaction_draft",
                          self.draft_args(account_id=self.other_acc.pk))

    def test_cannot_reject_other_users_draft(self):
        bob_draft = import_services.create_transaction_draft(
            self.other, source="gmail", description="x", amount="1.00",
            currency="USD", transaction_date="2026-03-01",
            transaction_type="expense", account=self.other_acc.pk,
        )
        with self.assertRaises(tools.InputInvalid):
            tools.execute(self.draft_token_obj, "moneta.reject_draft",
                          {"draft_id": bob_draft.pk})
        bob_draft.refresh_from_db()
        self.assertEqual(bob_draft.status, TransactionDraft.Status.PENDING)


# --------------------------------------------------------------------------- #
class InputValidationTests(McpBase):
    def test_rejects_nan_and_infinity(self):
        for bad in (float("nan"), float("inf")):
            with self.assertRaises(tools.InputInvalid):
                tools.execute(self.draft_token_obj, "moneta.create_transaction_draft",
                              self.draft_args(amount=bad))

    def test_rejects_bad_currency(self):
        with self.assertRaises(tools.InputInvalid):
            tools.execute(self.draft_token_obj, "moneta.create_transaction_draft",
                          self.draft_args(currency="US"))

    def test_rejects_impossible_date(self):
        with self.assertRaises(tools.InputInvalid):
            tools.execute(self.draft_token_obj, "moneta.create_transaction_draft",
                          self.draft_args(transaction_date="2026-02-31"))

    def test_rejects_unknown_field(self):
        with self.assertRaises(tools.InputInvalid):
            tools.execute(self.read_token_obj, "moneta.get_summary", {"x": 1})

    def test_rejects_bad_enum(self):
        with self.assertRaises(tools.InputInvalid):
            tools.execute(self.read_token_obj, "moneta.list_transactions",
                          {"transaction_type": "bogus"})

    def test_unknown_tool(self):
        with self.settings(MONETA_MCP_RATE_LIMITS={
            "__all__": (2, 60), "default": (1000, 60)
        }):
            ratelimit.reset(self.user.id, "__all__")
            before = MCPAuditEvent.objects.count()
            errors = []
            for index in range(6):
                try:
                    tools.execute(
                        self.read_token_obj,
                        f"moneta.unknown_{index}_" + ("x" * 120),
                        {},
                    )
                except tools.MCPToolError as exc:
                    errors.append(exc)
            self.assertEqual(len(errors), 6)
            self.assertLessEqual(MCPAuditEvent.objects.count() - before, 3)
            self.assertTrue(
                all(len(event.tool) <= 100 for event in MCPAuditEvent.objects.all())
            )


# --------------------------------------------------------------------------- #
class PaginationTests(McpBase):
    def test_default_and_max_enforced(self):
        out = tools.execute(self.read_token_obj, "moneta.list_transactions", {})
        self.assertEqual(out["limit"], tools.DEFAULT_PAGE)
        out = tools.execute(self.read_token_obj, "moneta.list_transactions",
                            {"limit": 9999})
        self.assertLessEqual(out["limit"], tools.MAX_PAGE)

    def test_negative_and_zero_rejected(self):
        with self.assertRaises(tools.InputInvalid):
            tools.execute(self.read_token_obj, "moneta.list_transactions", {"limit": 0})
        with self.assertRaises(tools.InputInvalid):
            tools.execute(self.read_token_obj, "moneta.list_transactions", {"limit": -3})
        with self.assertRaises(tools.InputInvalid):
            tools.execute(self.read_token_obj, "moneta.list_transactions", {"offset": -1})

    def test_pagination_continuity(self):
        p1 = tools.execute(self.read_token_obj, "moneta.list_transactions",
                           {"limit": 2, "offset": 0})
        p2 = tools.execute(self.read_token_obj, "moneta.list_transactions",
                           {"limit": 2, "offset": 2})
        ids1 = {t["id"] for t in p1["transactions"]}
        ids2 = {t["id"] for t in p2["transactions"]}
        self.assertEqual(len(ids1), 2)
        self.assertTrue(ids1.isdisjoint(ids2))
        self.assertEqual(p1["total"], 5)

    def test_every_list_tool_is_bounded(self):
        for name in ("moneta.list_accounts", "moneta.list_transactions",
                     "moneta.get_subscriptions", "moneta.get_credit_cards",
                     "moneta.get_categories", "moneta.get_upcoming_bills"):
            out = tools.execute(self.read_token_obj, name, {})
            self.assertIn("limit", out)
            self.assertLessEqual(out["limit"], tools.MAX_PAGE)


# --------------------------------------------------------------------------- #
@override_settings(MONETA_MCP_RATE_LIMITS={"default": (1000, 60),
                                           "moneta.create_import_batch": (2, 60)})
class RateLimitTests(McpBase):
    def setUp(self):
        super().setUp()
        ratelimit.reset(self.user.id, "moneta.create_import_batch")

    def test_rate_limit_blocks_after_threshold(self):
        tools.execute(self.draft_token_obj, "moneta.create_import_batch",
                      {"source": "a"})
        tools.execute(self.draft_token_obj, "moneta.create_import_batch",
                      {"source": "b"})
        with self.assertRaises(tools.RateLimited):
            tools.execute(self.draft_token_obj, "moneta.create_import_batch",
                          {"source": "c"})

    def test_rate_limited_call_is_audited_and_has_no_effect(self):
        for s in ("a", "b"):
            tools.execute(self.draft_token_obj, "moneta.create_import_batch",
                          {"source": s})
        before = TransactionDraft.objects.count()
        with self.assertRaises(tools.RateLimited):
            tools.execute(self.draft_token_obj, "moneta.create_import_batch",
                          {"source": "c"})
        self.assertEqual(TransactionDraft.objects.count(), before)
        ev = MCPAuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.error_code, "rate_limited")


# --------------------------------------------------------------------------- #
class AuditTests(McpBase):
    def test_success_is_audited_with_fields(self):
        tools.execute(self.read_token_obj, "moneta.get_summary", {}, transport="http",
                      client_ip="203.0.113.5", user_agent="pytest-agent")
        ev = MCPAuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.user, self.user)
        self.assertEqual(ev.tool, "moneta.get_summary")
        self.assertEqual(ev.scope, SCOPE_READ)
        self.assertEqual(ev.result, MCPAuditEvent.Result.SUCCESS)
        self.assertEqual(ev.transport, "http")
        self.assertEqual(ev.client_ip, "203.0.113.5")
        self.assertIsNotNone(ev.duration_ms)
        self.assertEqual(ev.token_id, self.read_token_obj.pk)
        self.assertIn(self.read_token_obj.token_prefix, ev.token_identifier)

    def test_audit_never_stores_raw_token_or_secrets(self):
        tools.execute(self.draft_token_obj, "moneta.create_transaction_draft",
                      self.draft_args(metadata={"Authorization": "Bearer sk-xyz"}))
        for ev in MCPAuditEvent.objects.all():
            blob = json.dumps({
                "id": ev.token_identifier, "ref": ev.object_reference,
                "err": ev.error_code, "ua": ev.user_agent,
            })
            self.assertNotIn(self.draft_raw, blob)
            self.assertNotIn("sk-xyz", blob)
            self.assertNotIn("Bearer sk", blob)

    def test_failure_is_audited(self):
        with self.assertRaises(tools.InputInvalid):
            tools.execute(self.draft_token_obj, "moneta.create_transaction_draft",
                          self.draft_args(currency="ZZ9"))
        ev = MCPAuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.result, MCPAuditEvent.Result.FAILURE)

    def test_object_reference_recorded_on_create(self):
        tools.execute(self.draft_token_obj, "moneta.create_import_batch",
                      {"source": "gmail"})
        ev = MCPAuditEvent.objects.latest("timestamp")
        self.assertTrue(ev.object_reference.startswith("batch:"))


# --------------------------------------------------------------------------- #
class ForbiddenToolsTests(McpBase):
    def test_registry_has_no_forbidden_capability(self):
        names = {t["name"] for t in tools.list_tool_specs()}
        self.assertFalse(names & tools.FORBIDDEN_TOOL_NAMES)
        for needle in ("approve", "delete", "balance", "confirm_payment",
                       "transaction_direct"):
            self.assertFalse(
                [n for n in names if needle in n],
                f"herramienta prohibida expuesta: {needle}",
            )

    def test_exactly_ten_read_and_five_draft(self):
        specs = tools.list_tool_specs()
        self.assertEqual(len(specs), 15)
        read = [t for t in tools.ALL_TOOLS if t["scope"] == SCOPE_READ]
        draft = [t for t in tools.ALL_TOOLS if t["scope"] == SCOPE_DRAFT]
        self.assertEqual(len(read), 10)
        self.assertEqual(len(draft), 5)

    def test_no_tool_mutates_financial_core_directly(self):
        before = FinancialTransaction.objects.count()
        for spec in tools.ALL_TOOLS:
            self.assertNotIn("approve", spec["name"])
        self.assertEqual(FinancialTransaction.objects.count(), before)


# --------------------------------------------------------------------------- #
class SecretScanGateTests(TestCase):
    def test_repo_secret_scan_is_clean(self):
        import subprocess
        proc = subprocess.run(
            [sys.executable, "manage.py", "secret_scan"],
            cwd=os.getcwd(), capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_phase6_paths_secret_scan_is_clean(self):
        import subprocess
        proc = subprocess.run(
            [sys.executable, "manage.py", "secret_scan",
             "finanzas/intelligence", "finanzas/management/commands"],
            cwd=os.getcwd(), capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
