"""Routes that belong to no module: public SPA config and the health check."""

import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from copilot_metrics.shared.kernel import Frozen

log = logging.getLogger(__name__)


class PublicConfig(Frozen):
    """Non-secret settings the SPA needs before sign-in."""

    org: str
    session_max_age_hours: int


def build_system_router(config: PublicConfig, ping_database: Callable[[], Awaitable[None]]) -> APIRouter:
    router = APIRouter()

    @router.get("/api/config", tags=["public"])
    def public_config() -> PublicConfig:
        return config

    @router.get("/healthz", include_in_schema=False)
    async def health() -> PlainTextResponse:
        """Up and able to reach the database; 503 otherwise (the detail goes to the log only)."""
        try:
            await ping_database()
        except Exception:
            log.exception("health check: database unreachable")
            return PlainTextResponse("database unreachable", status_code=503)
        return PlainTextResponse("ok")

    return router
