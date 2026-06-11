/**
 * Verify that the user/admin registries expose exactly the tools defined in
 * tools-schema.yaml. Mirror of py/tests/test_registry.py.
 */
import { describe, expect, it } from "vitest";
import { AuditLogger } from "../src/audit.js";
import { buildAdminRegistry } from "../src/admin/registry.js";
import { buildUserRegistry } from "../src/user/registry.js";
import { loadSchema } from "../src/schema.js";

const userCfg = {
  host: "mail.example.com",
  mailUser: "x@example.com",
  mailPass: "pw",
  imapPort: 993,
  smtpPort: 587,
  tlsVerify: true,
  auditLog: "/tmp/test-audit.log",
};

const adminCfg = {
  baseUrl: "https://mail.example.com",
  apiKey: "key",
  tlsVerify: true,
  auditLog: "/tmp/test-audit.log",
};

describe("registry", () => {
  it("user registry exposes all user tools from schema", async () => {
    const schema = await loadSchema();
    const expected = new Set(
      schema.tools.filter((t) => t.mode === "user").map((t) => t.name),
    );
    const { registry } = buildUserRegistry(userCfg, new AuditLogger(userCfg.auditLog));
    const actual = new Set(Object.keys(registry));
    const missing = [...expected].filter((n) => !actual.has(n));
    const extra = [...actual].filter((n) => !expected.has(n));
    expect(missing, `missing user tools: ${missing.join(", ")}`).toEqual([]);
    expect(extra, `extra user tools: ${extra.join(", ")}`).toEqual([]);
  });

  it("admin registry exposes all admin tools from schema", async () => {
    const schema = await loadSchema();
    const expected = new Set(
      schema.tools.filter((t) => t.mode === "admin").map((t) => t.name),
    );
    const { registry } = buildAdminRegistry(adminCfg, new AuditLogger(adminCfg.auditLog));
    const actual = new Set(Object.keys(registry));
    const missing = [...expected].filter((n) => !actual.has(n));
    const extra = [...actual].filter((n) => !expected.has(n));
    expect(missing, `missing admin tools: ${missing.join(", ")}`).toEqual([]);
    expect(extra, `extra admin tools: ${extra.join(", ")}`).toEqual([]);
  });
});
