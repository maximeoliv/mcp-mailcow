"""Load and validate the tool schema YAML."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any, Literal

import yaml

Mode = Literal["user", "admin"]


def load_schema() -> dict[str, Any]:
    """Load tools-schema.yaml shipped with the package."""
    schema_path = files("mcp_mailcow").joinpath("tools-schema.yaml")
    with schema_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def tools_for_mode(schema: dict[str, Any], mode: Mode) -> list[dict[str, Any]]:
    """Return the list of tool definitions for the given mode."""
    return [t for t in schema.get("tools", []) if t.get("mode") == mode]


def to_mcp_tool(tool_def: dict[str, Any]) -> dict[str, Any]:
    """Convert our YAML tool def into the MCP Tool schema format.

    MCP expects:
        {"name": str, "description": str, "inputSchema": {JSON Schema}}
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param_def in (tool_def.get("params") or {}).items():
        # Defensive: params may be empty dict {} for no-arg tools
        prop: dict[str, Any] = {"type": param_def.get("type", "string")}
        if "description" in param_def:
            prop["description"] = param_def["description"]
        if "default" in param_def:
            prop["default"] = param_def["default"]
        if "enum" in param_def:
            prop["enum"] = param_def["enum"]
        if "items" in param_def:
            prop["items"] = param_def["items"]
        if "format" in param_def:
            prop["format"] = param_def["format"]
        properties[param_name] = prop
        if param_def.get("required"):
            required.append(param_name)

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        input_schema["required"] = required

    return {
        "name": tool_def["name"],
        "description": tool_def.get("description", "").strip(),
        "inputSchema": input_schema,
    }
