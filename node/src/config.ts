/**
 * Configuration loading from environment variables.
 * Mirrors py/src/mcp_mailcow/config.py.
 */
import { homedir } from "node:os";
import { join } from "node:path";

export interface UserConfig {
  host: string;
  mailUser: string;
  mailPass: string;
  /** IMAP host — defaults to `host` if not set explicitly. */
  imapHost: string;
  /** SMTP host — defaults to `host` if not set explicitly. */
  smtpHost: string;
  imapPort: number;
  smtpPort: number;
  tlsVerify: boolean;
  auditLog: string;
}

export interface AdminConfig {
  baseUrl: string;
  apiKey: string;
  tlsVerify: boolean;
  /** Timeout per HTTP request in ms. Default 60_000 (was 30_000 in v0.3). */
  apiTimeoutMs?: number;
  auditLog: string;
}

const DEFAULT_AUDIT_LOG = join(
  process.env.XDG_STATE_HOME || join(homedir(), ".local", "state"),
  "mcp-mailcow",
  "audit.log",
);

function require_(name: string): string {
  const val = process.env[name];
  if (!val) {
    process.stderr.write(`error: required env var ${name} is not set\n`);
    process.exit(2);
  }
  return val;
}

function boolEnv(name: string, def: boolean): boolean {
  const v = process.env[name];
  if (v === undefined) return def;
  return ["1", "true", "yes", "on"].includes(v.toLowerCase());
}

/**
 * Hide a secret-bearing property from JSON.stringify / console.log /
 * util.inspect by making it non-enumerable. The value remains readable
 * via direct property access (`cfg.mailPass`), which is what the IMAP
 * and SMTP helpers do — but it never appears in a debug log or in an
 * Error message that interpolates the config object.
 */
function _hideSecret<T extends object>(obj: T, prop: keyof T, value: string): void {
  Object.defineProperty(obj, prop, {
    value,
    enumerable: false,
    writable: false,
    configurable: false,
  });
}

export function loadUserConfig(): UserConfig {
  const host = require_("MAILCOW_HOST");
  const cfg = {
    host,
    mailUser: require_("MAILCOW_MAIL_USER"),
    imapHost: process.env.MAILCOW_IMAP_HOST || host,
    smtpHost: process.env.MAILCOW_SMTP_HOST || host,
    imapPort: Number.parseInt(process.env.MAILCOW_IMAP_PORT || "993", 10),
    smtpPort: Number.parseInt(process.env.MAILCOW_SMTP_PORT || "587", 10),
    tlsVerify: boolEnv("MCP_MAILCOW_TLS_VERIFY", true),
    auditLog: process.env.MCP_MAILCOW_AUDIT_LOG || DEFAULT_AUDIT_LOG,
  } as UserConfig;
  _hideSecret(cfg, "mailPass", require_("MAILCOW_MAIL_PASS"));
  return cfg;
}

export function loadAdminConfig(): AdminConfig {
  const cfg = {
    baseUrl: require_("MAILCOW_ADMIN_URL").replace(/\/$/, ""),
    tlsVerify: boolEnv("MCP_MAILCOW_TLS_VERIFY", true),
    apiTimeoutMs:
      Number.parseInt(process.env.MCP_MAILCOW_API_TIMEOUT_MS || "60000", 10) || 60_000,
    auditLog: process.env.MCP_MAILCOW_AUDIT_LOG || DEFAULT_AUDIT_LOG,
  } as AdminConfig;
  _hideSecret(cfg, "apiKey", require_("MAILCOW_ADMIN_API_KEY"));
  return cfg;
}
