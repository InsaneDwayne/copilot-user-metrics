"""Composition root of the dashboard API. Holds no GitHub App key - only the
OAuth client credentials for sign-in - and connects as the read-only DB role."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from functools import partial

from fastapi import FastAPI

from copilot_metrics.identity.adapters.inbound.http.dependencies import Guards
from copilot_metrics.identity.adapters.inbound.http.router import build_auth_router
from copilot_metrics.identity.adapters.outbound.github.identity_provider import GitHubIdentityProvider
from copilot_metrics.identity.adapters.outbound.postgres.seat_directory import PostgresSeatDirectory
from copilot_metrics.identity.domain import AccessPolicy
from copilot_metrics.identity.ports import IdentityProvider
from copilot_metrics.identity.service import SignInService
from copilot_metrics.settings import Settings, get_settings
from copilot_metrics.shared.adapters.inbound.http.error_handlers import install_error_handlers
from copilot_metrics.shared.adapters.inbound.http.middleware import install_session_middleware
from copilot_metrics.shared.adapters.inbound.http.router import PublicConfig, build_system_router
from copilot_metrics.shared.adapters.inbound.http.spa import mount_spa
from copilot_metrics.shared.adapters.outbound.github.http_client import github_client
from copilot_metrics.shared.adapters.outbound.postgres.engine import create_engine, ping
from copilot_metrics.shared.kernel import Clock, SystemClock
from copilot_metrics.sync.adapters.inbound.http.router import build_sync_router
from copilot_metrics.sync.adapters.outbound.postgres.requests import PostgresSyncRequests
from copilot_metrics.sync.service import SyncControlService
from copilot_metrics.usage.adapters.inbound.http.router import build_usage_router
from copilot_metrics.usage.adapters.outbound.postgres.repository import PostgresUsageReader
from copilot_metrics.usage.service import UsageService


def create_app(
    settings: Settings | None = None,
    clock: Clock | None = None,
    identity_provider: IdentityProvider | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    clock = clock or SystemClock()
    api_settings, session_settings = settings.require_api()
    logging.basicConfig(level=settings.log_level)

    engine = create_engine(api_settings.database_url, pool_size=api_settings.pool_size)
    github = github_client(settings.github)
    seats = PostgresSeatDirectory(engine)
    guards = Guards(session_settings, seats, clock)
    policy = AccessPolicy.model_validate(settings.access.model_dump())
    sign_in = SignInService(identity_provider or GitHubIdentityProvider(settings.github, github), clock, policy)
    usage = UsageService(
        PostgresUsageReader(engine),
        clock,
        stale_after=timedelta(hours=settings.sync.stale_after_hours),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        await github.aclose()
        await engine.dispose()

    app = FastAPI(
        title="Copilot Usage API",
        lifespan=lifespan,
        openapi_url="/openapi.json" if api_settings.docs else None,  # without it /docs and /redoc are off too
    )
    install_error_handlers(app)
    install_session_middleware(app, session_settings, https=api_settings.https)

    public_config = PublicConfig(org=settings.github.org, session_max_age_hours=session_settings.max_age_hours)
    app.include_router(build_system_router(public_config, partial(ping, engine)))
    app.include_router(build_auth_router(service=sign_in, guards=guards, public_url=api_settings.public_url))
    app.include_router(
        build_usage_router(
            service=usage,
            seat_holder=guards.seat_holder,
            org_member=guards.org_member,
            org_reader=guards.org_reader,
            clock=clock,
        )
    )

    app.include_router(build_sync_router(service=SyncControlService(PostgresSyncRequests(engine)), admin=guards.admin))

    if api_settings.static_dir:
        mount_spa(app, api_settings.static_dir)
    return app
