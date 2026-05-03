"""Audit log for MCP tool invocations.

Writes JSONL entries to ~/.local/state/mcp-mailcow/audit.log (XDG-compliant)
with one line per tool call. Secrets are masked automatically.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

# Param names whose values are masked in the audit log.
SECRET_PARAM_NAMES = frozenset({
    "password",
    "password2",
    "app_passwd",
    "app_passwd2",
    "client_secret",
    "api_key",
    "key",
    "token",
})


def _mask_secrets(params: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for k, v in params.items():
        if k in SECRET_PARAM_NAMES and v:
            masked[k] = "***"
        elif isinstance(v, dict):
            masked[k] = _mask_secrets(v)
        else:
            masked[k] = v
    return masked


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        action: str,
        params: dict[str, Any],
        result: str,
        duration_ms: int,
        error: str | None = None,
    ) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "params": _mask_secrets(params),
            "result": result,
            "duration_ms": duration_ms,
        }
        if error:
            entry["error"] = error
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @contextmanager
    def trace(self, action: str, params: dict[str, Any]) -> Iterator[None]:
        """Context manager that auto-logs success or error with duration."""
        start = time.perf_counter()
        try:
            yield
            self.write(
                action=action,
                params=params,
                result="ok",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
        except Exception as e:
            self.write(
                action=action,
                params=params,
                result="err",
                duration_ms=int((time.perf_counter() - start) * 1000),
                error=str(e),
            )
            raise
