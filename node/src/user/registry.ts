/**
 * User-mode registry: maps tool names to handler factories.
 * Mirrors py/src/mcp_mailcow/registry.py (build_user_registry).
 */
import type { UserConfig } from "../config.js";
import type { AuditLogger } from "../audit.js";
import * as h from "./handlers.js";

type Handler = (args: unknown) => Promise<unknown>;

export function buildUserRegistry(
  config: UserConfig,
  audit: AuditLogger,
): Record<string, Handler> {
  const ctx = h.makeContext(config, audit);
  const wrap = (factory: (c: h.UserContext) => h.Handler): Handler => {
    const fn = factory(ctx);
    return (args: unknown) => fn((args as Record<string, unknown>) ?? {});
  };

  return {
    // mailbox.read
    list_inbox: wrap(h.list_inbox),
    read_message: wrap(h.read_message),
    get_message_raw: wrap(h.get_message_raw),
    search_messages: wrap(h.search_messages),
    get_unread_count: wrap(h.get_unread_count),
    download_attachment: wrap(h.download_attachment),
    // mailbox.folders
    list_folders: wrap(h.list_folders),
    create_folder: wrap(h.create_folder),
    rename_folder: wrap(h.rename_folder),
    delete_folder: wrap(h.delete_folder),
    empty_folder: wrap(h.empty_folder),
    // mailbox.send
    send_message: wrap(h.send_message),
    reply_to_message: wrap(h.reply_to_message),
    forward_message: wrap(h.forward_message),
    save_draft: wrap(h.save_draft),
    // mailbox.flags
    mark_read: wrap(h.mark_read),
    mark_unread: wrap(h.mark_unread),
    mark_flagged: wrap(h.mark_flagged),
    set_custom_flag: wrap(h.set_custom_flag),
    move_message: wrap(h.move_message),
    delete_message: wrap(h.delete_message),
  };
}
