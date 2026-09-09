"""Run the Moneta MCP server over the stdio transport.

The bearer token is read from the environment (``MONETA_MCP_TOKEN`` by default),
never from a visible CLI argument.  A valid, enabled, non-revoked
:class:`MCPAccessToken` is required to serve tool calls.

Usage::

    MONETA_MCP_TOKEN=mmcp_xxx python manage.py moneta_mcp_stdio
"""

from __future__ import annotations

import asyncio
import os
import sys

from django.core.management.base import BaseCommand, CommandError

from finanzas.intelligence.mcp.server import build_server, resolve_env_token, set_current_token


class Command(BaseCommand):
    help = "Run the Moneta MCP server (stdio transport)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--token-env",
            default="MONETA_MCP_TOKEN",
            help="Environment variable holding the MCP bearer token.",
        )
        parser.add_argument(
            "--allow-unauthenticated",
            action="store_true",
            help="Start even without a valid token (tool calls will be denied).",
        )

    def handle(self, *args, **options):
        raw = os.environ.get(options["token_env"], "").strip()
        token = resolve_env_token(raw)
        if token is None and not options["allow_unauthenticated"]:
            raise CommandError(
                f"No hay un token MCP valido en ${options['token_env']}. "
                "Genera uno en Configuracion -> Integraciones -> Moneta MCP."
            )
        if token is not None:
            set_current_token(token)
            token.touch()
            self.stderr.write(f"moneta-mcp: autenticado como {token.user} "
                              f"(scopes={token.scope_list})")
        else:
            self.stderr.write("moneta-mcp: iniciando SIN autenticacion")

        asyncio.run(self._serve())

    async def _serve(self):
        from mcp.server.stdio import stdio_server

        server = build_server()
        init_options = server.create_initialization_options()
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, init_options)


def _main():  # pragma: no cover - convenience entrypoint
    from django.core.management import execute_from_command_line

    execute_from_command_line([sys.argv[0], "moneta_mcp_stdio", *sys.argv[1:]])
