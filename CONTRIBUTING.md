# Contributing to mcp-mailcow

Thanks for your interest! This is a small open-source MCP server for Mailcow,
maintained primarily for personal use but designed as a generic tool.

## Project structure

```
mcp-mailcow/
├── tools-schema.yaml      ← source of truth for all tool definitions
├── py/                    ← Python implementation (PyPI)
├── node/                  ← TypeScript implementation (npm) — WIP
├── shared/                ← shared mocks & integration tests
└── .github/workflows/     ← CI/CD
```

The `tools-schema.yaml` is the **source of truth**. Both Python and TypeScript
implementations read it and expose the same set of tools.

## How the project handles the dual implementation

- **Adding a tool**: edit `tools-schema.yaml`, then implement the handler in
  both `py/src/mcp_mailcow/admin_tools.py` (or `user_tools.py`) and
  `node/src/admin/...`. Don't add a tool in only one — the other implementation
  will be missing it and the schema-vs-registry tests will fail.
- **Bug fixes**: cherry-pick to both impls if the bug exists in both. Some bugs
  are language-specific (e.g. IMAP library quirks); document the divergence in
  the PR.
- **Releases**: bump version in `py/pyproject.toml` AND `node/package.json` to
  the same number. Tag `vX.Y.Z`. CI publishes both packages.

## Development setup

### Python

```bash
cd py
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest -v
ruff check src
mypy src/mcp_mailcow
```

Run the server locally for manual testing:

```bash
export MAILCOW_HOST=mail.example.com
export MAILCOW_MAIL_USER=test@example.com
export MAILCOW_MAIL_PASS=...
mcp-mailcow --mode user
```

### TypeScript

```bash
cd node
npm install
npm run build
npm test
```

## Testing

### Unit tests (no real Mailcow needed)

- **Python**: `pytest -v` in `py/`. Mocks the API with `respx`.
- **TypeScript**: `npm test` in `node/`. Mocks with `nock` or similar.

### E2E smoke test (against a real Mailcow instance)

The repo includes a smoke test script that runs read-only API calls + a
single create/delete cycle against a real Mailcow instance. To run:

```bash
export MAILCOW_ADMIN_URL=https://your-mailcow.example.com
export MAILCOW_ADMIN_API_KEY=...
python shared/integration-tests/smoke.py
```

This is **destructive but minimal** (creates `mcp-smoketest@<your-domain>` and
deletes it). Don't run on production without reading the script first.

## Code style

- **Python**: ruff lint + mypy strict. PEP 8, line length 100.
- **TypeScript**: Biome or ESLint + Prettier (TBD). 100 columns.
- **Audit log**: every tool invocation must go through the `AuditLogger`
  context manager. This ensures consistent JSONL output and secret masking.
- **Secret handling**:
  - Never log a password, API key, or token in plain text.
  - Use the `secret: true` flag in `tools-schema.yaml` to mark sensitive params.
  - In CLI helpers, prefer `--password-from-env VAR_NAME` over passing secrets
    on argv (which leaks via shell history).

## Adding a new Mailcow operation

If Mailcow adds an endpoint and you want to wrap it:

1. Add the tool to `tools-schema.yaml` (name, mode, description, params).
2. Add the handler factory in `py/src/mcp_mailcow/admin_tools.py` or
   `user_tools.py`.
3. Wire it up in `py/src/mcp_mailcow/registry.py`.
4. Add a test in `py/tests/test_admin_tools.py` (mock the API call).
5. Mirror in `node/src/...` and `node/tests/...`.
6. Bump version, tag, ship.

## License

MIT. By contributing you agree your contribution is licensed under the same.

## Questions?

Open an issue on GitHub. Most likely the maintainer will respond within a
few days.
