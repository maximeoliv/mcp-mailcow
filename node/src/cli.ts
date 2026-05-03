#!/usr/bin/env node
/**
 * Entry point: `mcp-mailcow --mode user|admin`
 */
import { runServer } from "./server.js";

function main() {
  const args = process.argv.slice(2);
  let mode: "user" | "admin" | undefined;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--mode" && i + 1 < args.length) {
      const m = args[i + 1];
      if (m === "user" || m === "admin") {
        mode = m;
      } else {
        console.error(`error: invalid mode '${m}', expected 'user' or 'admin'`);
        process.exit(2);
      }
      i++;
    } else if (args[i] === "--version" || args[i] === "-v") {
      console.log("mcp-mailcow 1.0.0");
      process.exit(0);
    } else if (args[i] === "--help" || args[i] === "-h") {
      console.log("Usage: mcp-mailcow --mode <user|admin>");
      process.exit(0);
    }
  }

  if (!mode) {
    console.error("error: --mode is required (user or admin)");
    process.exit(2);
  }

  runServer(mode).catch((err) => {
    console.error("server error:", err);
    process.exit(1);
  });
}

main();
