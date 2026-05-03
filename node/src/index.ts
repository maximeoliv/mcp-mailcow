/**
 * Public API surface for programmatic use (alternative to CLI).
 * Most users will run this via the bin entry point.
 */
export { runServer } from "./server.js";
export type { Schema, ToolDef, Mode } from "./schema.js";
export { loadSchema, toolsForMode, toMcpTool } from "./schema.js";
