"""Thin async client over the Mailcow REST API.

Used by admin_tools.py. All methods raise MailcowAPIError on Mailcow error
responses (Mailcow returns HTTP 200 with `{"type": "danger"|"error"}` payloads).
"""

from __future__ import annotations

from typing import Any

import httpx


class MailcowAPIError(RuntimeError):
    """Raised when Mailcow returns an error in the response body."""

    def __init__(self, msg: str, payload: Any = None) -> None:
        super().__init__(msg)
        self.payload = payload


class MailcowClient:
    def __init__(self, base_url: str, api_key: str, tls_verify: bool = True) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            verify=tls_verify,
            timeout=30.0,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "MailcowClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    async def _request(
        self, method: str, path: str, *, json: Any = None
    ) -> Any:
        r = await self._client.request(method, path, json=json)
        r.raise_for_status()
        try:
            data = r.json()
        except ValueError as e:
            raise MailcowAPIError(f"non-JSON response from {path}", r.text) from e

        # Mailcow error format: list of {"type": "danger", "msg": "..."} or
        # single object with "type": "error".
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and entry.get("type") in ("danger", "error"):
                    msg = entry.get("msg") or "unknown error"
                    raise MailcowAPIError(f"{path}: {msg}", data)
        elif isinstance(data, dict) and data.get("type") in ("danger", "error"):
            msg = data.get("msg") or "unknown error"
            raise MailcowAPIError(f"{path}: {msg}", data)

        return data

    async def get(self, path: str) -> Any:
        return await self._request("GET", path)

    async def post(self, path: str, payload: Any) -> Any:
        return await self._request("POST", path, json=payload)
