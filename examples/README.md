# Examples

Sample configurations for using `mcp-mailcow` with various MCP clients.

## Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
or `%APPDATA%\Claude\claude_desktop_config.json` (Windows) and add the
`mcpServers` block from [`claude_desktop_config.json`](./claude_desktop_config.json).

You can run **both modes simultaneously** — they'll show up as two separate
MCP servers in Claude Desktop.

## Claude Code (CLI)

Add to `~/.config/claude-code/mcp.json`:

```json
{
  "mailcow-admin": {
    "command": "uvx",
    "args": ["mcp-mailcow", "--mode", "admin"],
    "env": {
      "MAILCOW_ADMIN_URL": "https://mail.example.com",
      "MAILCOW_ADMIN_API_KEY": "..."
    }
  }
}
```

## Node.js usage instead of Python

Replace the `command`+`args` with the npm version:

```json
{
  "command": "npx",
  "args": ["mcp-mailcow", "--mode", "admin"]
}
```

Or if installed globally:

```json
{
  "command": "mcp-mailcow",
  "args": ["--mode", "admin"]
}
```

## Tips

### Get a Mailcow API key
Mailcow admin UI → Configuration → Access → API → Create new API key.
Add the IP that will run the MCP to `API_ALLOW_FROM` in `mailcow.conf`.

### Get an app password (user mode)
Mailcow → User UI → Mail Setup → App Passwords → Create new.
Scope it to **IMAP + SMTP** only. Don't reuse your main mailbox password —
app passwords are revocable individually.

### Audit log location
By default: `~/.local/state/mcp-mailcow/audit.log` (Linux/macOS XDG).
Override with `MCP_MAILCOW_AUDIT_LOG=/path/to/audit.log`.

### TLS troubleshooting
If your Mailcow uses a self-signed cert (e.g. local lab setup), set
`MCP_MAILCOW_TLS_VERIFY=false`. Don't do this in production — get a real
Let's Encrypt cert, Mailcow ships ACME natively.
