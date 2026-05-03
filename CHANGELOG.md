# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0-alpha] - 2026-05-03

Iteration on v0.1.0-alpha based on review feedback (byh-dell1) and real-world
testing on Shadow PC. No tool changes — patches and DX improvements only.

### Added
- `ConfirmationRequired` exception (Python) + `ConfirmationRequired` class
  (TypeScript) for destructive ops without `confirm: true`. The MCP server
  catches them separately and surfaces an actionable message to the agent
  ("Add `confirm: true` to retry") instead of a generic error.
- `MAILCOW_IMAP_HOST` / `MAILCOW_SMTP_HOST` optional env vars to override
  the host individually for IMAP and SMTP submission. Defaults to
  `MAILCOW_HOST` for backwards compatibility.
- `examples/tailscale-serve-setup.md` documenting the pattern to expose the
  Mailcow API to the tailnet via Tailscale Serve, including the
  `X-Forwarded-For` gotcha (Mailcow nginx sees the peer's tailnet IP, so the
  whitelist entry must be the tailnet IP — not `127.0.0.1`).

### Changed
- Audit log timestamp now uses `datetime.now(timezone.utc).isoformat()` /
  `new Date().toISOString()` for explicit UTC + microsecond precision (was
  local time without microseconds).
- `import json` moved from inside `call_tool` to module-level in `server.py`.

### Documentation
- `SECURITY.md`: added "Concurrent audit log writes" to known limitations
  with explanation of the 4 KB PIPE_BUF guarantee and `flock()` workaround
  for stricter use cases.

## [0.1.0-alpha] - 2026-05-03

Initial public draft. Both Python and TypeScript implementations expose the
full Mailcow REST API (104 admin tools) plus IMAP/SMTP user-mode operations
(21 tools) — 125 tools total covering 100% of the official Mailcow OpenAPI
specification.

### Added
- `tools-schema.yaml` — single source of truth for tool definitions, both
  implementations read it at runtime.
- Python implementation (`py/`) — full coverage, 37 unit tests + E2E smoke
  test validated against a real Mailcow instance.
- TypeScript implementation (`node/`) — full coverage, basic unit tests.
- Audit log (JSONL, XDG state dir) with automatic secret masking.
- Confirmation requirement (`confirm: true`) on all destructive operations.
- CI workflows: pytest matrix on Python 3.10/11/12, release-py and
  release-node on tag push.
- Documentation: README, CONTRIBUTING, LICENSE (MIT).

### Notes
- Alpha status: API surface may shift before v1.0 based on real-world usage.
- The `send_test_mail` admin tool requires Docker access on the Mailcow host;
  it's a Python-only feature (TypeScript impl raises a clear error).
