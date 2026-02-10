"""MCP package — shared FastMCP instance and session factory."""

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# Shared FastMCP instance — tools register on this via @mcp.tool()
mcp = FastMCP(
    name="villaops-mcp",
    instructions="VillaOps AI MCP server. Provides tools for searching bookings and looking up guest information for Bali villa/hotel property managers.",
    port=8001,
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["localhost:8001", "mcp:8001", "127.0.0.1:8001"],
    ),
)

# Session factory — set by server.py at startup, used by tool modules
_session_factory = None


def set_session_factory(factory):
    global _session_factory
    _session_factory = factory


def get_session_factory():
    if _session_factory is None:
        raise RuntimeError("MCP session factory not initialized. Is server.py running?")
    return _session_factory
