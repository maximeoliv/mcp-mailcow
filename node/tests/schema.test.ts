/**
 * Vitest smoke test mirroring the Python schema tests.
 */
import { describe, expect, it } from "vitest";
import { loadSchema, toMcpTool, toolsForMode } from "../src/schema.js";

describe("schema", () => {
  it("loads with version 1.0", async () => {
    const s = await loadSchema();
    expect(s.version).toBe("1.0");
  });

  it("has user and admin modes", async () => {
    const s = await loadSchema();
    expect(s.modes.user).toBeDefined();
    expect(s.modes.admin).toBeDefined();
  });

  it("all tools have names and modes", async () => {
    const s = await loadSchema();
    for (const t of s.tools) {
      expect(t.name).toBeTruthy();
      expect(["user", "admin"]).toContain(t.mode);
    }
  });

  it("no duplicate tool names", async () => {
    const s = await loadSchema();
    const names = s.tools.map((t) => t.name);
    expect(new Set(names).size).toBe(names.length);
  });

  it("filters tools by mode", async () => {
    const s = await loadSchema();
    const userTools = toolsForMode(s, "user");
    const adminTools = toolsForMode(s, "admin");
    expect(userTools.length).toBeGreaterThan(0);
    expect(adminTools.length).toBeGreaterThan(0);
    expect(userTools.length + adminTools.length).toBe(s.tools.length);
  });

  it("converts a tool to MCP format", async () => {
    const s = await loadSchema();
    const sample = s.tools[0];
    const mcp = toMcpTool(sample);
    expect(mcp.name).toBe(sample.name);
    expect(mcp.inputSchema.type).toBe("object");
  });
});
