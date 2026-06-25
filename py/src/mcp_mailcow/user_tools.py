"""User-mode tool implementations (IMAP/SMTP).

Each tool factory returns an async callable that the registry wires up.
"""

from __future__ import annotations

import base64
import email
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

from .audit import AuditLogger
from .config import UserConfig
from .exceptions import ConfirmationRequired
from .imap_helpers import append_to_sent, imap_session, parse_full_message, parse_message_summary
from .smtp_helpers import build_message, send_via_submission

ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass
class UserContext:
    config: UserConfig
    audit: AuditLogger


# =============================================================================
# READ
# =============================================================================

def list_inbox(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("list_inbox", args):
            folder = args.get("folder", "INBOX")
            limit = min(int(args.get("limit", 20)), 200)
            unread_only = bool(args.get("unread_only", False))
            since = args.get("since")

            with imap_session(ctx.config) as imap:
                imap.select_folder(folder, readonly=True)
                criteria: list[Any] = ["UNSEEN"] if unread_only else ["ALL"]
                if since:
                    criteria.extend(["SINCE", since])
                uids = imap.search(criteria)
                uids = sorted(uids, reverse=True)[:limit]
                if not uids:
                    return []
                resp = imap.fetch(uids, ["ENVELOPE", "FLAGS", "RFC822.SIZE"])
                out = []
                for uid in uids:
                    e = resp[uid]
                    summary = parse_message_summary(
                        e[b"ENVELOPE"], e[b"FLAGS"], e[b"RFC822.SIZE"]
                    )
                    summary["uid"] = uid
                    summary["folder"] = folder
                    out.append(summary)
                return out
    return h


def read_message(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("read_message", args):
            uid = int(args["uid"])
            folder = args.get("folder", "INBOX")
            mark_read = bool(args.get("mark_read", False))

            with imap_session(ctx.config) as imap:
                imap.select_folder(folder, readonly=not mark_read)
                resp = imap.fetch([uid], ["RFC822", "FLAGS"])
                if uid not in resp:
                    raise RuntimeError(f"message uid={uid} not found in {folder}")
                raw = resp[uid][b"RFC822"]
                parsed = parse_full_message(raw)
                if not args.get("fetch_html"):
                    parsed.pop("body_html", None)
                return parsed
    return h


def get_message_raw(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("get_message_raw", args):
            uid = int(args["uid"])
            folder = args.get("folder", "INBOX")
            with imap_session(ctx.config) as imap:
                imap.select_folder(folder, readonly=True)
                resp = imap.fetch([uid], ["RFC822"])
                if uid not in resp:
                    raise RuntimeError(f"message uid={uid} not found")
                return {"raw": resp[uid][b"RFC822"].decode("utf-8", errors="replace")}
    return h


def search_messages(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("search_messages", args):
            query = args["query"]
            folder = args.get("folder", "INBOX")
            limit = min(int(args.get("limit", 50)), 500)

            # IMAP SEARCH expects a list of tokens (criteria + values).
            # We split the query string respecting double-quoted segments.
            import shlex
            criteria = shlex.split(query)

            with imap_session(ctx.config) as imap:
                imap.select_folder(folder, readonly=True)
                uids = imap.search(criteria)
                uids = sorted(uids, reverse=True)[:limit]
                if not uids:
                    return []
                resp = imap.fetch(uids, ["ENVELOPE", "FLAGS", "RFC822.SIZE"])
                out = []
                for uid in uids:
                    e = resp[uid]
                    summary = parse_message_summary(
                        e[b"ENVELOPE"], e[b"FLAGS"], e[b"RFC822.SIZE"]
                    )
                    summary["uid"] = uid
                    summary["folder"] = folder
                    out.append(summary)
                return out
    return h


def get_unread_count(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("get_unread_count", args):
            target = args.get("folder")
            with imap_session(ctx.config) as imap:
                if target:
                    status = imap.folder_status(target, [b"UNSEEN", b"MESSAGES"])
                    return {
                        "folder": target,
                        "unread": status[b"UNSEEN"],
                        "total": status[b"MESSAGES"],
                    }
                folders = imap.list_folders()
                out = []
                for _flags, _delim, name in folders:
                    try:
                        status = imap.folder_status(name, [b"UNSEEN", b"MESSAGES"])
                        out.append({
                            "folder": name,
                            "unread": status[b"UNSEEN"],
                            "total": status[b"MESSAGES"],
                        })
                    except Exception:
                        # some pseudo-folders may not support STATUS
                        continue
                return out
    return h


def download_attachment(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("download_attachment", args):
            uid = int(args["uid"])
            folder = args.get("folder", "INBOX")
            target_part_id = args["part_id"]
            max_bytes = int(args.get("max_size_mb", 25)) * 1024 * 1024

            with imap_session(ctx.config) as imap:
                imap.select_folder(folder, readonly=True)
                resp = imap.fetch([uid], ["RFC822"])
                if uid not in resp:
                    raise RuntimeError(f"message uid={uid} not found")
                msg = email.message_from_bytes(resp[uid][b"RFC822"])
                for part in msg.walk():
                    cid = part.get("Content-ID")
                    fname = part.get_filename()
                    if cid == target_part_id or fname == target_part_id:
                        data = part.get_payload(decode=True) or b""
                        if len(data) > max_bytes:
                            raise RuntimeError(
                                f"attachment {target_part_id} ({len(data)} bytes) exceeds max_size_mb"
                            )
                        return {
                            "filename": fname,
                            "mime_type": part.get_content_type(),
                            "size": len(data),
                            "content_b64": base64.b64encode(data).decode("ascii"),
                        }
                raise RuntimeError(f"attachment '{target_part_id}' not found in message uid={uid}")
    return h


# =============================================================================
# FOLDERS
# =============================================================================

def list_folders(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("list_folders", args):
            with imap_session(ctx.config) as imap:
                folders = imap.list_folders()
                return [
                    {
                        "name": name,
                        "delimiter": delim.decode() if delim else "",
                        "flags": [f.decode() for f in flags],
                    }
                    for flags, delim, name in folders
                ]
    return h


def create_folder(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("create_folder", args):
            with imap_session(ctx.config) as imap:
                imap.create_folder(args["name"])
                return {"created": args["name"]}
    return h


def rename_folder(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("rename_folder", args):
            with imap_session(ctx.config) as imap:
                imap.rename_folder(args["old_name"], args["new_name"])
                return {"renamed": args["old_name"], "to": args["new_name"]}
    return h


def delete_folder(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        if not args.get("confirm"):
            raise ConfirmationRequired("delete_folder requires confirm=true")
        with ctx.audit.trace("delete_folder", args):
            with imap_session(ctx.config) as imap:
                imap.delete_folder(args["name"])
                return {"deleted": args["name"]}
    return h


def empty_folder(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        if not args.get("confirm"):
            raise ConfirmationRequired("empty_folder requires confirm=true")
        with ctx.audit.trace("empty_folder", args):
            with imap_session(ctx.config) as imap:
                imap.select_folder(args["folder"])
                uids = imap.search(["ALL"])
                if uids:
                    imap.delete_messages(uids)
                    imap.expunge()
                return {"emptied": args["folder"], "count": len(uids)}
    return h


# =============================================================================
# SEND
# =============================================================================

def send_message(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("send_message", args):
            msg = build_message(
                sender=ctx.config.mail_user,
                to=list(args["to"]),
                subject=args["subject"],
                body=args["body"],
                body_html=args.get("body_html"),
                cc=args.get("cc"),
                bcc=args.get("bcc"),
                reply_to=args.get("reply_to"),
                in_reply_to=args.get("in_reply_to"),
                attachments=args.get("attachments"),
            )
            mid = send_via_submission(ctx.config, msg)
            appended = append_to_sent(ctx.config, msg)
            return {
                "sent": True,
                "message_id": mid,
                "to": args["to"],
                "sent_folder_appended": appended,
            }
    return h


def reply_to_message(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("reply_to_message", args):
            uid = int(args["uid"])
            folder = args.get("folder", "INBOX")
            reply_all = bool(args.get("reply_all", False))
            include_quoted = bool(args.get("include_quoted", True))

            with imap_session(ctx.config) as imap:
                imap.select_folder(folder, readonly=True)
                resp = imap.fetch([uid], ["RFC822"])
                if uid not in resp:
                    raise RuntimeError(f"message uid={uid} not found")
                orig: EmailMessage = email.message_from_bytes(
                    resp[uid][b"RFC822"], _class=EmailMessage
                )

            # Reply addressing
            reply_to = orig.get("Reply-To") or orig.get("From")
            if reply_all:
                cc = []
                if orig.get("To"):
                    cc.extend([a.strip() for a in orig["To"].split(",")])
                if orig.get("Cc"):
                    cc.extend([a.strip() for a in orig["Cc"].split(",")])
                # Filter out our own address
                cc = [a for a in cc if ctx.config.mail_user not in a]
            else:
                cc = None

            subj = orig.get("Subject", "")
            if not subj.lower().startswith("re:"):
                subj = f"Re: {subj}"

            body = args["body"]
            if include_quoted:
                quoted = "\n\n---\nOn " + orig.get("Date", "?") + ", " + (orig.get("From", "?")) + " wrote:\n"
                orig_body = ""
                for part in orig.walk():
                    if part.get_content_type() == "text/plain":
                        orig_body = (part.get_payload(decode=True) or b"").decode(
                            part.get_content_charset() or "utf-8", errors="replace"
                        )
                        break
                quoted += "\n".join(f"> {line}" for line in orig_body.splitlines())
                body = body + quoted

            msg = build_message(
                sender=ctx.config.mail_user,
                to=[reply_to],
                subject=subj,
                body=body,
                cc=cc,
                in_reply_to=orig.get("Message-ID"),
                references=" ".join(filter(None, [orig.get("References", ""), orig.get("Message-ID", "")])).strip() or None,
            )
            mid = send_via_submission(ctx.config, msg)
            appended = append_to_sent(ctx.config, msg)
            return {
                "sent": True,
                "message_id": mid,
                "in_reply_to": orig.get("Message-ID"),
                "sent_folder_appended": appended,
            }
    return h


def forward_message(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("forward_message", args):
            uid = int(args["uid"])
            folder = args.get("folder", "INBOX")
            include_attachments = bool(args.get("include_attachments", True))
            prefix = args.get("body_prefix", "")

            with imap_session(ctx.config) as imap:
                imap.select_folder(folder, readonly=True)
                resp = imap.fetch([uid], ["RFC822"])
                if uid not in resp:
                    raise RuntimeError(f"message uid={uid} not found")
                orig: EmailMessage = email.message_from_bytes(
                    resp[uid][b"RFC822"], _class=EmailMessage
                )

            subj = orig.get("Subject", "")
            if not subj.lower().startswith("fwd:"):
                subj = f"Fwd: {subj}"

            # Build forwarded body
            orig_plain = ""
            attachments = []
            for part in orig.walk():
                ctype = part.get_content_type()
                fname = part.get_filename()
                if fname and include_attachments:
                    data = part.get_payload(decode=True) or b""
                    attachments.append({
                        "filename": fname,
                        "mime_type": ctype,
                        "content_b64": base64.b64encode(data).decode("ascii"),
                    })
                elif ctype == "text/plain" and not orig_plain:
                    orig_plain = (part.get_payload(decode=True) or b"").decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )

            body = (
                f"{prefix}\n\n"
                f"---------- Forwarded message ----------\n"
                f"From: {orig.get('From', '?')}\n"
                f"Date: {orig.get('Date', '?')}\n"
                f"Subject: {orig.get('Subject', '?')}\n"
                f"To: {orig.get('To', '?')}\n\n"
                f"{orig_plain}"
            )

            msg = build_message(
                sender=ctx.config.mail_user,
                to=list(args["to"]),
                subject=subj,
                body=body,
                attachments=attachments if include_attachments else None,
            )
            mid = send_via_submission(ctx.config, msg)
            appended = append_to_sent(ctx.config, msg)
            return {
                "sent": True,
                "message_id": mid,
                "to": args["to"],
                "sent_folder_appended": appended,
            }
    return h


def save_draft(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("save_draft", args):
            msg = build_message(
                sender=ctx.config.mail_user,
                to=list(args.get("to") or []),
                subject=args.get("subject", ""),
                body=args.get("body", ""),
                cc=args.get("cc"),
            )
            with imap_session(ctx.config) as imap:
                drafts = "Drafts"
                resp = imap.append(drafts, msg.as_bytes(), flags=[r"\Draft"])
                return {"saved": True, "folder": drafts, "raw_response": str(resp)}
    return h


# =============================================================================
# FLAGS
# =============================================================================

def _set_flag_handler(ctx: UserContext, action: str, flag: str, add: bool) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace(action, args):
            uid = int(args["uid"])
            folder = args.get("folder", "INBOX")
            with imap_session(ctx.config) as imap:
                imap.select_folder(folder)
                if add:
                    imap.add_flags([uid], [flag])
                else:
                    imap.remove_flags([uid], [flag])
                return {"uid": uid, "flag": flag, "added": add}
    return h


def mark_read(ctx: UserContext) -> ToolHandler:
    return _set_flag_handler(ctx, "mark_read", "\\Seen", True)


def mark_unread(ctx: UserContext) -> ToolHandler:
    return _set_flag_handler(ctx, "mark_unread", "\\Seen", False)


def mark_flagged(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        return await _set_flag_handler(ctx, "mark_flagged", "\\Flagged", bool(args.get("value", True)))(args)
    return h


def set_custom_flag(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        return await _set_flag_handler(ctx, "set_custom_flag", args["flag"], bool(args.get("value", True)))(args)
    return h


def move_message(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("move_message", args):
            uid = int(args["uid"])
            with imap_session(ctx.config) as imap:
                imap.select_folder(args.get("source_folder", "INBOX"))
                imap.move([uid], args["dest_folder"])
                return {"moved": uid, "to": args["dest_folder"]}
    return h


def delete_message(ctx: UserContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("delete_message", args):
            uid = int(args["uid"])
            folder = args.get("folder", "INBOX")
            purge = bool(args.get("purge", False))
            with imap_session(ctx.config) as imap:
                imap.select_folder(folder)
                if purge:
                    imap.delete_messages([uid])
                    imap.expunge()
                    return {"purged": uid}
                else:
                    imap.move([uid], "Trash")
                    return {"trashed": uid}
    return h
