"""Engine creation and the row-level-security scope."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from pydantic import PostgresDsn
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from copilot_metrics.shared.kernel import Viewer


def sqlalchemy_url(dsn: PostgresDsn | str) -> str:
    """postgresql://... -> postgresql+psycopg://... (psycopg 3, sync and async)."""
    url = str(dsn)
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    raise ValueError(f"not a PostgreSQL URL: {url.split('@')[-1]}")


def create_engine(dsn: PostgresDsn | str, pool_size: int = 5) -> AsyncEngine:
    return create_async_engine(sqlalchemy_url(dsn), pool_size=pool_size, pool_pre_ping=True)


@asynccontextmanager
async def viewer_scope(engine: AsyncEngine, viewer: Viewer) -> AsyncGenerator[AsyncConnection]:
    """A transaction in which Postgres row-level security sees ``viewer``.

    ``set_config(..., is_local => true)`` lasts until the transaction ends, so a
    pooled connection never carries one person's identity into the next request.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.user_id', :user_id, true), set_config('app.role', :role, true)"),
            {"user_id": str(viewer.user_id), "role": viewer.role.value},
        )
        yield conn


async def ping(engine: AsyncEngine) -> None:
    """Raise unless the database answers a trivial query."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
