/**
 * Custom errors raised by MCP tools.
 * Mirror of py/src/mcp_mailcow/exceptions.py.
 */

/**
 * Thrown when a destructive operation is invoked without an explicit
 * `confirm: true` argument. The MCP server catches this separately and
 * surfaces a clear, actionable message to the calling agent rather than
 * treating it as a generic error.
 */
export class ConfirmationRequired extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfirmationRequired";
  }
}
