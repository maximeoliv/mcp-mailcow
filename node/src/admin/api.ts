/**
 * Thin async client over the Mailcow REST API.
 * Mirrors py/src/mcp_mailcow/mailcow_api.py.
 */
import { fetch, Agent } from "undici";

export class MailcowAPIError extends Error {
  constructor(message: string, public readonly payload?: unknown) {
    super(message);
    this.name = "MailcowAPIError";
  }
}

export interface MailcowClientOptions {
  baseUrl: string;
  apiKey: string;
  tlsVerify?: boolean;
  timeoutMs?: number;
}

export class MailcowClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly dispatcher?: Agent;
  private readonly timeoutMs: number;

  constructor(opts: MailcowClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/$/, "");
    this.apiKey = opts.apiKey;
    this.timeoutMs = opts.timeoutMs ?? 30_000;
    if (opts.tlsVerify === false) {
      this.dispatcher = new Agent({ connect: { rejectUnauthorized: false } });
    }
  }

  private async request(method: string, path: string, body?: unknown): Promise<unknown> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers: {
          "X-API-Key": this.apiKey,
          "Content-Type": "application/json",
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
        dispatcher: this.dispatcher,
      });

      if (!response.ok) {
        throw new MailcowAPIError(
          `HTTP ${response.status} ${response.statusText} on ${path}`,
        );
      }

      const text = await response.text();
      let data: unknown;
      try {
        data = JSON.parse(text);
      } catch {
        throw new MailcowAPIError(`non-JSON response from ${path}`, text.slice(0, 500));
      }

      // Mailcow returns HTTP 200 even on errors, with `type: "danger"` payload.
      if (Array.isArray(data)) {
        for (const entry of data) {
          if (entry && typeof entry === "object" && "type" in entry) {
            const e = entry as { type: string; msg?: string };
            if (e.type === "danger" || e.type === "error") {
              throw new MailcowAPIError(`${path}: ${e.msg ?? "unknown error"}`, data);
            }
          }
        }
      } else if (data && typeof data === "object" && "type" in data) {
        const e = data as { type: string; msg?: string };
        if (e.type === "danger" || e.type === "error") {
          throw new MailcowAPIError(`${path}: ${e.msg ?? "unknown error"}`, data);
        }
      }

      return data;
    } finally {
      clearTimeout(timeout);
    }
  }

  get(path: string): Promise<unknown> {
    return this.request("GET", path);
  }

  post(path: string, body: unknown): Promise<unknown> {
    return this.request("POST", path, body);
  }
}
