"""Database connection helpers for the rule-engine application."""

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine using the configured database URL."""
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Set DATABASE_URL or pass a database URL")
    return create_engine(url, pool_pre_ping=True)