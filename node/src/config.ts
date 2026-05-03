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
  imapPort: number;
  smtpPort: number;
  tlsVerify: boolean;
  auditLog: string;
}

export interface AdminConfig {
  baseUrl: string;
  apiKey: string;
  tlsVerify: boolean;
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

export function loadUserConfig(): UserConfig {
  return {
    host: require_("MAILCOW_HOST"),
    mailUser: require_("MAILCOW_MAIL_USER"),
    mailPass: require_("MAILCOW_MAIL_PASS"),
    imapPort: Number.parseInt(process.env.MAILCOW_IMAP_PORT || "993", 10),
    smtpPort: Number.parseInt(process.env.MAILCOW_SMTP_PORT || "587", 10),
    tlsVerify: boolEnv("MCP_MAILCOW_TLS_VERIFY", true),
    auditLog: process.env.MCP_MAILCOW_AUDIT_LOG || DEFAULT_AUDIT_LOG,
  };
}

export function loadAdminConfig(): AdminConfig {
  return {
    baseUrl: require_("MAILCOW_ADMIN_URL").replace(/\/$/, ""),
    apiKey: require_("MAILCOW_ADMIN_API_KEY"),
    tlsVerify: boolEnv("MCP_MAILCOW_TLS_VERIFY", true),
    auditLog: process.env.MCP_MAILCOW_AUDIT_LOG || DEFAULT_AUDIT_LOG,
  };
}
