/**
 * SMTP submission helpers using nodemailer.
 */
import nodemailer from "nodemailer";
import type { UserConfig } from "../config.js";

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

export async function sendViaSubmission(
  config: UserConfig,
  opts: SendOptions,
): Promise<string> {
  const transporter = nodemailer.createTransport({
    host: config.smtpHost || config.host,
    port: config.smtpPort,
    secure: config.smtpPort === 465,
    auth: { user: config.mailUser, pass: config.mailPass },
    tls: { rejectUnauthorized: config.tlsVerify },
  });

  const info = await transporter.sendMail({
    from: opts.sender,
    to: opts.to,
    cc: opts.cc,
    bcc: opts.bcc,
    replyTo: opts.replyTo,
    subject: opts.subject,
    text: opts.body,
    html: opts.bodyHtml,
    inReplyTo: opts.inReplyTo,
    references: opts.references,
    attachments: opts.attachments?.map((a) => ({
      filename: a.filename,
      content: Buffer.from(a.content_b64, "base64"),
      contentType: a.mime_type,
    })),
  });

  return (info.messageId as string) || "";
}
