/**
 * Sanitize text that may flow back to the LLM context.
 *
 * The MCP server returns text content to the calling agent. Anything
 * that might contain a secret value (password, API key, token, app
 * password) must be redacted before it leaves the process boundary.
 *
 * Mirror of py/src/mcp_mailcow/secret_sanitize.py.
 *
 * The rule "no secret in LLM context" is non-negotiable — both as a
 * tool call argument and as a tool response value.
 */

// Keys whose value must be masked. Case-insensitive on the key.
const SECRET_KEYS: ReadonlyArray<string> = [
  // Bare names
  "password",
  "passwd",
  "password2",
  "passwd2",
  "app_passwd",
  "app_passwd2",
  "app_password",
  "client_secret",
  "api_key",
  "apikey",
  "api-key",
  "x-api-key",
  "token",
  "access_token",
  "refresh_token",
  "secret",
  // Internal field names (config interfaces, etc.)
  "mail_pass",
  "mailpass",
  // Env var conventions (uppercase variants)
  "mailcow_mail_pass",
  "mailcow_admin_api_key",
  "mailcow_api_key",
  "mailcow_password",
  "npm_token",
  "pypi_api_token",
  "github_token",
];

const _ESCAPED = SECRET_KEYS.map((k) => k.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&"));
const _KEY_ALT = _ESCAPED.join("|");

// key=value | key: value | key is value, optional quoting on value.
const _KV_PATTERN = new RegExp(
  `\\b(?<key>${_KEY_ALT})\\b(?<sep>\\s*[:=]\\s*|\\s+is\\s+)(?<quote>['"]?)(?<value>[^'"\\s,;}\\]]+)\\k<quote>`,
  "gi",
);

// HTTP Authorization-style: "Bearer <token>" or "Basic <b64>".
const _AUTH_PATTERN = new RegExp(
  `\\b(?<scheme>Bearer|Basic|Token)\\s+(?<value>[A-Za-z0-9\\-._~+/=]{6,})`,
  "gi",
);

export function sanitizeText(text: string): string {
  if (!text) return text;
  let out = text.replace(_KV_PATTERN, (_match: string, ...args: unknown[]) => {
    const groups = args[args.length - 1] as Record<string, string>;
    return `${groups.key}${groups.sep}${groups.quote}***${groups.quote}`;
  });
  out = out.replace(_AUTH_PATTERN, (_match: string, ...args: unknown[]) => {
    const groups = args[args.length - 1] as Record<string, string>;
    return `${groups.scheme} ***`;
  });
  return out;
}

export function sanitizeException(e: unknown): string {
  if (e instanceof Error) {
    const typeName = e.constructor.name;
    const msg = sanitizeText(e.message);
    return msg ? `${typeName}: ${msg}` : typeName;
  }
  return sanitizeText(String(e));
}
