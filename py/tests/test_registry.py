"""Test that the registry exposes one handler per schema tool, both modes."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mcp_mailcow.audit import AuditLogger
from mcp_mailcow.config import AdminConfig, UserConfig
from mcp_mailcow.registry import build_admin_registry, build_user_registry

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "tools-schema.yaml"


@pytest.fixture(scope="module")
def schema():
    with SCHEMA_PATH.open() as f:
        return yaml.safe_load(f)


def _user_cfg(tmp_path):
    return UserConfig(
        host="mail.example.com",
        mail_user="x@a.com",
        mail_pass="pw",
        audit_log=tmp_path / "audit.log",
    )


def _admin_cfg(tmp_path):
    return AdminConfig(
        base_url="https://mail.example.com",
        api_key="key",
        audit_log=tmp_path / "audit.log",
    )


def test_user_registry_has_all_user_tools(schema, tmp_path):
    cfg = _user_cfg(tmp_path)
    audit = AuditLogger(cfg.audit_log)
    registry = build_user_registry(cfg, audit)
    user_tools = {t["name"] for t in schema["tools"] if t["mode"] == "user"}
    missing = user_tools - set(registry.keys())
    assert not missing, f"user registry missing handlers for: {missing}"


def test_admin_registry_has_all_admin_tools(schema, tmp_path):
    cfg = _admin_cfg(tmp_path)
    audit = AuditLogger(cfg.audit_log)
    registry = build_admin_registry(cfg, audit)
    admin_tools = {t["name"] for t in schema["tools"] if t["mode"] == "admin"}
    missing = admin_tools - set(registry.keys())
    assert not missing, f"admin registry missing handlers for: {missing}"


def test_no_extra_handlers_in_user_registry(schema, tmp_path):
    """The registry shouldn't expose handlers that don't have a schema entry."""
    cfg = _user_cfg(tmp_path)
    registry = build_user_registry(cfg, AuditLogger(cfg.audit_log))
    user_tools = {t["name"] for t in schema["tools"] if t["mode"] == "user"}
    extra = set(registry.keys()) - user_tools
    assert not extra, f"user registry has extra handlers: {extra}"


def test_no_extra_handlers_in_admin_registry(schema, tmp_path):
    cfg = _admin_cfg(tmp_path)
    registry = build_admin_registry(cfg, AuditLogger(cfg.audit_log))
    admin_tools = {t["name"] for t in schema["tools"] if t["mode"] == "admin"}
    extra = set(registry.keys()) - admin_tools
    assert not extra, f"admin registry has extra handlers: {extra}"
