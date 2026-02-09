"""Shared API dependencies — single import point for all routers.

Re-exports database session and authentication dependencies so that router
modules can import everything they need from one place::

    from app.api.deps import get_db, get_current_active_user
"""

from app.auth.dependencies import (
    get_current_active_user,
    get_current_user,
    get_optional_user,
)
from app.database import get_db

__all__ = [
    "get_db",
    "get_current_user",
    "get_current_active_user",
    "get_optional_user",
]
