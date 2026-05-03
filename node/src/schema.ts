/**
 * Loads tools-schema.yaml and converts tool defs to MCP Tool format.
 * Mirrors py/src/mcp_mailcow/schema.py.
 */
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import yaml from "yaml";

const __dirname = dirname(fileURLToPath(import.meta.url));

export type Mode = "user" | "admin";

export interface ParamDef {
  type: string;
  description?: string;
  required?: boolean;
  default?: unknown;
  enum?: string[];
  items?: unknown;
  format?: string;
  secret?: boolean;
}

export interface ToolDef {
  name: string;
  mode: Mode;
  category?: string;
  description: string;
  params?: Record<string, ParamDef>;
}

export interface Schema {
  version: string;
  modes: Record<Mode, { description: string }>;
  tools: ToolDef[];
}

export async function loadSchema(): Promise<Schema> {
  // The schema is shipped at the package root (next to dist/).
  const candidates = [
    join(__dirname, "..", "tools-schema.yaml"),
    join(__dirname, "..", "..", "tools-schema.yaml"),
  ];
  for (const path of candidates) {
    try {
      const content = await readFile(path, "utf-8");
      return yaml.parse(content) as Schema;
    } catch {
      // try next
    }
  }
  throw new Error("tools-schema.yaml not found");
}

export function toolsForMode(schema: Schema, mode: Mode): ToolDef[] {
  return schema.tools.filter((t) => t.mode === mode);
}

export function toMcpTool(tool: ToolDef): {
  name: string;
  description: string;
  inputSchema: {
    type: "object";
    properties: Record<string, unknown>;
    required?: string[];
  };
} {
  const properties: Record<string, unknown> = {};
  const required: string[] = [];

  for (const [pname, pdef] of Object.entries(tool.params || {})) {
    const prop: Record<string, unknown> = { type: pdef.type };
    if (pdef.description) prop.description = pdef.description;
    if (pdef.default !== undefined) prop.default = pdef.default;
    if (pdef.enum) prop.enum = pdef.enum;
    if (pdef.items) prop.items = pdef.items;
    if (pdef.format) prop.format = pdef.format;
    properties[pname] = prop;
    if (pdef.required) required.push(pname);
  }

  return {
    name: tool.name,
    description: (tool.description || "").trim(),
    inputSchema: {
      type: "object",
      properties,
      ...(required.length > 0 ? { required } : {}),
    },
  };
}
