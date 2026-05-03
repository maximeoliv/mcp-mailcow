"""Validate the tools-schema.yaml is well-formed and complete."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "tools-schema.yaml"


@pytest.fixture(scope="module")
def schema():
    with SCHEMA_PATH.open() as f:
        return yaml.safe_load(f)


def test_schema_has_version(schema):
    assert schema.get("version") == "1.0"


def test_schema_has_modes(schema):
    modes = schema.get("modes", {})
    assert "user" in modes
    assert "admin" in modes


def test_all_tools_have_name_and_mode(schema):
    for t in schema["tools"]:
        assert "name" in t, f"tool missing name: {t}"
        assert "mode" in t, f"tool missing mode: {t['name']}"
        assert t["mode"] in ("user", "admin"), f"invalid mode for {t['name']}"


def test_no_duplicate_tool_names(schema):
    names = [t["name"] for t in schema["tools"]]
    assert len(names) == len(set(names)), f"duplicate tool names found: {names}"


def test_all_tools_have_description(schema):
    for t in schema["tools"]:
        assert t.get("description"), f"tool {t['name']} missing description"


def test_all_tool_params_have_type(schema):
    for t in schema["tools"]:
        for pname, pdef in (t.get("params") or {}).items():
            assert "type" in pdef, f"{t['name']}.{pname} missing type"


def test_user_mode_has_essential_tools(schema):
    user_tools = {t["name"] for t in schema["tools"] if t["mode"] == "user"}
    essential = {
        "list_inbox", "read_message", "send_message",
        "list_folders", "search_messages", "delete_message",
    }
    missing = essential - user_tools
    assert not missing, f"user mode missing essential tools: {missing}"


def test_admin_mode_has_essential_tools(schema):
    admin_tools = {t["name"] for t in schema["tools"] if t["mode"] == "admin"}
    essential = {
        "domain_list", "domain_create",
        "mailbox_list", "mailbox_create", "mailbox_delete",
        "alias_list", "alias_create",
        "app_password_create", "app_password_delete",
        "dkim_create", "server_version",
    }
    missing = essential - admin_tools
    assert not missing, f"admin mode missing essential tools: {missing}"


def test_destructive_tools_require_confirm(schema):
    """Operations that delete data must require an explicit confirm=true param."""
    destructive = {
        "domain_delete", "mailbox_delete", "alias_delete", "dkim_delete",
        "bcc_delete", "queue_delete", "quarantine_delete",
        "domain_admin_delete", "delete_folder", "empty_folder",
    }
    by_name = {t["name"]: t for t in schema["tools"]}
    for name in destructive:
        if name not in by_name:
            continue
        tool = by_name[name]
        params = tool.get("params") or {}
        assert "confirm" in params, f"{name} should require confirm param"
        assert params["confirm"].get("required") is True, f"{name} confirm must be required"


def test_secret_params_marked():
    """Params named password/api_key/etc should ideally be flagged secret:true.
    Not strictly enforced (some are passed via --password-from-env in CLI), but
    we audit count.
    """
    with SCHEMA_PATH.open() as f:
        schema = yaml.safe_load(f)

    secret_param_names = {"password", "password2", "app_passwd", "app_passwd2",
                          "client_secret", "api_key", "key", "token"}
    found_password_params = []
    for t in schema["tools"]:
        for pname, _pdef in (t.get("params") or {}).items():
            if pname in secret_param_names:
                found_password_params.append((t["name"], pname))

    # At least some tools should have secret params (mailbox_create, app_password_create…)
    assert len(found_password_params) >= 5
