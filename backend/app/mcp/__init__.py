"""MCP package — shared MCPServer instance and session factory."""

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

# Shared MCPServer instance — tools register on this via @mcp.tool()
mcp = MCPServer(
    name="villaops-mcp",
    instructions="VillaOps AI MCP server. Provides tools for managing bookings, guests, and properties for Bali villa/hotel property managers.",
)

# Transport security for the Streamable HTTP app (passed to streamable_http_app() in server.py)
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=["localhost:8001", "mcp:8001", "127.0.0.1:8001", "mcp.villaops.local:8001"],
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
