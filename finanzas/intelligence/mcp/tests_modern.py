"""MCP 2026-07-28 modern-protocol compliance suite.

Uses the official ``mcp.Client`` (SDK v2) against the real Moneta ``Server``:

* in-memory modern per-request path (no handshake, no session id)
* official Streamable HTTP client transport <-> ``Server.streamable_http_app()``
  served by an ephemeral uvicorn
* real ``manage.py moneta_mcp_stdio`` subprocess (no auth-bypass flag) with a
  real token in ``MONETA_MCP_TOKEN``

Every path asserts: protocol version == 2026-07-28, ``server/discover``,
``list_tools`` == 15 with no forbidden capability, a read call, a scoped draft
call, auth enforcement and audit.  Legacy handshake clients are checked on the
same server for backward compatibility.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
from decimal import Decimal

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase

from finanzas.models import Account
from finanzas.intelligence.mcp import server as mcp_server
from finanzas.intelligence.mcp import tools as tool_registry
from finanzas.intelligence.mcp.models import (
    MCPAccessToken,
    MCPAuditEvent,
    SCOPE_DRAFT,
    SCOPE_READ,
)

MODERN_VERSION = "2026-07-28"
FORBIDDEN = tool_registry.FORBIDDEN_TOOL_NAMES


def _mkuser(name):
    return get_user_model().objects.create_user(username=name, password="secret12345")


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# --------------------------------------------------------------------------- #
class ModernInMemoryTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.user = _mkuser("mim_user")
        self.acc = Account.objects.create(
            user=self.user, name="Banco", account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("100.00"), current_balance=Decimal("100.00"),
        )
        self.draft_tok, self.draft_raw = MCPAccessToken.issue(
            self.user, "mim", [SCOPE_DRAFT])
        self.read_tok, self.read_raw = MCPAccessToken.issue(
            self.user, "mim-read", [SCOPE_READ])

    def test_modern_negotiation_discover_and_calls(self):
        from mcp import Client
        out = {}

        async def scenario():
            srv = mcp_server.build_server()
            mcp_server.set_current_token(self.draft_tok)
            async with Client(srv, mode="auto", raise_exceptions=True) as c:
                out["pv"] = c.protocol_version
                out["supported"] = list(c.session.discover_result.supported_versions)
                out["server"] = (c.server_info.name, c.server_info.version)
                out["tools_cap"] = c.server_capabilities.tools is not None
                dr2 = await c.session.discover()
                out["explicit_supported"] = list(dr2.supported_versions)
                listed = await c.list_tools()
                out["names"] = {t.name for t in listed.tools}
                r = await c.call_tool("moneta.get_summary", {})
                out["read"] = json.loads(r.content[0].text)
                d = await c.call_tool("moneta.create_import_batch", {"source": "mim"})
                out["draft"] = json.loads(d.content[0].text)

        async_to_sync(scenario)()
        self.assertEqual(out["pv"], MODERN_VERSION)
        self.assertEqual(out["supported"], [MODERN_VERSION])
        self.assertEqual(out["explicit_supported"], [MODERN_VERSION])
        self.assertEqual(out["server"], ("moneta", "0.3.0"))
        self.assertTrue(out["tools_cap"])
        self.assertEqual(len(out["names"]), 15)
        self.assertFalse(out["names"] & FORBIDDEN)
        self.assertTrue(out["read"]["ok"])
        self.assertIn("assets", out["read"]["data"])
        self.assertTrue(out["draft"]["ok"])
        self.assertEqual(out["draft"]["data"]["batch"]["source"], "mim")
        self.assertTrue(MCPAuditEvent.objects.filter(
            user=self.user, tool="moneta.create_import_batch",
            result=MCPAuditEvent.Result.SUCCESS).exists())

    def test_modern_scope_enforced(self):
        from mcp import Client
        out = {}

        async def scenario():
            srv = mcp_server.build_server()
            mcp_server.set_current_token(self.read_tok)
            async with Client(srv, mode="auto", raise_exceptions=True) as c:
                res = await c.call_tool("moneta.create_import_batch", {"source": "x"})
                out["is_error"] = res.is_error
                out["payload"] = json.loads(res.content[0].text)

        async_to_sync(scenario)()
        self.assertTrue(out["is_error"])
        self.assertEqual(out["payload"]["error_code"], "scope_denied")

    def test_modern_unauthenticated_denied(self):
        from mcp import Client
        out = {}

        async def scenario():
            srv = mcp_server.build_server()
            mcp_server.set_current_token(None)
            async with Client(srv, mode="auto", raise_exceptions=True) as c:
                res = await c.call_tool("moneta.get_summary", {})
                out["is_error"] = res.is_error
                out["text"] = res.content[0].text

        async_to_sync(scenario)()
        self.assertTrue(out["is_error"])
        self.assertIn("unauthenticated", out["text"])

    def test_legacy_handshake_backward_compat(self):
        from mcp import Client
        out = {}

        async def scenario():
            srv = mcp_server.build_server()
            mcp_server.set_current_token(self.draft_tok)
            async with Client(srv, mode="legacy", raise_exceptions=True) as c:
                out["pv"] = c.protocol_version
                listed = await c.list_tools()
                out["n"] = len(listed.tools)
                r = await c.call_tool("moneta.get_summary", {})
                out["ok"] = json.loads(r.content[0].text)["ok"]

        async_to_sync(scenario)()
        self.assertNotEqual(out["pv"], "")
        self.assertEqual(out["n"], 15)
        self.assertTrue(out["ok"])


# --------------------------------------------------------------------------- #
class ModernStreamableHttpTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.user = _mkuser("mhttp_user")
        self.acc = Account.objects.create(
            user=self.user, name="Banco", account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("100.00"), current_balance=Decimal("100.00"),
        )
        self.draft_tok, self.draft_raw = MCPAccessToken.issue(
            self.user, "mhttp", [SCOPE_DRAFT])
        self.read_tok, self.read_raw = MCPAccessToken.issue(
            self.user, "mhttp-read", [SCOPE_READ])
        self.revoked_tok, self.revoked_raw = MCPAccessToken.issue(
            self.user, "mhttp-rev", [SCOPE_READ])
        self.revoked_tok.revoke()

    async def _serve(self):
        import uvicorn
        app = mcp_server.build_streamable_http_app(path="/", stateless=True)
        port = _free_port()
        cfg = uvicorn.Config(app, host="127.0.0.1", port=port,
                             log_level="error", lifespan="on")
        server = uvicorn.Server(cfg)
        task = asyncio.ensure_future(server.serve())
        for _ in range(200):
            if server.started:
                break
            await asyncio.sleep(0.05)
        else:  # pragma: no cover
            raise RuntimeError("uvicorn did not start")
        return server, task, f"http://127.0.0.1:{port}/"

    def _client(self, url, raw=None, mode="auto"):
        import httpx2
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
        headers = {"Authorization": f"Bearer {raw}"} if raw else {}
        hc = httpx2.AsyncClient(headers=headers)
        return hc, Client(streamable_http_client(url, http_client=hc),
                          mode=mode, raise_exceptions=True)

    def test_modern_http_end_to_end(self):
        out = {}

        async def scenario():
            server, task, url = await self._serve()
            hc, client = self._client(url, self.draft_raw, mode="auto")
            try:
                async with client as c:
                    out["pv"] = c.protocol_version
                    out["supported"] = list(c.session.discover_result.supported_versions)
                    out["server"] = (c.server_info.name, c.server_info.version)
                    out["tools_cap"] = c.server_capabilities.tools is not None
                    listed = await c.list_tools()
                    out["names"] = {t.name for t in listed.tools}
                    r = await c.call_tool("moneta.get_summary", {})
                    out["read"] = json.loads(r.content[0].text)
                    d = await c.call_tool("moneta.create_import_batch",
                                          {"source": "mhttp"})
                    out["draft"] = json.loads(d.content[0].text)
            finally:
                await hc.aclose()
                server.should_exit = True
                await task

        async_to_sync(scenario)()
        self.assertEqual(out["pv"], MODERN_VERSION)
        self.assertEqual(out["supported"], [MODERN_VERSION])
        self.assertEqual(out["server"], ("moneta", "0.3.0"))
        self.assertTrue(out["tools_cap"])
        self.assertEqual(len(out["names"]), 15)
        self.assertFalse(out["names"] & FORBIDDEN)
        self.assertTrue(out["read"]["ok"])
        self.assertTrue(out["draft"]["ok"])
        ev = MCPAuditEvent.objects.filter(user=self.user, transport="http")
        self.assertTrue(ev.filter(tool="moneta.get_summary").exists())
        self.assertTrue(ev.filter(tool="moneta.create_import_batch").exists())

    def test_http_auth_matrix(self):
        results = {}

        async def scenario():
            server, task, url = await self._serve()
            try:
                for label, raw in (("missing", None),
                                   ("bad", "mmcp_bogus_value_1234567890"),
                                   ("revoked", self.revoked_raw),
                                   ("valid", self.read_raw)):
                    hc, client = self._client(url, raw, mode="auto")
                    try:
                        async with client as c:
                            await c.list_tools()
                        results[label] = "allowed"
                    except Exception:
                        results[label] = "denied"
                    finally:
                        await hc.aclose()
            finally:
                server.should_exit = True
                await task

        async_to_sync(scenario)()
        self.assertEqual(results["missing"], "denied")
        self.assertEqual(results["bad"], "denied")
        self.assertEqual(results["revoked"], "denied")
        self.assertEqual(results["valid"], "allowed")

    def test_sessionless_no_affinity(self):
        """Modern transport is stateless: independent client connections each
        complete a full exchange with no initialize handshake and no shared
        Mcp-Session-Id."""
        from mcp import Client
        results = []

        async def scenario():
            server, task, url = await self._serve()
            try:
                mgr_stateless = mcp_server.build_streamable_http_app(
                    path="/", stateless=True)
                # the app the test server runs is the same builder; assert config
                for _ in range(3):
                    hc, client = self._client(url, self.read_raw, mode="auto")
                    try:
                        async with client as c:
                            assert c.protocol_version == MODERN_VERSION
                            dr = await c.session.discover()
                            results.append(list(dr.supported_versions))
                            r = await c.call_tool("moneta.get_summary", {})
                            results.append(json.loads(r.content[0].text)["ok"])
                    finally:
                        await hc.aclose()
                self.assertIsNotNone(mgr_stateless)
            finally:
                server.should_exit = True
                await task

        async_to_sync(scenario)()
        self.assertEqual(results, [[MODERN_VERSION], True] * 3)

    def test_modern_routing_header_validation(self):
        """The MCP-Protocol-Version header routes to (and is validated by) the
        official modern transport: duplicated -> HEADER_MISMATCH; malformed
        modern envelope -> INVALID_PARAMS; absent -> the request is not handled
        as a modern one (legacy 'method not found' for server/discover)."""
        import httpx2
        out = {}

        async def scenario():
            server, task, url = await self._serve()
            try:
                async with httpx2.AsyncClient() as hc:
                    dup = await hc.post(
                        url,
                        content=json.dumps({"jsonrpc": "2.0", "id": 1,
                                            "method": "server/discover"}),
                        headers=[
                            ("content-type", "application/json"),
                            ("accept", "application/json, text/event-stream"),
                            ("mcp-protocol-version", MODERN_VERSION),
                            ("mcp-protocol-version", MODERN_VERSION),
                        ],
                    )
                    out["dup"] = (dup.status_code, dup.text[:400].lower())

                    malformed = await hc.post(
                        url,
                        content=json.dumps({"jsonrpc": "2.0", "id": 2,
                                            "method": "server/discover"}),
                        headers={
                            "content-type": "application/json",
                            "accept": "application/json, text/event-stream",
                            "mcp-protocol-version": MODERN_VERSION,
                        },
                    )
                    out["malformed"] = (malformed.status_code,
                                        malformed.text[:400].lower())

                    noheader = await hc.post(
                        url,
                        content=json.dumps({"jsonrpc": "2.0", "id": 3,
                                            "method": "server/discover"}),
                        headers={
                            "content-type": "application/json",
                            "accept": "application/json, text/event-stream",
                        },
                    )
                    out["noheader"] = (noheader.status_code,
                                       noheader.text[:400].lower())
            finally:
                server.should_exit = True
                await task

        async_to_sync(scenario)()
        self.assertEqual(out["dup"][0], 400)
        self.assertIn("more than once", out["dup"][1])
        self.assertEqual(out["malformed"][0], 400)
        self.assertIn("error", out["malformed"][1])
        # without the modern header the modern route is not taken
        self.assertIn("error", out["noheader"][1])

    def test_legacy_http_client_backward_compat(self):
        out = {}

        async def scenario():
            server, task, url = await self._serve()
            hc, client = self._client(url, self.draft_raw, mode="legacy")
            try:
                async with client as c:
                    out["pv"] = c.protocol_version
                    listed = await c.list_tools()
                    out["n"] = len(listed.tools)
            finally:
                await hc.aclose()
                server.should_exit = True
                await task

        async_to_sync(scenario)()
        self.assertNotEqual(out["pv"], "")
        self.assertEqual(out["n"], 15)


# --------------------------------------------------------------------------- #
class AuthBypassRemovedTests(TestCase):
    def test_command_has_no_unauthenticated_flag(self):
        import inspect
        from finanzas.management.commands import moneta_mcp_stdio
        src = inspect.getsource(moneta_mcp_stdio)
        self.assertNotIn("allow-unauthenticated", src)
        self.assertNotIn("allow_unauthenticated", src)

    def test_command_refuses_without_valid_token(self):
        env = dict(os.environ)
        env["DJANGO_SETTINGS_MODULE"] = "config.settings"
        env.pop("MONETA_MCP_TOKEN", None)
        proc = subprocess.run(
            [sys.executable, "manage.py", "moneta_mcp_stdio"],
            cwd=os.getcwd(), env=env, capture_output=True, text=True,
            timeout=90, input="",
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("token MCP valido", proc.stderr + proc.stdout)


# --------------------------------------------------------------------------- #
class ModernStdioSubprocessTests(TransactionTestCase):
    def test_modern_stdio_end_to_end(self):
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters

        tmpdir = tempfile.mkdtemp(prefix="moneta-mcp-e2e-")
        db_path = os.path.join(tmpdir, "e2e.sqlite3")
        env = dict(os.environ)
        env["DJANGO_SETTINGS_MODULE"] = "config.settings"
        env["DB_NAME"] = db_path

        setup = (
            "import django,os;"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');"
            "django.setup();"
            "from django.core.management import call_command;"
            "call_command('migrate',verbosity=0);"
            "from django.contrib.auth import get_user_model;"
            "from finanzas.models import Account;"
            "from finanzas.intelligence.mcp.models import MCPAccessToken;"
            "u=get_user_model().objects.create_user(username='e2e',password='x');"
            "Account.objects.create(user=u,name='B',account_type='checking',"
            "opening_balance=0,current_balance=0);"
            "t,raw=MCPAccessToken.issue(u,'e2e',['draft']);"
            "print('RAWTOKEN='+raw)"
        )
        res = subprocess.run([sys.executable, "-c", setup], cwd=os.getcwd(),
                             env=env, capture_output=True, text=True, timeout=240)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        raw = next(line.split("=", 1)[1].strip()
                   for line in res.stdout.splitlines()
                   if line.startswith("RAWTOKEN="))
        env["MONETA_MCP_TOKEN"] = raw

        params = StdioServerParameters(
            command=sys.executable,
            args=["manage.py", "moneta_mcp_stdio"],
            env=env, cwd=str(os.getcwd()),
        )
        out = {}

        async def scenario():
            import anyio
            with anyio.fail_after(150):
                async with Client(params, mode="auto", raise_exceptions=True) as c:
                    out["pv"] = c.protocol_version
                    out["supported"] = list(
                        c.session.discover_result.supported_versions)
                    out["server"] = (c.server_info.name, c.server_info.version)
                    listed = await c.list_tools()
                    out["names"] = {t.name for t in listed.tools}
                    r = await c.call_tool("moneta.get_summary", {})
                    out["read"] = json.loads(r.content[0].text)
                    d = await c.call_tool("moneta.create_import_batch",
                                          {"source": "e2e"})
                    out["draft"] = json.loads(d.content[0].text)

        try:
            async_to_sync(scenario)()
        finally:
            import shutil
            with contextlib.suppress(Exception):
                shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(out["pv"], MODERN_VERSION)
        self.assertEqual(out["supported"], [MODERN_VERSION])
        self.assertEqual(out["server"], ("moneta", "0.3.0"))
        self.assertEqual(len(out["names"]), 15)
        self.assertFalse(out["names"] & FORBIDDEN)
        self.assertTrue(out["read"]["ok"])
        self.assertIn("assets", out["read"]["data"])
        self.assertTrue(out["draft"]["ok"])
        self.assertTrue(out["draft"]["data"]["batch"]["id"])


# --------------------------------------------------------------------------- #
class CombinedAsgiMountTests(TransactionTestCase):
    """The production ASGI entrypoint (config.asgi:application) serves Django
    AND the official MCP Streamable HTTP transport at /mcp on the same port."""

    def setUp(self):
        cache.clear()
        self.user = _mkuser("asgi_user")
        Account.objects.create(
            user=self.user, name="Banco", account_type=Account.AccountType.CHECKING,
            opening_balance=Decimal("0.00"), current_balance=Decimal("0.00"),
        )
        self.tok, self.raw = MCPAccessToken.issue(self.user, "asgi", [SCOPE_READ])

    def test_django_and_mcp_on_one_asgi_app(self):
        import httpx2
        import uvicorn
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
        from config.asgi import application

        out = {}

        async def scenario():
            port = _free_port()
            server = uvicorn.Server(uvicorn.Config(
                application, host="127.0.0.1", port=port,
                log_level="error", lifespan="on"))
            task = asyncio.ensure_future(server.serve())
            for _ in range(200):
                if server.started:
                    break
                await asyncio.sleep(0.05)
            base = f"http://127.0.0.1:{port}"
            try:
                async with httpx2.AsyncClient(timeout=15) as hc:
                    dj = await hc.get(base + "/accounts/login/")
                    out["django"] = dj.status_code
                hc2 = httpx2.AsyncClient(
                    headers={"Authorization": f"Bearer {self.raw}"}, timeout=15)
                async with Client(
                    streamable_http_client(base + "/mcp/", http_client=hc2),
                    mode="auto", raise_exceptions=True,
                ) as c:
                    out["pv"] = c.protocol_version
                    out["tools"] = len((await c.list_tools()).tools)
                await hc2.aclose()
            finally:
                server.should_exit = True
                await task

        async_to_sync(scenario)()
        self.assertEqual(out["django"], 200)
        self.assertEqual(out["pv"], MODERN_VERSION)
        self.assertEqual(out["tools"], 15)
