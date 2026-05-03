"""Test selected admin tools against mocked Mailcow responses."""

from __future__ import annotations

from pathlib import Path

import pytest
import respx
from httpx import Response

from mcp_mailcow import admin_tools as at
from mcp_mailcow.audit import AuditLogger
from mcp_mailcow.config import AdminConfig


@pytest.fixture
def admin_ctx(tmp_path):
    config = AdminConfig(
        base_url="https://mail.example.com",
        api_key="test-key",
        tls_verify=True,
        audit_log=tmp_path / "audit.log",
    )
    return at.AdminContext(config=config, audit=AuditLogger(config.audit_log))


@pytest.mark.asyncio
@respx.mock
async def test_domain_list(admin_ctx):
    respx.get("https://mail.example.com/api/v1/get/domain/all").mock(
        return_value=Response(200, json=[{"domain_name": "a.com"}, {"domain_name": "b.com"}])
    )
    handler = at.domain_list(admin_ctx)
    result = await handler({})
    assert len(result) == 2


@pytest.mark.asyncio
@respx.mock
async def test_mailbox_create_payload(admin_ctx):
    import json
    route = respx.post("https://mail.example.com/api/v1/add/mailbox").mock(
        return_value=Response(200, json=[{"type": "success", "msg": "mailbox_added"}])
    )
    handler = at.mailbox_create(admin_ctx)
    await handler({
        "email": "test@a.com",
        "name": "Test",
        "quota_mb": 500,
        "password": "Secret123",
    })
    payload = json.loads(route.calls.last.request.content.decode())
    assert payload["local_part"] == "test"
    assert payload["domain"] == "a.com"
    assert payload["quota"] == 500
    assert payload["password"] == "Secret123"


@pytest.mark.asyncio
@respx.mock
async def test_mailbox_delete_requires_confirm(admin_ctx):
    handler = at.mailbox_delete(admin_ctx)
    with pytest.raises(ValueError, match="confirm"):
        await handler({"email": "x@a.com"})


@pytest.mark.asyncio
@respx.mock
async def test_mailbox_delete_with_confirm(admin_ctx):
    respx.post("https://mail.example.com/api/v1/delete/mailbox").mock(
        return_value=Response(200, json=[{"type": "success"}])
    )
    handler = at.mailbox_delete(admin_ctx)
    result = await handler({"email": "x@a.com", "confirm": True})
    assert result[0]["type"] == "success"


@pytest.mark.asyncio
@respx.mock
async def test_app_password_list_masks_hash(admin_ctx):
    respx.get("https://mail.example.com/api/v1/get/app-passwd/all/x@a.com").mock(
        return_value=Response(200, json=[
            {"id": 1, "name": "n8n", "password": "{BLF-CRYPT}$2y$10$abc..."},
        ])
    )
    handler = at.app_password_list(admin_ctx)
    result = await handler({"email": "x@a.com"})
    assert result[0]["password"] == "***"


@pytest.mark.asyncio
@respx.mock
async def test_quota_report_filters_by_threshold(admin_ctx):
    respx.get("https://mail.example.com/api/v1/get/mailbox/all").mock(
        return_value=Response(200, json=[
            {"username": "low@a.com", "quota": 1024 * 1024 * 1024, "quota_used": 100},
            {"username": "high@a.com", "quota": 1024 * 1024 * 1024, "quota_used": 1024 * 1024 * 1024 * 0.95},
        ])
    )
    handler = at.mailbox_quota_report(admin_ctx)
    result = await handler({"threshold_pct": 50})
    assert len(result) == 1
    assert result[0]["mailbox"] == "high@a.com"


@pytest.mark.asyncio
@respx.mock
async def test_dkim_create_payload(admin_ctx):
    import json
    route = respx.post("https://mail.example.com/api/v1/add/dkim").mock(
        return_value=Response(200, json=[{"type": "success"}])
    )
    handler = at.dkim_create(admin_ctx)
    await handler({"domain": "a.com", "selector": "mail", "key_size_bits": 2048})
    payload = json.loads(route.calls.last.request.content.decode())
    assert payload["dkim_selector"] == "mail"
    assert payload["key_size"] == 2048
    assert payload["domains"] == "a.com"
