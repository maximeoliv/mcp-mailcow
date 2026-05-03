"""Custom exceptions raised by MCP tools."""

from __future__ import annotations


class ConfirmationRequired(Exception):
    """Raised when a destructive operation lacks the explicit `confirm: true`.

    The MCP server catches this separately and surfaces a clear, actionable
    message to the calling agent (rather than treating it as a generic error).
    """
