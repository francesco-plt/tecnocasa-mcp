"""Tecnocasa MCP server.

Public, read-only access to Tecnocasa listings across Italy, including the
franchise microsites. No API key required.
"""

from __future__ import annotations

from .client import TecnocasaClient, TecnocasaError

__version__ = "0.1.0"

__all__ = ["TecnocasaClient", "TecnocasaError", "__version__"]
