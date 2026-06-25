# Windows specifics — Claude Desktop and Claude Code CLI

The default config examples assume `python` resolves to a real interpreter.
On Windows that's not always the case — feedback from real-world testing on
a Shadow PC running Windows 11 surfaced a few quirks. This page covers both
Claude Desktop and Claude Code CLI (which use different config files).

## Claude Desktop vs Claude Code CLI on Windows

Two distinct config files, two distinct paths. Don't confuse them.

| Client | Config file path |
|---|---|
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` |
| Claude Code CLI | `%USERPROFILE%\.claude.json` |

The JSON shape is the same (`mcpServers: {...}` at the top level), so the
snippets below work in both files. Just point your editor at the right one.

### Claude Code CLI on Windows — specifics

- `%USERPROFILE%` typically resolves to `C:\Users\<You>`, so the full path
  is `C:\Users\<You>\.claude.json`.
- Reload after editing: in Claude Code CLI, press `Ctrl+C` then re-run
  `claude` (or restart your terminal). MCP servers are loaded at session
  start, not hot-reloaded.
- The `mcpServers` block is read at boot. A syntax error in the JSON
  prevents Claude Code from starting — validate with `python -m json.tool
  %USERPROFILE%\.claude.json` before re-launching.



## Pitfall #1 — `command: "python"` vs Microsoft Store stub

By default, Windows ships with a `python.exe` shim that opens the Microsoft
Store rather than running Python. If you have Python installed via the MS
Store, this works; if you've installed Python yourself (e.g. from
python.org), MCP launchers using `command: "python"` may fail silently.

**Fix** : use the absolute path or the `py.exe` launcher.

```json
{
  "mcpServers": {
    "mailcow-admin": {
      "command": "C:\\Users\\<You>\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe",
      "args": ["-m", "mcp_mailcow", "--mode", "admin"],
      "env": { "...": "..." }
    }
  }
}
```

Or with `py.exe` (cross-version Windows launcher):

```json
{
  "command": "py",
  "args": ["-3", "-m", "mcp_mailcow", "--mode", "admin"]
}
```

## Pitfall #2 — backslashes in JSON paths

JSON requires backslashes to be escaped: `C:\\Users\\Shadow\\...`. Use
double-backslash (`\\`) or forward slashes (`/`) — both work on Windows.

```json
"command": "C:\\path\\to\\python.exe"
```
or
```json
"command": "C:/path/to/python.exe"
```

## Pitfall #3 — editing the config file

`claude_desktop_config.json` lives at:

```
%APPDATA%\Claude\claude_desktop_config.json
```

Open it with Notepad, VS Code, or any editor — but **don't** open it via
the file menu in Claude Desktop on Windows; the in-app editor sometimes
refuses to save changes due to file locks.

## Pitfall #4 — `uvx` installation

`uvx` (the recommended zero-install runner from `uv`) needs `uv` itself
installed. If you haven't:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Reload your terminal after install. Then `uvx mcp-mailcow --help` should
work as expected.

## Pitfall #5 — long paths in env vars

Windows has historical issues with long paths (>260 chars) in env vars.
If you put `MCP_MAILCOW_AUDIT_LOG` somewhere deep, you may hit limits on
older systems. Use a short path like `C:\mcp\audit.log` if affected.

## Verifying setup

After editing `claude_desktop_config.json`, restart Claude Desktop. In the
chat, ask:

> Use the `server_version` tool from mailcow-admin

You should get back something like `{"version": "2026-03b"}`. If you see
"unknown tool" or a connection error, check the Claude Desktop logs at:

```
%APPDATA%\Claude\logs\
```

These show MCP server startup errors (typically Python ImportError or
missing env vars).
