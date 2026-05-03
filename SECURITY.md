# Security policy

## Reporting a vulnerability

If you find a security vulnerability in `mcp-mailcow`, please **do not open a
public issue**. Instead, email the maintainer at `git@maximeolivier.fr` with:

- A description of the issue
- Steps to reproduce (or proof-of-concept)
- The version affected
- Your assessment of impact

You should expect an acknowledgement within 7 days. Fixes for confirmed
critical issues are typically released within 14 days.

## Threat model and design choices

### Secret handling

`mcp-mailcow` is designed to keep credentials safe:

- **Mailcow API keys, IMAP passwords, app passwords** are read from environment
  variables at startup and never written to disk by the MCP itself.
- Tool parameters tagged `secret: true` in `tools-schema.yaml` are automatically
  masked in the audit log (`***` placeholder).
- The `app_password_list` tool masks hashed passwords (`<HASH_MASKED>` /
  `***`) returned by the Mailcow API even though they're already hashed
  (BLF-CRYPT).
- The CLI helpers in the Python `mailcow-api-wrapper` (sibling skill) use the
  `--password-from-env VAR_NAME` convention to avoid passing secrets on argv.

### Network exposure

This MCP runs in **stdio mode only** — it does not bind any port and does not
expose itself over the network. Communication with Claude Desktop / Claude
Code is via stdin/stdout pipes. The only network egress is to your Mailcow
instance (HTTPS for the REST API, IMAPS for mailbox reads, SMTPS/STARTTLS
for sends).

If you choose to run the MCP on a remote machine and expose it via SSH or a
secure tunnel, that's your operational choice — the MCP itself does not
provide HTTP/SSE transport in this version.

### TLS

By default, all connections to your Mailcow verify TLS certificates. You can
disable this with `MCP_MAILCOW_TLS_VERIFY=false` for self-signed certs, but
**do not do this** in production. Get a valid Let's Encrypt cert; Mailcow
ships ACME built-in.

### Destructive operations

Every admin operation that deletes data requires `confirm: true` in the
arguments, e.g.:

```json
{ "email": "user@example.com", "confirm": true }
```

The MCP refuses to delete without this flag, even from a privileged caller.
This guards against accidental destructive calls from over-eager agents.

### Audit log

Every tool invocation is logged to `~/.local/state/mcp-mailcow/audit.log`
(JSONL) with timestamp, tool name, parameters (with secrets masked), success/
failure, and duration. Review this log periodically.

## Known limitations

1. **HTTP transport** is not yet implemented. If/when added, it will require
   an authentication layer (recommended: shared secret + tailnet-only ACL).

2. **Multi-tenancy** is not supported. The MCP authenticates as a single
   admin user (or single mailbox user). For per-user isolation, run separate
   MCP instances with different credentials.

3. **Rate limiting** of the MCP itself is not implemented. The Mailcow API
   has its own rate limits, but a buggy or malicious agent could spam the
   MCP. Consider running it behind a subprocess wrapper that monitors call
   frequency.

4. **Concurrent audit log writes**: when both the user-mode and admin-mode
   MCPs run side-by-side and write to the same audit log file, individual
   JSONL entries < 4 KB are atomic on Linux (POSIX `PIPE_BUF` guarantee).
   Larger entries (e.g. tool params containing large binary attachments
   encoded in base64) may interleave between processes. JSONL parsers
   should tolerate occasional malformed lines; if you need stricter
   guarantees, set `MCP_MAILCOW_AUDIT_LOG` to different paths per mode or
   wrap with `flock()` (currently not enabled by default to avoid sync
   overhead).

## Out of scope

The following are not security concerns of this project:

- Mailcow itself — vulnerabilities in Mailcow should be reported upstream
  to https://github.com/mailcow/mailcow-dockerized.
- Claude / MCP protocol — issues with the protocol layer should be reported
  to https://github.com/modelcontextprotocol/specification.
- Your local machine's security — protecting your credentials in environment
  variables and your audit log file is your responsibility.
