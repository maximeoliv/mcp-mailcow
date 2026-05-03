"""Test SMTP message construction (no actual send)."""

from __future__ import annotations

import base64

from mcp_mailcow.smtp_helpers import build_message


def test_build_minimal_message():
    msg = build_message(
        sender="alice@example.com",
        to=["bob@example.com"],
        subject="Hello",
        body="hi",
    )
    assert msg["From"] == "alice@example.com"
    assert msg["To"] == "bob@example.com"
    assert msg["Subject"] == "Hello"
    assert "hi" in msg.as_string()


def test_build_with_html_alternative():
    msg = build_message(
        sender="a@a.com",
        to=["b@b.com"],
        subject="s",
        body="plain",
        body_html="<p>html</p>",
    )
    assert msg.is_multipart()
    parts = list(msg.iter_parts())
    types = {p.get_content_type() for p in parts}
    assert "text/plain" in types
    assert "text/html" in types


def test_build_with_cc_and_bcc():
    msg = build_message(
        sender="a@a.com",
        to=["b@b.com"],
        subject="s",
        body="x",
        cc=["c1@c.com", "c2@c.com"],
        bcc=["d@d.com"],
    )
    assert msg["Cc"] == "c1@c.com, c2@c.com"
    assert msg["Bcc"] == "d@d.com"


def test_build_with_attachment():
    data = b"hello world"
    msg = build_message(
        sender="a@a.com",
        to=["b@b.com"],
        subject="s",
        body="x",
        attachments=[
            {
                "filename": "test.txt",
                "content_b64": base64.b64encode(data).decode(),
                "mime_type": "text/plain",
            }
        ],
    )
    assert msg.is_multipart()
    has_attachment = any(p.get_filename() == "test.txt" for p in msg.iter_attachments())
    assert has_attachment


def test_build_reply_headers():
    msg = build_message(
        sender="a@a.com",
        to=["b@b.com"],
        subject="Re: x",
        body="ok",
        in_reply_to="<orig-id@b.com>",
        references="<thread-1@b.com> <orig-id@b.com>",
    )
    assert msg["In-Reply-To"] == "<orig-id@b.com>"
    assert "<orig-id@b.com>" in msg["References"]
