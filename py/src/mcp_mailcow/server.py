"""MCP server entry point.

Wires up the tool registry (user or admin mode), the audit logger, and the
MCP stdio transport from the official `mcp` SDK.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .audit import AuditLogger
from .config import load_admin_config, load_user_config
from .exceptions import ConfirmationRequired
from .schema import load_schema, to_mcp_tool, tools_for_mode

logger = logging.getLogger("mcp_mailcow")


async def run_server(mode: str) -> None:
    schema = load_schema()
    tool_defs = tools_for_mode(schema, mode)  # type: ignore[arg-type]

    # Lazy-import the right registry depending on mode (avoids loading IMAP libs
    # in admin mode and vice versa).
    if mode == "user":
        from .registry import build_user_registry

        config = load_user_config()
        audit = AuditLogger(config.audit_log)
        registry, ctx = build_user_registry(config, audit)
    else:
        from .registry import build_admin_registry

        config = load_admin_config()
        audit = AuditLogger(config.audit_log)
        registry, ctx = build_admin_registry(config, audit)

    server = Server("mcp-mailcow")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [Tool(**to_mcp_tool(t)) for t in tool_defs]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name not in registry:
            return [TextContent(type="text", text=f"error: unknown tool '{name}'")]
        handler = registry[name]
        try:
            result = await handler(arguments)
        except ConfirmationRequired as e:
            return [
                TextContent(
                    type="text",
                    text=f"⚠ {e}\nAdd `confirm: true` to the arguments and retry.",
                )
            ]
        except Exception as e:  # surface as text error, don't crash the server
            logger.exception("tool %s failed", name)
            return [TextContent(type="text", text=f"error: {e}")]
        text = (
            result
            if isinstance(result, str)
            else json.dumps(result, ensure_ascii=False, indent=2)
        )
        return [TextContent(type="text", text=text)]

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        # Close persistent resources owned by the context (e.g. the
        # MailcowClient httpx pool in admin mode). Best-effort.
        aclose = getattr(ctx, "aclose", None)
        if callable(aclose):
            try:
                await aclose()
            except Exception:
                logger.exception("error during context cleanup")
