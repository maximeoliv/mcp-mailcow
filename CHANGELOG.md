# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0-alpha] - 2026-05-03

Iteration based on Shadow PC end-to-end test report (`rapport-test-mcp-mailcow.md`).
P0/P1 fixes from real-world usage; the architecture itself is unchanged.

### Fixed
- **`pip install -e .`** : `tools-schema.yaml` was packaged via hatchling
  `shared-data` which only fires on wheel builds, so editable installs
  crashed at first call with `FileNotFoundError`. The schema now lives
  inside the package (`py/src/mcp_mailcow/tools-schema.yaml`) with a
  fallback to the repo-root copy for unconventional dev setups. Both
  wheel and editable installs now work.
- **Missing `_require_confirm`** on 11 destructive admin tools that the
  v0.1.0/v0.2.0 SECURITY.md promised but didn't deliver:
  `mailbox_set_password`, `app_password_delete`, `recipient_map_delete`,
  `transport_delete`, `relayhost_delete`, `tls_policy_delete`,
  `forward_host_delete`, `sync_job_delete`, `resource_delete`,
  `oauth2_client_delete`, `domain_policy_delete`. Both Python and
  TypeScript impls are now consistent with the documented promise.
  `transport_delete`/`relayhost_delete` (mail routing) and
  `oauth2_client_delete` (integrations) had the highest blast radius.
- **`server_status_summary`** now returns the full set of fields its
  description advertises: `containers_healthy`, `containers_down`,
  `vmail_disk_pct`, `queue_length`, `fail2ban_bans` (in addition to the
  existing `version`, `containers_total`, `containers_running`, `vmail`).
  Best-effort fetch on optional endpoints (returns `null` if a probe
  hiccups) so the summary never fails the whole call.
- **`send_message`** now sets `Date` and `Message-ID` headers explicitly
  (Python `email.utils.formatdate()` and `make_msgid()`). Previously
  `EmailMessage` left them blank and the response payload had an empty
  `message_id` field. Bonus side effect: improves mail-tester score
  (avoids `MISSING_DATE -1.396` and `MISSING_MID -0.14`).

### Changed
- `pyproject.toml` version bumped to `0.3.0a0` (was incorrectly `1.0.0`
  in v0.1.0/v0.2.0). `node/package.json` similarly bumped to
  `0.3.0-alpha.0`.
- Python classifiers: added `Python :: 3.14` (works in practice on
  Shadow's setup, was missing from the metadata).
- pyproject `shared-data` directive removed (no longer needed since the
  schema YAML lives inside the package).

### Known issues / next iteration
- **`alias_delete` 30s timeout + MCP freeze** under load (P0 from Shadow
  report) — root cause involves the resolve-by-address GET before
  delete + per-call httpx client lifecycle. Refactor to a persistent
  `MailcowClient` is a deeper change planned for v0.4.0-alpha. As a
  workaround, restart Claude Desktop if the admin MCP becomes
  unresponsive after a destructive op.
- **CI Python tests** : the GitHub Actions workflow needs `pip install -e
  .[dev]` to pick up the schema correctly, fixed by P0 #2 above.

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
