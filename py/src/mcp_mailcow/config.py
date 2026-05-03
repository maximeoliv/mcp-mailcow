"""Configuration loaded from environment variables.

Each mode has its own required variables. Missing required vars exit with a
clear error rather than failing at first tool call.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_state_dir

DEFAULT_AUDIT_LOG = Path(user_state_dir("mcp-mailcow")) / "audit.log"


@dataclass(frozen=True)
class UserConfig:
    """Config for user mode (IMAP/SMTP).

    `imap_host` and `smtp_host` default to `host` when not set explicitly.
    Override them only if your IMAP and SMTP submission run on different
    servers (rare — e.g. external SMTP relay in front of local IMAP).
    """

    host: str
    mail_user: str
    mail_pass: str
    imap_host: str = ""  # falls back to `host` in load_user_config
    smtp_host: str = ""  # falls back to `host` in load_user_config
    imap_port: int = 993
    smtp_port: int = 587
    tls_verify: bool = True
    audit_log: Path = DEFAULT_AUDIT_LOG


@dataclass(frozen=True)
class AdminConfig:
    """Config for admin mode (Mailcow REST API).

    `api_timeout` controls how long a single HTTP request can hang before
    httpx aborts. Default 60s (was 30s in v0.3 — bumped because Mailcow
    list endpoints can be slow on busy instances). Override via
    ``MCP_MAILCOW_API_TIMEOUT`` env var.
    """

    base_url: str
    api_key: str
    tls_verify: bool = True
    api_timeout: float = 60.0
    audit_log: Path = DEFAULT_AUDIT_LOG


def _require(var: str) -> str:
    val = os.environ.get(var)
    if not val:
        sys.stderr.write(f"error: required env var {var} is not set\n")
        sys.exit(2)
    return val


def _bool_env(var: str, default: bool) -> bool:
    val = os.environ.get(var)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")


def _path_env(var: str, default: Path) -> Path:
    val = os.environ.get(var)
    return Path(val).expanduser() if val else default


def load_user_config() -> UserConfig:
    host = _require("MAILCOW_HOST")
    return UserConfig(
        host=host,
        mail_user=_require("MAILCOW_MAIL_USER"),
        mail_pass=_require("MAILCOW_MAIL_PASS"),
        imap_host=os.environ.get("MAILCOW_IMAP_HOST") or host,
        smtp_host=os.environ.get("MAILCOW_SMTP_HOST") or host,
        imap_port=int(os.environ.get("MAILCOW_IMAP_PORT", "993")),
        smtp_port=int(os.environ.get("MAILCOW_SMTP_PORT", "587")),
        tls_verify=_bool_env("MCP_MAILCOW_TLS_VERIFY", True),
        audit_log=_path_env("MCP_MAILCOW_AUDIT_LOG", DEFAULT_AUDIT_LOG),
    )


def load_admin_config() -> AdminConfig:
    return AdminConfig(
        base_url=_require("MAILCOW_ADMIN_URL").rstrip("/"),
        api_key=_require("MAILCOW_ADMIN_API_KEY"),
        tls_verify=_bool_env("MCP_MAILCOW_TLS_VERIFY", True),
        api_timeout=float(os.environ.get("MCP_MAILCOW_API_TIMEOUT", "60")),
        audit_log=_path_env("MCP_MAILCOW_AUDIT_LOG", DEFAULT_AUDIT_LOG),
    )
