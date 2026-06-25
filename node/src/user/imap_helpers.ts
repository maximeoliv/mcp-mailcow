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
    host: config.imapHost || config.host,
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

/**
 * APPEND a sent message into the user's Sent folder.
 *
 * Best-effort: returns true on success, false on failure. Failure does
 * NOT throw — the SMTP send already succeeded by the time we get here,
 * the mail is on its way, and we don't want to surface an APPEND error
 * as if the send itself failed.
 *
 * Folder detection: SPECIAL-USE \\Sent (RFC 6154) first, fallback to
 * common folder names.
 */
export async function appendToSent(
  config: UserConfig,
  raw: Buffer | string,
): Promise<boolean> {
  try {
    return await withImapSession(config, async (client) => {
      const folder = await findSentFolder(client);
      if (!folder) return false;
      await client.append(folder, raw, ["\\Seen"], new Date());
      return true;
    });
  } catch {
    return false;
  }
}

async function findSentFolder(client: ImapFlow): Promise<string | null> {
  const fallbacks = ["Sent", "Sent Items", "Sent Messages", "INBOX.Sent"];
  try {
    const list = await client.list();
    for (const box of list) {
      const flags = box.flags ?? new Set<string>();
      const specialUse = box.specialUse ?? "";
      if (flags.has("\\Sent") || specialUse === "\\Sent") {
        return box.path;
      }
    }
    const paths = new Set(list.map((b) => b.path));
    for (const fb of fallbacks) {
      if (paths.has(fb)) return fb;
    }
  } catch {
    /* fall through */
  }
  return null;
}
