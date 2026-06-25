/**
 * SMTP submission helpers using nodemailer.
 */
import { hostname } from "node:os";
import nodemailer from "nodemailer";
import type { UserConfig } from "../config.js";

// Resolved once at module load. Used in the X-Sent-By-Host header
// that every outbound message carries — lets the sysadmin trace which
// machine in the fleet sent a given mail, even when the From address is
// shared across multiple agents.
const _HOSTNAME = hostname();

export interface SendOptions {
  sender: string;
  to: string[];
  subject: string;
  body: string;
  bodyHtml?: string;
  cc?: string[];
  bcc?: string[];
  replyTo?: string;
  inReplyTo?: string;
  references?: string;
  attachments?: Array<{
    filename: string;
    content_b64: string;
    mime_type: string;
  }>;
}

export interface SendResult {
  messageId: string;
  /** RFC822 raw bytes (without BCC), for IMAP APPEND to Sent. */
  raw: Buffer;
}

function _baseMail(opts: SendOptions) {
  return {
    from: opts.sender,
    to: opts.to,
    cc: opts.cc,
    replyTo: opts.replyTo,
    subject: opts.subject,
    text: opts.body,
    html: opts.bodyHtml,
    inReplyTo: opts.inReplyTo,
    references: opts.references,
    // Forensic trace: which machine of the fleet sent this. Survives
    // even when From is a shared persona mailbox used by multiple
    // agents.
    headers: { "X-Sent-By-Host": _HOSTNAME },
    attachments: opts.attachments?.map((a) => ({
      filename: a.filename,
      content: Buffer.from(a.content_b64, "base64"),
      contentType: a.mime_type,
    })),
  };
}

export async function sendViaSubmission(
  config: UserConfig,
  opts: SendOptions,
): Promise<SendResult> {
  const transporter = nodemailer.createTransport({
    host: config.smtpHost || config.host,
    port: config.smtpPort,
    secure: config.smtpPort === 465,
    auth: { user: config.mailUser, pass: config.mailPass },
    tls: { rejectUnauthorized: config.tlsVerify },
  });

  const info = await transporter.sendMail({ ..._baseMail(opts), bcc: opts.bcc });
  const messageId = (info.messageId as string) || "";

  // Compile a raw RFC822 copy without BCC for IMAP APPEND to Sent.
  // RFC 5322: BCC must not appear in the message body delivered to anyone.
  const streamTransport = nodemailer.createTransport({
    streamTransport: true,
    buffer: true,
  });
  const compiled = await streamTransport.sendMail(_baseMail(opts));
  const raw = compiled.message as Buffer;

  return { messageId, raw };
}
