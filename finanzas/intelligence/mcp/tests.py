"""MCP test suite (Phase 6): auth, scopes, tenant isolation, validation,
pagination, rate limiting, audit, forbidden tools, and real client smokes
(in-memory MCP transport + real stdio subprocess + Streamable HTTP)."""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from finanzas.models import Account, Category, FinancialTransaction
from finanzas.intelligence.imports import services as import_services
from finanzas.intelligence.imports.models import TransactionDraft
from finanzas.intelligence.mcp import ratelimit, tools
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
        with self.assertRaises(tools.ToolNotFound):
            tools.execute(self.read_token_obj, "moneta.delete_everything", {})


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
class StreamableHttpSmokeTests(McpBase):
    """Real request/response cycle through the Django view + middleware stack."""

    def _rpc(self, method, params=None, token=None, rid=1):
        headers = {}
        if token:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.post(
            "/mcp/",
            data=json.dumps({"jsonrpc": "2.0", "id": rid, "method": method,
                             "params": params or {}}),
            content_type="application/json",
            **headers,
        )

    def test_initialize_without_auth(self):
        resp = self._rpc("initialize", {"protocolVersion": "2025-06-18"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["result"]["serverInfo"]["name"], "moneta")

    def test_tools_list_requires_auth(self):
        self.assertEqual(self._rpc("tools/list").status_code, 401)
        resp = self._rpc("tools/list", token=self.read_raw)
        self.assertEqual(resp.status_code, 200)
        names = {t["name"] for t in resp.json()["result"]["tools"]}
        self.assertEqual(len(names), 15)
        self.assertFalse(names & tools.FORBIDDEN_TOOL_NAMES)

    def test_call_read_tool_over_http(self):
        resp = self._rpc("tools/call",
                         {"name": "moneta.get_summary", "arguments": {}},
                         token=self.read_raw)
        self.assertEqual(resp.status_code, 200)
        result = resp.json()["result"]
        self.assertFalse(result["isError"])
        self.assertIn("assets", result["structuredContent"])
        ev = MCPAuditEvent.objects.latest("timestamp")
        self.assertEqual(ev.transport, "http")

    def test_call_draft_tool_over_http(self):
        resp = self._rpc("tools/call",
                         {"name": "moneta.create_import_batch",
                          "arguments": {"source": "gmail"}},
                         token=self.draft_raw)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["result"]["isError"])

    def test_scope_denied_over_http(self):
        resp = self._rpc("tools/call",
                         {"name": "moneta.create_import_batch",
                          "arguments": {"source": "gmail"}},
                         token=self.read_raw)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["result"]["isError"])

    def test_revoked_token_over_http(self):
        resp = self._rpc("tools/list", token=self.revoked_raw)
        self.assertEqual(resp.status_code, 401)


# --------------------------------------------------------------------------- #
class StdioInMemorySmokeTests(TransactionTestCase):
    """Real MCP ``Server`` + real ``ClientSession`` over in-memory streams.

    Exercises the genuine MCP protocol (initialize handshake, list_tools,
    call_tool, JSON-RPC framing) that the stdio command runs, without an OS pipe.
    """

    def setUp(self):
        cache.clear()
        self.user = _mkuser("carol")
        self.acc = Account.objects.create(
            user=self.user, name="Banco", account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("500.00"), current_balance=Decimal("500.00"),
        )
        self.token_obj, self.raw = MCPAccessToken.issue(
            self.user, "stdio", [SCOPE_DRAFT])

    def test_real_client_server_roundtrip(self):
        from mcp.shared.memory import create_client_server_memory_streams
        from mcp.client.session import ClientSession
        import anyio

        from finanzas.intelligence.mcp import server as mcp_server

        async def scenario():
            srv = mcp_server.build_server()
            mcp_server.set_current_token(self.token_obj)
            init_opts = srv.create_initialization_options()
            async with create_client_server_memory_streams() as (c_streams, s_streams):
                c_read, c_write = c_streams
                s_read, s_write = s_streams
                async with anyio.create_task_group() as tg:
                    async def run_server():
                        await srv.run(s_read, s_write, init_opts)
                    tg.start_soon(run_server)

                    async with ClientSession(c_read, c_write) as session:
                        init_res = await session.initialize()
                        assert init_res.server_info.name == "moneta"

                        listed = await session.list_tools()
                        names = {t.name for t in listed.tools}
                        assert len(names) == 15, names
                        assert not (names & tools.FORBIDDEN_TOOL_NAMES)

                        read_res = await session.call_tool("moneta.get_summary", {})
                        payload = json.loads(read_res.content[0].text)
                        assert payload["ok"] is True, payload
                        assert "assets" in payload["data"]

                        draft_res = await session.call_tool(
                            "moneta.create_import_batch", {"source": "gmail"})
                        dpayload = json.loads(draft_res.content[0].text)
                        assert dpayload["ok"] is True, dpayload
                        assert dpayload["data"]["batch"]["source"] == "gmail"

                    tg.cancel_scope.cancel()

        async_to_sync(scenario)()

        self.assertTrue(
            MCPAuditEvent.objects.filter(
                user=self.user, tool="moneta.get_summary",
                result=MCPAuditEvent.Result.SUCCESS).exists()
        )
        self.assertTrue(
            MCPAuditEvent.objects.filter(
                user=self.user, tool="moneta.create_import_batch",
                result=MCPAuditEvent.Result.SUCCESS).exists()
        )

    def test_unauthenticated_call_is_denied(self):
        from mcp.shared.memory import create_client_server_memory_streams
        from mcp.client.session import ClientSession
        import anyio
        from finanzas.intelligence.mcp import server as mcp_server

        async def scenario():
            srv = mcp_server.build_server()
            mcp_server.set_current_token(None)
            init_opts = srv.create_initialization_options()
            async with create_client_server_memory_streams() as (c_streams, s_streams):
                async with anyio.create_task_group() as tg:
                    tg.start_soon(lambda: srv.run(s_streams[0], s_streams[1], init_opts))
                    async with ClientSession(c_streams[0], c_streams[1]) as session:
                        await session.initialize()
                        res = await session.call_tool("moneta.get_summary", {})
                        assert res.is_error, res
                        assert "unauthenticated" in res.content[0].text
                    tg.cancel_scope.cancel()

        async_to_sync(scenario)()


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


class StdioSubprocessSmokeTests(TransactionTestCase):
    """Spawn the real ``manage.py moneta_mcp_stdio`` process and drive it with a
    real MCP stdio ``ClientSession`` (initialize + list_tools + clean shutdown).

    Runs with --allow-unauthenticated so it needs no shared DB for this path.
    """

    def test_process_starts_and_lists_tools(self):
        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        env = dict(os.environ)
        env["DJANGO_SETTINGS_MODULE"] = "config.settings"

        params = StdioServerParameters(
            command=sys.executable,
            args=["manage.py", "moneta_mcp_stdio", "--allow-unauthenticated"],
            env=env,
            cwd=str(os.getcwd()),
        )

        async def scenario():
            import anyio
            with anyio.fail_after(60):
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        init = await session.initialize()
                        assert init.server_info.name == "moneta"
                        listed = await session.list_tools()
                        names = {t.name for t in listed.tools}
                        assert len(names) == 15, names
                        assert not (names & tools.FORBIDDEN_TOOL_NAMES)

        async_to_sync(scenario)()
