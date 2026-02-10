"""MCP Server for VillaOps AI — Streamable HTTP transport on port 8001.

Runs as a standalone service. Provides tools for searching bookings
and looking up guest information.

Uses the FastMCP high-level API with streamable_http_app() for
Streamable HTTP transport (single /mcp endpoint, recommended over
deprecated SSE transport since MCP spec 2025-03-26).
"""

import contextlib
import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
import uvicorn

from app.mcp import mcp, set_session_factory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database — separate engine for the MCP process
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://villa:villa_secret@postgres:5432/villa_ops",
)

mcp_engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
mcp_session_factory = async_sessionmaker(mcp_engine, class_=AsyncSession, expire_on_commit=False)

# Make session factory available to tool modules
set_session_factory(mcp_session_factory)

# ---------------------------------------------------------------------------
# Import tool modules — triggers @mcp.tool() registration
# ---------------------------------------------------------------------------
import app.mcp.tools.booking_tools  # noqa: F401, E402
import app.mcp.tools.guest_tools  # noqa: F401, E402


# ---------------------------------------------------------------------------
# Health check endpoint (not part of MCP, just for Docker healthcheck)
# ---------------------------------------------------------------------------
async def health(request):
    return JSONResponse({"status": "healthy", "service": "villaops-mcp"})


# ---------------------------------------------------------------------------
# Starlette ASGI app — mounts MCP Streamable HTTP app + health check
# ---------------------------------------------------------------------------
# Create the MCP ASGI sub-app first so session_manager is initialized
mcp_http_app = mcp.streamable_http_app()


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    """Manage MCP session manager lifecycle."""
    async with mcp.session_manager.run():
        logger.info("MCP server started (Streamable HTTP transport)")
        yield
        logger.info("MCP server shutting down")


app = Starlette(
    routes=[
        Route("/health", health),
        Mount("/", app=mcp_http_app),
    ],
    lifespan=lifespan,
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
