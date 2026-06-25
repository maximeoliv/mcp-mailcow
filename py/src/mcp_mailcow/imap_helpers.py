"""Helpers around imapclient: connection pooling, message parsing.

We open a fresh IMAP connection per tool call (cheap on TLS resumption, simpler
than maintaining a long-lived connection across MCP requests). For high-throughput
flows, this could be replaced with a connection pool later.
"""

from __future__ import annotations

import email
import logging
from contextlib import contextmanager
from datetime import datetime
from email.message import EmailMessage, Message
from typing import Any, Iterator

from imapclient import IMAPClient

from .config import UserConfig

logger = logging.getLogger("mcp_mailcow.imap")


@contextmanager
def imap_session(config: UserConfig) -> Iterator[IMAPClient]:
    client = IMAPClient(
        host=config.imap_host or config.host,
        port=config.imap_port,
        ssl=True,
        ssl_context=None if config.tls_verify else _insecure_context(),
        use_uid=True,
    )
    try:
        client.login(config.mail_user, config.mail_pass)
        yield client
    finally:
        try:
            client.logout()
        except Exception:
            pass


def _insecure_context() -> Any:
    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def parse_message_summary(envelope: Any, flags: tuple[bytes, ...], size: int) -> dict[str, Any]:
    """Build a compact metadata dict from an IMAP FETCH ENVELOPE."""
    return {
        "subject": (envelope.subject or b"").decode("utf-8", errors="replace"),
        "from": _format_addr(envelope.from_),
        "to": _format_addrs(envelope.to),
        "cc": _format_addrs(envelope.cc),
        "date": envelope.date.isoformat() if envelope.date else None,
        "message_id": (envelope.message_id or b"").decode("ascii", errors="replace"),
        "size": size,
        "flags": [f.decode("ascii", errors="replace") for f in flags],
    }


def append_to_sent(config: UserConfig, msg: EmailMessage) -> bool:
    """APPEND a sent message into the user's Sent folder.

    Best-effort: returns True on success, False on any failure (logged).
    Failure does NOT raise — the SMTP send already succeeded by the time
    we get here, the mail is on its way, and we don't want to surface an
    APPEND error as if the send itself failed.

    Folder detection: we look for the SPECIAL-USE \\Sent flag (RFC 6154)
    in the LIST response. Falls back to common folder names if the server
    doesn't advertise SPECIAL-USE (rare for modern Mailcow/Dovecot).
    """
    try:
        with imap_session(config) as client:
            sent_folder = _find_sent_folder(client)
            if not sent_folder:
                logger.warning("no Sent folder found, skipping APPEND")
                return False
            # Mark as already-read in the Sent folder, and date it now.
            client.append(
                sent_folder,
                msg.as_bytes(),
                flags=(b"\\Seen",),
                msg_time=datetime.now(),
            )
            return True
    except Exception:  # noqa: BLE001 — best-effort, never bubble up
        logger.exception("APPEND to Sent failed (mail was sent regardless)")
        return False


def _find_sent_folder(client: IMAPClient) -> str | None:
    """Return the IMAP path of the Sent folder, or None.

    Prefer the SPECIAL-USE \\Sent flag (RFC 6154). Fall back to a list of
    common folder names if no SPECIAL-USE info is available.
    """
    fallbacks = ("Sent", "Sent Items", "Sent Messages", "INBOX.Sent")
    try:
        folders = client.list_folders()
    except Exception:  # noqa: BLE001
        return None
    for flags, _delim, name in folders:
        if b"\\Sent" in flags:
            return name
    folder_names = {n for _f, _d, n in folders}
    for fb in fallbacks:
        if fb in folder_names:
            return fb
    return None


def _format_addr(addrs: Any) -> str | None:
    if not addrs:
        return None
    a = addrs[0]
    name = a.name.decode() if a.name else ""
    mbox = a.mailbox.decode() if a.mailbox else ""
    host = a.host.decode() if a.host else ""
    return f"{name} <{mbox}@{host}>".strip()


def _format_addrs(addrs: Any) -> list[str]:
    return [_format_addr([a]) or "" for a in (addrs or [])]


def parse_full_message(raw: bytes) -> dict[str, Any]:
    """Parse a raw RFC822 message into a structured dict."""
    msg: Message = email.message_from_bytes(raw)
    body_plain = ""
    body_html = ""
    attachments: list[dict[str, Any]] = []

    for part in msg.walk():
        ctype = part.get_content_type()
        cdisp = (part.get("Content-Disposition") or "").lower()
        filename = part.get_filename()

        if filename or "attachment" in cdisp:
            attachments.append({
                "part_id": part.get("Content-ID") or filename or ctype,
                "filename": filename,
                "mime_type": ctype,
                "size": len(part.get_payload(decode=True) or b""),
            })
        elif ctype == "text/plain" and not body_plain:
            payload = part.get_payload(decode=True) or b""
            body_plain = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        elif ctype == "text/html" and not body_html:
            payload = part.get_payload(decode=True) or b""
            body_html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")

    return {
        "headers": {k: msg[k] for k in msg.keys()},
        "body_plain": body_plain,
        "body_html": body_html,
        "attachments": attachments,
    }
