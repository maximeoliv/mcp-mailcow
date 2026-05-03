/**
 * Test selected admin handlers using undici's MockAgent.
 */
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MockAgent, setGlobalDispatcher } from "undici";
import * as h from "../src/admin/handlers.js";
import { AuditLogger } from "../src/audit.js";

const cfg = {
  baseUrl: "https://mail.example.com",
  apiKey: "test-key",
  tlsVerify: true,
  auditLog: "/tmp/handlers-test-audit.log",
};

let agent: MockAgent;
beforeEach(() => {
  agent = new MockAgent();
  agent.disableNetConnect();
  setGlobalDispatcher(agent);
});
afterEach(async () => {
  await agent.close();
});

function makeCtx() {
  return h.makeContext(cfg, new AuditLogger(cfg.auditLog));
}

describe("admin handlers", () => {
  it("domain_list returns the list", async () => {
    agent
      .get("https://mail.example.com")
      .intercept({ path: "/api/v1/get/domain/all", method: "GET" })
      .reply(200, [{ domain_name: "a.com" }, { domain_name: "b.com" }]);

    const handler = h.domain_list(makeCtx());
    const result = (await handler({})) as Array<{ domain_name: string }>;
    expect(result).toHaveLength(2);
    expect(result[0].domain_name).toBe("a.com");
  });

  it("mailbox_create sends correct payload", async () => {
    let captured: Record<string, unknown> | undefined;
    agent
      .get("https://mail.example.com")
      .intercept({ path: "/api/v1/add/mailbox", method: "POST" })
      .reply((opts) => {
        captured = JSON.parse(opts.body as string);
        return { statusCode: 200, data: [{ type: "success" }] };
      });

    const handler = h.mailbox_create(makeCtx());
    await handler({
      email: "test@a.com",
      name: "Test",
      quota_mb: 500,
      password: "Secret123",
    });
    expect(captured?.local_part).toBe("test");
    expect(captured?.domain).toBe("a.com");
    expect(captured?.quota).toBe(500);
  });

  it("mailbox_delete requires confirm", async () => {
    const handler = h.mailbox_delete(makeCtx());
    await expect(handler({ email: "x@a.com" })).rejects.toThrow(/confirm/);
  });

  it("app_password_list masks hashes", async () => {
    agent
      .get("https://mail.example.com")
      .intercept({ path: "/api/v1/get/app-passwd/all/x@a.com", method: "GET" })
      .reply(200, [{ id: 1, name: "n8n", password: "{BLF-CRYPT}$2y$..." }]);

    const handler = h.app_password_list(makeCtx());
    const result = (await handler({ email: "x@a.com" })) as Array<{ password: string }>;
    expect(result[0].password).toBe("***");
  });

  it("mailcow error response is converted to thrown error", async () => {
    agent
      .get("https://mail.example.com")
      .intercept({ path: "/api/v1/add/mailbox", method: "POST" })
      .reply(200, [{ type: "danger", msg: "password_complexity" }]);

    const handler = h.mailbox_create(makeCtx());
    await expect(
      handler({ email: "x@a.com", name: "X", password: "weak" }),
    ).rejects.toThrow(/password_complexity/);
  });
});
