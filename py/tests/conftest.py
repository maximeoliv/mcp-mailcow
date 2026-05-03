"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

# Add the package source to sys.path so tests can `import mcp_mailcow`.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
