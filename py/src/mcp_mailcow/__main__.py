"""Entry point: `mcp-mailcow --mode user|admin`."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import NoReturn

from .server import run_server


def main() -> NoReturn:
    parser = argparse.ArgumentParser(
        prog="mcp-mailcow",
        description="MCP server for Mailcow (mail + admin)",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["user", "admin"],
        help="user: IMAP/SMTP mailbox operations | admin: Mailcow REST API operations",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_server(mode=args.mode))
    except KeyboardInterrupt:
        sys.exit(0)
    sys.exit(0)


if __name__ == "__main__":
    main()
