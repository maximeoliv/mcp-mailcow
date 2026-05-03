/**
 * User-mode tool handlers (IMAP via imapflow, SMTP via nodemailer).
 *
 * Mirrors py/src/mcp_mailcow/user_tools.py.
 */
import type { UserConfig } from "../config.js";
import type { AuditLogger } from "../audit.js";
import { withImapSession, formatAddress, formatAddresses } from "./imap_helpers.js";
import { sendViaSubmission } from "./smtp_helpers.js";

type Args = Record<string, unknown>;
export type Handler = (args: Args) => Promise<unknown>;

export interface UserContext {
  config: UserConfig;
  audit: AuditLogger;
}

export function makeContext(config: UserConfig, audit: AuditLogger): UserContext {
  return { config, audit };
}

// =============================================================================
// READ
// =============================================================================

export const list_inbox = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("list_inbox", args, async () => {
    const folder = (args.folder as string) ?? "INBOX";
    const limit = Math.min(Number(args.limit ?? 20), 200);
    const unreadOnly = Boolean(args.unread_only);
    const since = args.since as string | undefined;

    return withImapSession(ctx.config, async (imap) => {
      const lock = await imap.getMailboxLock(folder, { readonly: true });
      try {
        const search: Record<string, unknown> = unreadOnly ? { seen: false } : { all: true };
        if (since) search.since = new Date(since);
        const uids = ((await imap.search(search, { uid: true })) as number[]) ?? [];
        const sorted = uids.sort((a, b) => b - a).slice(0, limit);
        if (sorted.length === 0) return [];
        const out = [];
        for await (const msg of imap.fetch(sorted, { envelope: true, flags: true, size: true }, { uid: true })) {
          out.push({
            uid: msg.uid,
            folder,
            subject: msg.envelope?.subject ?? "",
            from: formatAddress(msg.envelope?.from),
            to: formatAddresses(msg.envelope?.to),
            cc: formatAddresses(msg.envelope?.cc),
            date: msg.envelope?.date?.toISOString() ?? null,
            message_id: msg.envelope?.messageId ?? "",
            size: msg.size ?? 0,
            flags: Array.from(msg.flags ?? []),
          });
        }
        return out;
      } finally {
        lock.release();
      }
    });
  });

export const read_message = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("read_message", args, async () => {
    const uid = Number(args.uid);
    const folder = (args.folder as string) ?? "INBOX";
    const markRead = Boolean(args.mark_read);

    return withImapSession(ctx.config, async (imap) => {
      const lock = await imap.getMailboxLock(folder, { readonly: !markRead });
      try {
        const msg = await imap.fetchOne(uid, { source: true }, { uid: true });
        if (!msg?.source) throw new Error(`message uid=${uid} not found`);
        const { simpleParser } = await import("mailparser");
        const parsed = await simpleParser(msg.source);
        const result: Record<string, unknown> = {
          headers: Object.fromEntries(parsed.headers as Map<string, unknown>),
          body_plain: parsed.text ?? "",
          attachments: (parsed.attachments ?? []).map((a) => ({
            part_id: a.contentId ?? a.filename ?? a.contentType,
            filename: a.filename ?? null,
            mime_type: a.contentType,
            size: a.size,
          })),
        };
        if (args.fetch_html) result.body_html = parsed.html || "";
        return result;
      } finally {
        lock.release();
      }
    });
  });

export const get_message_raw = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("get_message_raw", args, async () => {
    const uid = Number(args.uid);
    const folder = (args.folder as string) ?? "INBOX";
    return withImapSession(ctx.config, async (imap) => {
      const lock = await imap.getMailboxLock(folder, { readonly: true });
      try {
        const msg = await imap.fetchOne(uid, { source: true }, { uid: true });
        if (!msg?.source) throw new Error(`message uid=${uid} not found`);
        return { raw: msg.source.toString("utf-8") };
      } finally {
        lock.release();
      }
    });
  });

export const search_messages = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("search_messages", args, async () => {
    const query = (args.query as string) ?? "";
    const folder = (args.folder as string) ?? "INBOX";
    const limit = Math.min(Number(args.limit ?? 50), 500);

    // Very basic IMAP search: parse "FROM x SUBJECT y" style
    const search: Record<string, unknown> = {};
    const tokens = query.match(/(?:[^\s"]+|"[^"]*")+/g) ?? [];
    for (let i = 0; i < tokens.length; i++) {
      const t = tokens[i].toUpperCase();
      const v = (tokens[i + 1] || "").replace(/^"|"$/g, "");
      if (t === "FROM") { search.from = v; i++; }
      else if (t === "TO") { search.to = v; i++; }
      else if (t === "SUBJECT") { search.subject = v; i++; }
      else if (t === "BODY") { search.body = v; i++; }
      else if (t === "SINCE") { search.since = new Date(v); i++; }
      else if (t === "BEFORE") { search.before = new Date(v); i++; }
      else if (t === "UNSEEN") { search.seen = false; }
      else if (t === "FLAGGED") { search.flagged = true; }
    }

    return withImapSession(ctx.config, async (imap) => {
      const lock = await imap.getMailboxLock(folder, { readonly: true });
      try {
        const uids = ((await imap.search(search, { uid: true })) as number[]) ?? [];
        const sorted = uids.sort((a, b) => b - a).slice(0, limit);
        if (sorted.length === 0) return [];
        const out = [];
        for await (const msg of imap.fetch(sorted, { envelope: true, flags: true, size: true }, { uid: true })) {
          out.push({
            uid: msg.uid,
            folder,
            subject: msg.envelope?.subject ?? "",
            from: formatAddress(msg.envelope?.from),
            to: formatAddresses(msg.envelope?.to),
            date: msg.envelope?.date?.toISOString() ?? null,
            size: msg.size ?? 0,
            flags: Array.from(msg.flags ?? []),
          });
        }
        return out;
      } finally {
        lock.release();
      }
    });
  });

export const get_unread_count = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("get_unread_count", args, async () => {
    const target = args.folder as string | undefined;
    return withImapSession(ctx.config, async (imap) => {
      if (target) {
        const status = await imap.status(target, { unseen: true, messages: true });
        return { folder: target, unread: status.unseen ?? 0, total: status.messages ?? 0 };
      }
      const out = [];
      for await (const folder of imap.list()) {
        try {
          const status = await imap.status(folder.path, { unseen: true, messages: true });
          out.push({ folder: folder.path, unread: status.unseen ?? 0, total: status.messages ?? 0 });
        } catch {
          /* skip */
        }
      }
      return out;
    });
  });

export const download_attachment = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("download_attachment", args, async () => {
    const uid = Number(args.uid);
    const folder = (args.folder as string) ?? "INBOX";
    const targetPart = args.part_id as string;
    const maxBytes = Number(args.max_size_mb ?? 25) * 1024 * 1024;

    return withImapSession(ctx.config, async (imap) => {
      const lock = await imap.getMailboxLock(folder, { readonly: true });
      try {
        const msg = await imap.fetchOne(uid, { source: true }, { uid: true });
        if (!msg?.source) throw new Error(`message uid=${uid} not found`);
        const { simpleParser } = await import("mailparser");
        const parsed = await simpleParser(msg.source);
        for (const att of parsed.attachments ?? []) {
          if (att.contentId === targetPart || att.filename === targetPart) {
            if (att.size > maxBytes) {
              throw new Error(`attachment ${targetPart} (${att.size} bytes) exceeds max_size_mb`);
            }
            return {
              filename: att.filename,
              mime_type: att.contentType,
              size: att.size,
              content_b64: att.content.toString("base64"),
            };
          }
        }
        throw new Error(`attachment '${targetPart}' not found`);
      } finally {
        lock.release();
      }
    });
  });

// =============================================================================
// FOLDERS
// =============================================================================

export const list_folders = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("list_folders", args, async () =>
    withImapSession(ctx.config, async (imap) => {
      const out = [];
      for await (const f of imap.list()) {
        out.push({ name: f.path, delimiter: f.delimiter ?? "", flags: Array.from(f.flags ?? []) });
      }
      return out;
    }),
  );

export const create_folder = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("create_folder", args, async () =>
    withImapSession(ctx.config, async (imap) => {
      await imap.mailboxCreate(args.name as string);
      return { created: args.name };
    }),
  );

export const rename_folder = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("rename_folder", args, async () =>
    withImapSession(ctx.config, async (imap) => {
      await imap.mailboxRename(args.old_name as string, args.new_name as string);
      return { renamed: args.old_name, to: args.new_name };
    }),
  );

export const delete_folder = (ctx: UserContext): Handler => async (args) => {
  if (!args.confirm) throw new Error("delete_folder requires confirm=true");
  return ctx.audit.trace("delete_folder", args, async () =>
    withImapSession(ctx.config, async (imap) => {
      await imap.mailboxDelete(args.name as string);
      return { deleted: args.name };
    }),
  );
};

export const empty_folder = (ctx: UserContext): Handler => async (args) => {
  if (!args.confirm) throw new Error("empty_folder requires confirm=true");
  return ctx.audit.trace("empty_folder", args, async () =>
    withImapSession(ctx.config, async (imap) => {
      const folder = args.folder as string;
      const lock = await imap.getMailboxLock(folder);
      try {
        const uids = ((await imap.search({ all: true }, { uid: true })) as number[]) ?? [];
        if (uids.length > 0) {
          await imap.messageDelete(uids, { uid: true });
        }
        return { emptied: folder, count: uids.length };
      } finally {
        lock.release();
      }
    }),
  );
};

// =============================================================================
// SEND
// =============================================================================

export const send_message = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("send_message", args, async () => {
    const messageId = await sendViaSubmission(ctx.config, {
      sender: ctx.config.mailUser,
      to: args.to as string[],
      subject: args.subject as string,
      body: args.body as string,
      bodyHtml: args.body_html as string | undefined,
      cc: args.cc as string[] | undefined,
      bcc: args.bcc as string[] | undefined,
      replyTo: args.reply_to as string | undefined,
      inReplyTo: args.in_reply_to as string | undefined,
      attachments: args.attachments as Array<{ filename: string; content_b64: string; mime_type: string }> | undefined,
    });
    return { sent: true, message_id: messageId, to: args.to };
  });

export const reply_to_message = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("reply_to_message", args, async () => {
    const uid = Number(args.uid);
    const folder = (args.folder as string) ?? "INBOX";
    const replyAll = Boolean(args.reply_all);
    const includeQuoted = args.include_quoted !== false;

    const orig = await withImapSession(ctx.config, async (imap) => {
      const lock = await imap.getMailboxLock(folder, { readonly: true });
      try {
        const msg = await imap.fetchOne(uid, { source: true, envelope: true }, { uid: true });
        if (!msg?.source) throw new Error(`message uid=${uid} not found`);
        return msg;
      } finally {
        lock.release();
      }
    });

    const env = orig.envelope!;
    const replyAddr = formatAddress(env.replyTo) || formatAddress(env.from) || "";
    let cc: string[] | undefined;
    if (replyAll) {
      cc = [...formatAddresses(env.to), ...formatAddresses(env.cc)].filter(
        (a) => a && !a.includes(ctx.config.mailUser),
      );
    }
    let subj = env.subject ?? "";
    if (!subj.toLowerCase().startsWith("re:")) subj = `Re: ${subj}`;

    let body = args.body as string;
    if (includeQuoted) {
      const { simpleParser } = await import("mailparser");
      const parsed = await simpleParser(orig.source!);
      const quoted =
        `\n\n---\nOn ${env.date?.toISOString() ?? "?"}, ${formatAddress(env.from) ?? "?"} wrote:\n` +
        (parsed.text ?? "")
          .split("\n")
          .map((l) => `> ${l}`)
          .join("\n");
      body = body + quoted;
    }

    const refs = [env.references, env.messageId].filter(Boolean).join(" ");
    const messageId = await sendViaSubmission(ctx.config, {
      sender: ctx.config.mailUser,
      to: [replyAddr],
      subject: subj,
      body,
      cc,
      inReplyTo: env.messageId ?? undefined,
      references: refs || undefined,
    });
    return { sent: true, message_id: messageId, in_reply_to: env.messageId };
  });

export const forward_message = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("forward_message", args, async () => {
    const uid = Number(args.uid);
    const folder = (args.folder as string) ?? "INBOX";
    const includeAttachments = args.include_attachments !== false;
    const prefix = (args.body_prefix as string) ?? "";

    const { source, envelope } = await withImapSession(ctx.config, async (imap) => {
      const lock = await imap.getMailboxLock(folder, { readonly: true });
      try {
        const msg = await imap.fetchOne(uid, { source: true, envelope: true }, { uid: true });
        if (!msg?.source) throw new Error(`message uid=${uid} not found`);
        return { source: msg.source, envelope: msg.envelope };
      } finally {
        lock.release();
      }
    });

    const { simpleParser } = await import("mailparser");
    const parsed = await simpleParser(source);

    let subj = envelope?.subject ?? "";
    if (!subj.toLowerCase().startsWith("fwd:")) subj = `Fwd: ${subj}`;

    const body =
      `${prefix}\n\n` +
      `---------- Forwarded message ----------\n` +
      `From: ${formatAddress(envelope?.from) ?? "?"}\n` +
      `Date: ${envelope?.date?.toISOString() ?? "?"}\n` +
      `Subject: ${envelope?.subject ?? "?"}\n` +
      `To: ${formatAddresses(envelope?.to).join(", ") || "?"}\n\n` +
      (parsed.text ?? "");

    const attachments =
      includeAttachments && parsed.attachments
        ? parsed.attachments.map((a) => ({
            filename: a.filename ?? "attachment",
            content_b64: a.content.toString("base64"),
            mime_type: a.contentType,
          }))
        : undefined;

    const messageId = await sendViaSubmission(ctx.config, {
      sender: ctx.config.mailUser,
      to: args.to as string[],
      subject: subj,
      body,
      attachments,
    });
    return { sent: true, message_id: messageId, to: args.to };
  });

export const save_draft = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("save_draft", args, async () => {
    // Build the message via nodemailer's built-in compose, then APPEND via IMAP
    const nodemailer = (await import("nodemailer")).default;
    const compose = nodemailer.createTransport({ jsonTransport: true });
    const result = await compose.sendMail({
      from: ctx.config.mailUser,
      to: (args.to as string[]) || [],
      subject: (args.subject as string) ?? "",
      text: (args.body as string) ?? "",
      cc: args.cc as string[] | undefined,
    });
    const raw = (result as unknown as { message: string }).message;

    return withImapSession(ctx.config, async (imap) => {
      await imap.append("Drafts", Buffer.from(raw), ["\\Draft"]);
      return { saved: true, folder: "Drafts" };
    });
  });

// =============================================================================
// FLAGS
// =============================================================================

async function setFlag(
  ctx: UserContext,
  args: Args,
  action: string,
  flag: string,
  add: boolean,
): Promise<unknown> {
  return ctx.audit.trace(action, args, async () => {
    const uid = Number(args.uid);
    const folder = (args.folder as string) ?? "INBOX";
    return withImapSession(ctx.config, async (imap) => {
      const lock = await imap.getMailboxLock(folder);
      try {
        if (add) {
          await imap.messageFlagsAdd(uid, [flag], { uid: true });
        } else {
          await imap.messageFlagsRemove(uid, [flag], { uid: true });
        }
        return { uid, flag, added: add };
      } finally {
        lock.release();
      }
    });
  });
}

export const mark_read = (ctx: UserContext): Handler => async (args) =>
  setFlag(ctx, args, "mark_read", "\\Seen", true);

export const mark_unread = (ctx: UserContext): Handler => async (args) =>
  setFlag(ctx, args, "mark_unread", "\\Seen", false);

export const mark_flagged = (ctx: UserContext): Handler => async (args) =>
  setFlag(ctx, args, "mark_flagged", "\\Flagged", args.value !== false);

export const set_custom_flag = (ctx: UserContext): Handler => async (args) =>
  setFlag(ctx, args, "set_custom_flag", args.flag as string, args.value !== false);

export const move_message = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("move_message", args, async () => {
    const uid = Number(args.uid);
    return withImapSession(ctx.config, async (imap) => {
      const src = (args.source_folder as string) ?? "INBOX";
      const lock = await imap.getMailboxLock(src);
      try {
        await imap.messageMove(uid, args.dest_folder as string, { uid: true });
        return { moved: uid, to: args.dest_folder };
      } finally {
        lock.release();
      }
    });
  });

export const delete_message = (ctx: UserContext): Handler => async (args) =>
  ctx.audit.trace("delete_message", args, async () => {
    const uid = Number(args.uid);
    const folder = (args.folder as string) ?? "INBOX";
    const purge = Boolean(args.purge);
    return withImapSession(ctx.config, async (imap) => {
      const lock = await imap.getMailboxLock(folder);
      try {
        if (purge) {
          await imap.messageDelete(uid, { uid: true });
          return { purged: uid };
        }
        await imap.messageMove(uid, "Trash", { uid: true });
        return { trashed: uid };
      } finally {
        lock.release();
      }
    });
  });
