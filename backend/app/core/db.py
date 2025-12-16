"""
Database engine re-export for convenience.

This module re-exports the async engine from app.db.session for use in tasks and tests.
"""

from app.db.session import engine

__all__ = ["engine"]
