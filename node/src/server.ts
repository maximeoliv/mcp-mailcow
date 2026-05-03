/**
 * MCP server entry. Loads the schema, builds the registry for the requested
 * mode, and exposes it over stdio.
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { loadSchema, toolsForMode, toMcpTool } from "./schema.js";
import { loadAdminConfig, loadUserConfig } from "./config.js";
import { AuditLogger } from "./audit.js";
import { ConfirmationRequired } from "./exceptions.js";
import { buildAdminRegistry } from "./admin/registry.js";
import { buildUserRegistry } from "./user/registry.js";

export async function runServer(mode: "user" | "admin"): Promise<void> {
  const schema = await loadSchema();
  const tools = toolsForMode(schema, mode);

  let registry: Record<string, (args: unknown) => Promise<unknown>>;
  if (mode === "user") {
    const config = loadUserConfig();
    const audit = new AuditLogger(config.auditLog);
    registry = buildUserRegistry(config, audit);
  } else {
    const config = loadAdminConfig();
    const audit = new AuditLogger(config.auditLog);
    registry = buildAdminRegistry(config, audit);
  }

  const server = new Server(
    { name: "mcp-mailcow", version: "1.0.0" },
    { capabilities: { tools: {} } },
  );

  // Tool listing
  server.setRequestHandler(
    { method: "tools/list" } as never,
    async () => ({ tools: tools.map(toMcpTool) }),
  );

  // Tool invocation
  server.setRequestHandler(
    { method: "tools/call" } as never,
    async (req: { params: { name: string; arguments?: unknown } }) => {
      const { name, arguments: args } = req.params;
      if (!(name in registry)) {
        return {
          content: [{ type: "text", text: `error: unknown tool '${name}'` }],
        };
      }
      try {
        const result = await registry[name](args || {});
        const text =
          typeof result === "string" ? result : JSON.stringify(result, null, 2);
        return { content: [{ type: "text", text }] };
      } catch (err) {
        if (err instanceof ConfirmationRequired) {
          return {
            content: [
              {
                type: "text",
                text: `⚠ ${err.message}\nAdd \`confirm: true\` to the arguments and retry.`,
              },
            ],
          };
        }
        const msg = err instanceof Error ? err.message : String(err);
        return { content: [{ type: "text", text: `error: ${msg}` }] };
      }
    },
  );

  const transport = new StdioServerTransport();
  await server.connect(transport);
}
