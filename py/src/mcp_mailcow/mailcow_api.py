"""Thin async client over the Mailcow REST API.

Designed to be used as a **persistent client at the lifetime of the MCP
server** rather than re-instantiated per call. The previous per-call pattern
(`async with ctx.client() as c`) caused TLS handshake on every request and
left the asyncio loop in a bad state after a timeout, freezing the stdio
server until the subprocess was killed (Shadow E2E cycle 1 P0).

The new pattern:
    client = MailcowClient(base_url, api_key)  # at server boot
    await client.get("/api/v1/...")            # any number of times
    await client.aclose()                      # at server shutdown

Recovery after a transient error: the client tracks the underlying
``httpx.AsyncClient`` and lazily recreates it if it has been forcibly
closed (e.g. due to a network failure that left the pool in a broken
state). Callers don't need to handle the rebuild themselves.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger("mcp_mailcow.api")


class MailcowAPIError(RuntimeError):
    """Raised when Mailcow returns an error in the response body."""

    def __init__(self, msg: str, payload: Any = None) -> None:
        super().__init__(msg)
        self.payload = payload


class MailcowClient:
    """Persistent async HTTP client for the Mailcow REST API.

    Thread-/task-safety: all access to the underlying ``httpx.AsyncClient``
    is mediated by ``self._lock``, so concurrent tool calls share the same
    client and connection pool safely.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        tls_verify: bool = True,
        timeout: float = 60.0,
    ) -> None:
        self._base_url = base_url
        self._headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }
        self._tls_verify = tls_verify
        self._timeout = timeout
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            verify=self._tls_verify,
            timeout=self._timeout,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Return the active httpx client, building it on first use or
        rebuilding it if the previous instance is closed."""
        async with self._lock:
            if self._client is None or self._client.is_closed:
                if self._client is not None:
                    logger.warning("rebuilding httpx client (previous was closed)")
                self._client = self._build_client()
            return self._client

    async def aclose(self) -> None:
        """Close the underlying client. Idempotent."""
        async with self._lock:
            if self._client is not None and not self._client.is_closed:
                try:
                    await self._client.aclose()
                except Exception:  # never raise from cleanup
                    logger.exception("error closing httpx client")
            self._client = None

    async def _request(self, method: str, path: str, *, json: Any = None) -> Any:
        client = await self._get_client()
        try:
            r = await client.request(method, path, json=json)
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            # On transient network/timeout errors, force the client to be
            # rebuilt on the next call. This avoids a broken pool from
            # hanging subsequent requests.
            logger.warning("transient httpx error on %s %s: %s — will rebuild client", method, path, e)
            await self.aclose()
            raise MailcowAPIError(f"{method} {path}: {type(e).__name__}: {e}") from e

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

    # Async-context-manager support is kept for ad-hoc scripts/tests.
    # The MCP server itself uses the explicit aclose() at shutdown.
    async def __aenter__(self) -> "MailcowClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()
