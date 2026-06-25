"""Sanitize text that may flow back to the LLM context.

The MCP server returns text content to the calling agent. Anything that
might contain a secret value (password, API key, token, app password) must
be redacted before it leaves the process boundary.

This module is intentionally aggressive: it masks every occurrence of a
known secret-bearing key=value pattern, regardless of context. False
positives (legitimate values that look like passwords) are acceptable;
false negatives (a secret that slips through) are not.

The rule "no secret in LLM context" is non-negotiable — both as a tool
call argument and as a tool response value.
"""

from __future__ import annotations

import re
from typing import Iterable

# Keys whose value must be masked. Match is case-insensitive on the key.
# Includes both bare names (password) and the env var conventions we use
# (MAILCOW_MAIL_PASS, MAILCOW_ADMIN_API_KEY, etc.).
_SECRET_KEYS: tuple[str, ...] = (
    # Bare names
    "password",
    "passwd",
    "password2",
    "passwd2",
    "app_passwd",
    "app_passwd2",
    "app_password",
    "client_secret",
    "api_key",
    "apikey",
    "api-key",
    "x-api-key",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    # Internal field names (config dataclasses, etc.)
    "mail_pass",
    "mailpass",
    # Env var conventions (uppercase variants)
    "mailcow_mail_pass",
    "mailcow_admin_api_key",
    "mailcow_api_key",
    "mailcow_password",
    "npm_token",
    "pypi_api_token",
    "github_token",
)

_KEY_ALT = "|".join(re.escape(k) for k in _SECRET_KEYS)

# key=value or key: value or key is value, with optional quoting on value.
_KV_PATTERN = re.compile(
    r"(?i)"  # case-insensitive
    rf"(?P<key>\b(?:{_KEY_ALT})\b)"
    r"(?P<sep>\s*[:=]\s*|\s+is\s+)"
    r"(?P<quote>['\"]?)"
    r"(?P<value>[^'\"\s,;}\]]+)"
    r"(?P=quote)"
)

# HTTP Authorization-style: "Bearer <token>" or "Basic <b64>".
_AUTH_PATTERN = re.compile(
    r"(?i)\b(?P<scheme>Bearer|Basic|Token)\s+(?P<value>[A-Za-z0-9\-._~+/=]{6,})"
)


def sanitize_text(text: str) -> str:
    """Replace secret-bearing values with `***` inside arbitrary text.

    Designed to wrap untrusted strings (exception messages, error replies
    from a backend, log lines) before they are returned to the LLM.

    Example:
        >>> sanitize_text("Auth failed with password='abc123' and token: xyz")
        "Auth failed with password='***' and token: ***"
    """
    if not text:
        return text
    text = _KV_PATTERN.sub(_redact_kv_match, text)
    text = _AUTH_PATTERN.sub(_redact_auth_match, text)
    return text


def _redact_kv_match(m: "re.Match[str]") -> str:
    return f"{m.group('key')}{m.group('sep')}{m.group('quote')}***{m.group('quote')}"


def _redact_auth_match(m: "re.Match[str]") -> str:
    return f"{m.group('scheme')} ***"


def sanitize_exception(e: BaseException) -> str:
    """Convert an exception to a safe display string.

    Combines the type name (always safe — it's a class name) with the
    sanitized message (potentially user-controlled or backend-controlled
    text).
    """
    type_name = type(e).__name__
    msg = sanitize_text(str(e))
    return f"{type_name}: {msg}" if msg else type_name


__all__: Iterable[str] = ("sanitize_text", "sanitize_exception")
