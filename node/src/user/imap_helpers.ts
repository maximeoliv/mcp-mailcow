/**
 * IMAP helpers using imapflow.
 * Mirrors py/src/mcp_mailcow/imap_helpers.py.
 */
import { ImapFlow } from "imapflow";
import type { UserConfig } from "../config.js";

export async function withImapSession<T>(
  config: UserConfig,
  fn: (client: ImapFlow) => Promise<T>,
): Promise<T> {
  const client = new ImapFlow({
    host: config.host,
    port: config.imapPort,
    secure: true,
    auth: { user: config.mailUser, pass: config.mailPass },
    tls: { rejectUnauthorized: config.tlsVerify },
    logger: false,
  });
  try {
    await client.connect();
    return await fn(client);
  } finally {
    try {
      await client.logout();
    } catch {
      /* ignore */
    }
  }
}

export interface MessageSummary {
  uid: number;
  folder: string;
  subject: string;
  from: string | null;
  to: string[];
  cc: string[];
  date: string | null;
  message_id: string;
  size: number;
  flags: string[];
}

export interface ParsedMessage {
  headers: Record<string, string>;
  body_plain: string;
  body_html?: string;
  attachments: Array<{
    part_id: string;
    filename: string | null;
    mime_type: string;
    size: number;
  }>;
}

export function formatAddress(addrs: Array<{ name?: string; address?: string }> | undefined): string | null {
  if (!addrs || addrs.length === 0) return null;
  const a = addrs[0];
  return `${a.name ?? ""} <${a.address ?? ""}>`.trim();
}

export function formatAddresses(addrs: Array<{ name?: string; address?: string }> | undefined): string[] {
  if (!addrs) return [];
  return addrs.map((a) => formatAddress([a]) ?? "");
}
