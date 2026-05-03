"""SMTP submission helpers (port 587 STARTTLS by default)."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

from .config import UserConfig


def build_message(
    *,
    sender: str,
    to: list[str],
    subject: str,
    body: str,
    body_html: str | None = None,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    reply_to: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    if reply_to:
        msg["Reply-To"] = reply_to
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    msg.set_content(body)
    if body_html:
        msg.add_alternative(body_html, subtype="html")

    for att in attachments or []:
        import base64

        data = base64.b64decode(att["content_b64"])
        mime = att.get("mime_type", "application/octet-stream")
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(
            data,
            maintype=maintype,
            subtype=subtype or "octet-stream",
            filename=att["filename"],
        )
    return msg


def send_via_submission(config: UserConfig, msg: EmailMessage) -> str:
    """Send msg via SMTP submission (587 STARTTLS or 465 SSL)."""
    ctx = ssl.create_default_context()
    if not config.tls_verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    smtp_host = config.smtp_host or config.host
    if config.smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, config.smtp_port, context=ctx, timeout=30) as s:
            s.login(config.mail_user, config.mail_pass)
            s.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, config.smtp_port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(config.mail_user, config.mail_pass)
            s.send_message(msg)
    return msg["Message-ID"] or ""
