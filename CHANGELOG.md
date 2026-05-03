# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
