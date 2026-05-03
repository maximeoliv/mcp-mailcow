"""Test the MailcowClient against mocked HTTP responses."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from mcp_mailcow.mailcow_api import MailcowAPIError, MailcowClient


@pytest.mark.asyncio
@respx.mock
async def test_get_returns_json():
    respx.get("https://mail.example.com/api/v1/get/domain/all").mock(
        return_value=Response(200, json=[{"domain_name": "example.com"}])
    )
    async with MailcowClient("https://mail.example.com", "test-key") as c:
        data = await c.get("/api/v1/get/domain/all")
    assert data == [{"domain_name": "example.com"}]


@pytest.mark.asyncio
@respx.mock
async def test_post_returns_success():
    respx.post("https://mail.example.com/api/v1/add/mailbox").mock(
        return_value=Response(200, json=[{"type": "success", "msg": "mailbox_added"}])
    )
    async with MailcowClient("https://mail.example.com", "test-key") as c:
        data = await c.post("/api/v1/add/mailbox", {"local_part": "x"})
    assert data[0]["type"] == "success"


@pytest.mark.asyncio
@respx.mock
async def test_error_response_raises():
    """Mailcow returns HTTP 200 with `{"type": "danger"}` on errors. We must raise."""
    respx.post("https://mail.example.com/api/v1/add/mailbox").mock(
        return_value=Response(200, json=[{"type": "danger", "msg": "password_complexity"}])
    )
    async with MailcowClient("https://mail.example.com", "test-key") as c:
        with pytest.raises(MailcowAPIError) as exc:
            await c.post("/api/v1/add/mailbox", {})
        assert "password_complexity" in str(exc.value)


@pytest.mark.asyncio
@respx.mock
async def test_api_key_header_sent():
    route = respx.get("https://mail.example.com/api/v1/get/domain/all").mock(
        return_value=Response(200, json=[])
    )
    async with MailcowClient("https://mail.example.com", "secret-key") as c:
        await c.get("/api/v1/get/domain/all")
    request = route.calls.last.request
    assert request.headers.get("X-API-Key") == "secret-key"
