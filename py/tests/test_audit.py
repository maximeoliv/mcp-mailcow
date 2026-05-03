"""Test the audit logger writes JSONL entries and masks secrets."""

from __future__ import annotations

import json

import pytest

from mcp_mailcow.audit import AuditLogger, _mask_secrets


def test_mask_secrets_basic():
    data = {"username": "alice", "password": "supersecret", "domain": "x.com"}
    masked = _mask_secrets(data)
    assert masked["username"] == "alice"
    assert masked["password"] == "***"
    assert masked["domain"] == "x.com"


def test_mask_secrets_nested():
    data = {
        "items": ["a"],
        "attr": {"password": "secret", "active": 1},
    }
    masked = _mask_secrets(data)
    assert masked["items"] == ["a"]
    assert masked["attr"]["password"] == "***"
    assert masked["attr"]["active"] == 1


def test_mask_empty_password_not_masked():
    """An empty password is not masked (probably means no value supplied)."""
    masked = _mask_secrets({"password": ""})
    assert masked["password"] == ""


def test_audit_writes_jsonl(tmp_path):
    log = AuditLogger(tmp_path / "audit.log")
    log.write(
        action="mailbox_create",
        params={"email": "x@y.fr", "password": "secret123"},
        result="ok",
        duration_ms=42,
    )
    content = (tmp_path / "audit.log").read_text(encoding="utf-8")
    line = json.loads(content.strip())
    assert line["action"] == "mailbox_create"
    assert line["params"]["email"] == "x@y.fr"
    assert line["params"]["password"] == "***"
    assert line["result"] == "ok"
    assert line["duration_ms"] == 42


def test_audit_trace_success(tmp_path):
    log = AuditLogger(tmp_path / "audit.log")
    with log.trace("test_action", {"foo": "bar"}):
        pass
    line = json.loads((tmp_path / "audit.log").read_text().strip())
    assert line["result"] == "ok"
    assert "duration_ms" in line


def test_audit_trace_records_error(tmp_path):
    log = AuditLogger(tmp_path / "audit.log")
    with pytest.raises(RuntimeError):
        with log.trace("failing_action", {"x": 1}):
            raise RuntimeError("boom")
    line = json.loads((tmp_path / "audit.log").read_text().strip())
    assert line["result"] == "err"
    assert "boom" in line["error"]


def test_audit_creates_parent_dir(tmp_path):
    """Logger creates the parent directory if it doesn't exist."""
    nested_path = tmp_path / "a" / "b" / "c" / "audit.log"
    log = AuditLogger(nested_path)
    log.write(action="x", params={}, result="ok", duration_ms=1)
    assert nested_path.exists()
