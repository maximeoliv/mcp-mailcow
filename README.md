# mcp-mailcow

[![PyPI](https://img.shields.io/pypi/v/mcp-mailcow)](https://pypi.org/project/mcp-mailcow/)
[![npm](https://img.shields.io/npm/v/mcp-mailcow)](https://www.npmjs.com/package/mcp-mailcow)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Model Context Protocol server for Mailcow.** Pilot your Mailcow instance
from Claude (or any MCP-compatible client): read/send mail, manage mailboxes,
aliases, domains, app passwords.

This is a **BYOK** (Bring Your Own Keys) package — install it on your own
machine, point it at **your** Mailcow, use **your** credentials.

## Features

### User mode (mailbox operations)
- Read inbox, search messages, download attachments
- Send mail, reply to messages
- Mark read/unread/flagged, move, delete

### Admin mode (server operations)
- Manage mailboxes (create / list / update / delete / quota)
- Manage aliases (create / list / delete)
- Manage domains (list / create)
- Manage app passwords (list / create / delete with protocol scoping)
- Quota reports, deliverability tests, server status

## Install

### Python (recommended)

```bash
# Zero-install with uvx (recommended)
uvx mcp-mailcow --mode user

# Or pip install
pip install mcp-mailcow
```

### Node / TypeScript

```bash
npm install -g mcp-mailcow
# or use npx
npx mcp-mailcow --mode user
```

## Configuration

### Claude Desktop / Claude Code

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mailcow-mailbox": {
      "command": "uvx",
      "args": ["mcp-mailcow", "--mode", "user"],
      "env": {
        "MAILCOW_HOST": "mail.example.com",
        "MAILCOW_MAIL_USER": "you@example.com",
        "MAILCOW_MAIL_PASS": "your-app-password"
      }
    },
    "mailcow-admin": {
      "command": "uvx",
      "args": ["mcp-mailcow", "--mode", "admin"],
      "env": {
        "MAILCOW_ADMIN_URL": "https://mail.example.com",
        "MAILCOW_ADMIN_API_KEY": "your-api-key"
      }
    }
  }
}
```

You can run **both modes** simultaneously (each gets its own server entry).

### Environment variables

#### User mode
| Variable | Required | Description |
|---|---|---|
| `MAILCOW_HOST` | yes | Mailcow hostname (e.g. `mail.example.com`) |
| `MAILCOW_MAIL_USER` | yes | Full email address (e.g. `you@example.com`) |
| `MAILCOW_MAIL_PASS` | yes | App password (recommended) or main password |
| `MAILCOW_IMAP_PORT` | no | Default `993` (IMAPS) |
| `MAILCOW_SMTP_PORT` | no | Default `587` (STARTTLS) |

#### Admin mode
| Variable | Required | Description |
|---|---|---|
| `MAILCOW_ADMIN_URL` | yes | Base URL (e.g. `https://mail.example.com`) |
| `MAILCOW_ADMIN_API_KEY` | yes | Mailcow API key (admin → Configuration → Access → API) |

#### Common
| Variable | Default | Description |
|---|---|---|
| `MCP_MAILCOW_AUDIT_LOG` | `~/.local/state/mcp-mailcow/audit.log` | Audit log path (JSONL) |
| `MCP_MAILCOW_TLS_VERIFY` | `true` | Set to `false` only for self-signed certs (not recommended) |

## Security best practices

1. **Use app passwords**, not your main mailbox password.
   In Mailcow: mailbox → app passwords → create, scope to IMAP+SMTP only.

2. **Use a Read-Only API key** for admin mode if you only need to query.
   (Set `API_KEY_READ_ONLY` instead of `API_KEY` in `mailcow.conf`.)

3. **Audit log review**: tail `~/.local/state/mcp-mailcow/audit.log` periodically.

4. **Destructive operations** (`mailbox_delete`, `alias_delete`) require an
   explicit `confirm: true` parameter. The server refuses without it.

## Development

This is a monorepo with parallel Python and TypeScript implementations.
Both share a common tool schema (`tools-schema.yaml`) as source of truth.

```
mcp-mailcow/
├── tools-schema.yaml       ← source of truth (read by both impls at build time)
├── py/                     ← Python implementation (PyPI)
├── node/                   ← TypeScript implementation (npm)
└── shared/                 ← shared mocks, integration tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and contribution guidelines.

## License

MIT — see [LICENSE](LICENSE).
