/**
 * Tests for the AuditLogger (mirror of py/tests/test_audit.py).
 */
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { AuditLogger } from "../src/audit.js";

let dir: string;
beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "mcp-mailcow-test-"));
});
afterEach(() => {
  rmSync(dir, { recursive: true, force: true });
});

describe("AuditLogger", () => {
  it("writes a JSONL entry", () => {
    const log = new AuditLogger(join(dir, "audit.log"));
    log.write("test_action", { foo: "bar" }, "ok", 42);
    const line = JSON.parse(readFileSync(join(dir, "audit.log"), "utf-8").trim());
    expect(line.action).toBe("test_action");
    expect(line.params.foo).toBe("bar");
    expect(line.result).toBe("ok");
    expect(line.duration_ms).toBe(42);
  });

  it("masks password params", () => {
    const log = new AuditLogger(join(dir, "audit.log"));
    log.write("create", { email: "x@y.fr", password: "secret" }, "ok", 1);
    const line = JSON.parse(readFileSync(join(dir, "audit.log"), "utf-8").trim());
    expect(line.params.email).toBe("x@y.fr");
    expect(line.params.password).toBe("***");
  });

  it("masks nested password params", () => {
    const log = new AuditLogger(join(dir, "audit.log"));
    log.write("edit", { items: ["a"], attr: { password: "secret", active: 1 } }, "ok", 1);
    const line = JSON.parse(readFileSync(join(dir, "audit.log"), "utf-8").trim());
    expect(line.params.attr.password).toBe("***");
    expect(line.params.attr.active).toBe(1);
  });

  it("trace records success", async () => {
    const log = new AuditLogger(join(dir, "audit.log"));
    await log.trace("op", { x: 1 }, async () => "result");
    const line = JSON.parse(readFileSync(join(dir, "audit.log"), "utf-8").trim());
    expect(line.result).toBe("ok");
  });

  it("trace records error", async () => {
    const log = new AuditLogger(join(dir, "audit.log"));
    await expect(
      log.trace("op", { x: 1 }, async () => {
        throw new Error("boom");
      }),
    ).rejects.toThrow("boom");
    const line = JSON.parse(readFileSync(join(dir, "audit.log"), "utf-8").trim());
    expect(line.result).toBe("err");
    expect(line.error).toBe("boom");
  });

  it("creates parent dir if needed", () => {
    const path = join(dir, "a", "b", "c", "audit.log");
    const log = new AuditLogger(path);
    log.write("x", {}, "ok", 1);
    expect(() => readFileSync(path)).not.toThrow();
  });
});
