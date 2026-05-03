/**
 * Audit log: JSONL with automatic secret masking.
 * Mirrors py/src/mcp_mailcow/audit.py.
 */
import { mkdirSync, appendFileSync } from "node:fs";
import { dirname } from "node:path";

const SECRET_PARAM_NAMES = new Set([
  "password",
  "password2",
  "app_passwd",
  "app_passwd2",
  "client_secret",
  "api_key",
  "key",
  "token",
]);

function maskSecrets(params: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(params)) {
    if (SECRET_PARAM_NAMES.has(k) && v) {
      out[k] = "***";
    } else if (v && typeof v === "object" && !Array.isArray(v)) {
      out[k] = maskSecrets(v as Record<string, unknown>);
    } else {
      out[k] = v;
    }
  }
  return out;
}

export class AuditLogger {
  constructor(private readonly path: string) {
    mkdirSync(dirname(path), { recursive: true });
  }

  write(
    action: string,
    params: Record<string, unknown>,
    result: "ok" | "err",
    durationMs: number,
    error?: string,
  ): void {
    const entry = {
      ts: new Date().toISOString(),
      action,
      params: maskSecrets(params),
      result,
      duration_ms: durationMs,
      ...(error ? { error } : {}),
    };
    appendFileSync(this.path, `${JSON.stringify(entry)}\n`, "utf-8");
  }

  async trace<T>(
    action: string,
    params: Record<string, unknown>,
    fn: () => Promise<T>,
  ): Promise<T> {
    const start = performance.now();
    try {
      const result = await fn();
      this.write(action, params, "ok", Math.round(performance.now() - start));
      return result;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      this.write(action, params, "err", Math.round(performance.now() - start), msg);
      throw err;
    }
  }
}
