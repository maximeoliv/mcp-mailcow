"""Entry point: `mcp-mailcow --mode user|admin`."""

from __future__ import annotations

import argparse
import asyncio
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from typing import NoReturn

from .server import run_server


def _version_string() -> str:
    """Read the installed package version. Falls back to 'dev' when running
    from a source checkout that hasn't been installed (e.g. directly via
    `python -m mcp_mailcow`)."""
    try:
        return _pkg_version("mcp-mailcow")
    except PackageNotFoundError:
        return "dev"


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
        version=f"%(prog)s {_version_string()}",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_server(mode=args.mode))
    except KeyboardInterrupt:
        sys.exit(0)
    sys.exit(0)


if __name__ == "__main__":
    main()
