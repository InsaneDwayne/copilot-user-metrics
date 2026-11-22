"""Application configuration.

Every value comes from environment variables (or a ``.env`` file), grouped by
prefix: ``GITHUB_ORG`` -> ``settings.github.org``, ``API_DATABASE_URL`` ->
``settings.api.database_url`` and so on. Each process only needs the groups it
uses; the composition roots call the ``require_*`` helpers so a missing secret
fails at start-up with a clear message instead of at the first request.
"""

from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

from pydantic import BaseModel, BeforeValidator, Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class ConfigurationError(RuntimeError):
    pass


class GitHubSettings(BaseModel):
    org: str = Field(min_length=1, description="Organization login, e.g. acme-labs")
    api_url: str = "https://api.github.com"
    web_url: str = "https://github.com"
    api_version: str = "2026-03-10"
    timeout_seconds: float = 30.0

    # GitHub App: installation token for the sync worker (needs the private key).
    app_id: int | None = None
    app_private_key_path: Path | None = None
    # GitHub App: user authorization for sign-in (the API only needs these).
    app_client_id: str | None = None
    app_client_secret: SecretStr | None = None


class DatabaseSettings(BaseModel):
    """Owner connection, used for migrations only."""

    url: PostgresDsn | None = None
    api_role: str = "copilot_api"
    worker_role: str = "copilot_worker"


class ApiSettings(BaseModel):
    database_url: PostgresDsn
    # Base URL the browser uses to reach the app. In development that's the Vite
    # dev server, which proxies /api and /auth to FastAPI - so the session cookie
    # and the OAuth callback live on one origin. Its scheme decides the cookie's Secure flag.
    public_url: str = "http://localhost:5173"
    # Plain-HTTP mode: allow an http public URL on a host other than localhost (e.g. a test
    # box). Without TLS the session cookie and the OAuth code cross the network in clear text.
    allow_http: bool = False
    # Optional: serve the built SPA from FastAPI (single-container deploys).
    static_dir: Path | None = None
    pool_size: int = 5
    # Serve the interactive API docs (/docs, /redoc, /openapi.json). Off unless asked for: they
    # are a development aid and would show the API's shape to anyone who can reach the server.
    docs: bool = False

    @property
    def https(self) -> bool:
        return urlsplit(self.public_url).scheme == "https"

    def require_transport_security(self) -> None:
        """An ``https`` public URL, unless the browser talks to this machine or plain HTTP is allowed."""
        url = urlsplit(self.public_url)
        if url.scheme not in ("http", "https") or not url.hostname:
            raise ConfigurationError(f"API_PUBLIC_URL must be an http(s) URL, got {self.public_url!r}")
        if url.scheme == "http" and url.hostname not in _LOOPBACK_HOSTS and not self.allow_http:
            raise ConfigurationError(
                f"API_PUBLIC_URL {self.public_url!r} is plain HTTP: the session cookie and the OAuth code "
                "would cross the network unencrypted. Put a TLS-terminating reverse proxy in front and use "
                "an https URL, or set API_ALLOW_HTTP=true (e.g. for a test host)."
            )


_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_MIN_SECRET_LENGTH = 32


class SessionSettings(BaseModel):
    # Signs the session cookie, which carries the role (and thereby the database's RLS identity):
    # whoever knows it can mint an admin session.
    secret: SecretStr
    cookie_name: str = "copilot_session"
    # The role is only checked with GitHub at sign-in, so the session expiry is
    # what bounds how stale a role can get.
    max_age_hours: int = 4

    @field_validator("secret")
    @classmethod
    def _long_enough(cls, secret: SecretStr) -> SecretStr:
        if len(secret.get_secret_value()) < _MIN_SECRET_LENGTH:
            raise ValueError(
                f"SESSION_SECRET must be at least {_MIN_SECRET_LENGTH} characters; generate one with "
                'python3 -c "import secrets; print(secrets.token_hex(32))"'
            )
        return secret

    @property
    def max_age(self) -> timedelta:
        return timedelta(hours=self.max_age_hours)


def _comma_list(value: Any) -> Any:
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    return value


# A comma-separated env value ("a, b") rather than JSON.
TeamSlugs = Annotated[tuple[str, ...], NoDecode, BeforeValidator(_comma_list)]


class AccessSettings(BaseModel):
    """Who may open the admin console besides org owners (who are always admins).

    Checked with GitHub at sign-in only. Team slugs are teams of ``GITHUB_ORG`` (the part after
    ``/orgs/<org>/teams/`` in the URL); members of child teams count, pending invitations do not.
    """

    # ACCESS_ADMIN_TEAMS: members are admins, like org owners - all org data plus the Sync page.
    admin_teams: TeamSlugs = ()
    # ACCESS_ORG_READER_TEAMS: members are organization readers - all org data, read only, no Sync page.
    org_reader_teams: TeamSlugs = ()


class WorkerSettings(BaseModel):
    database_url: PostgresDsn
    concurrency: int = 1
    queue: str = "sync"


class SyncSettings(BaseModel):
    credits_cron: str = "*/20 * * * *"
    seats_cron: str = "0 * * * *"
    metrics_cron: str = "0 6 * * *"
    budgets_cron: str = "10 * * * *"
    # Re-queues jobs a stopped or crashed worker left running (see recover_stalled_jobs).
    recover_stalled_cron: str = "*/5 * * * *"
    # Drops the sync's own bookkeeping once it is older than history_retention_days: finished
    # runs (each job's latest success stays), handled admin requests, finished queue jobs.
    # The synced usage data is never pruned.
    prune_cron: str = "30 3 * * *"
    history_retention_days: int = Field(default=90, ge=7)
    # How many recent days each periodic run re-fetches (covers late corrections).
    credits_lookback_days: int = Field(default=2, ge=1)
    metrics_lookback_days: int = Field(default=3, ge=1)
    # GitHub's retention: ~24 months of billing, ~1 year of metrics. The worker fetches every
    # day in these windows it doesn't have yet when it starts (SYNC_CATCH_UP_ON_START), so the
    # first start loads all available history and later starts fill gaps such as downtime.
    backfill_credits_days: int = Field(default=730, ge=1)
    backfill_metrics_days: int = Field(default=365, ge=1)
    catch_up_on_start: bool = True
    # GitHub calls a credit sync runs at once (shared by all jobs of one worker process).
    parallel_requests: int = Field(default=8, ge=1)
    # The UI shows a "may be behind" banner when credits haven't synced for this long.
    stale_after_hours: int = 3
    # A job that failed this many times since its last success is logged as an error and
    # marks the worker container unhealthy, until it succeeds again.
    alert_after_failures: int = Field(default=3, ge=1)


_ENV = SettingsConfigDict(
    env_file=(".env", "../.devcontainer/.env"),
    env_nested_delimiter="_",
    env_nested_max_split=1,
    extra="ignore",
)


class MigrationSettings(BaseSettings):
    """Only what Alembic needs: the owner connection and the role names to grant to."""

    model_config = _ENV
    database: DatabaseSettings = DatabaseSettings()

    def require_owner_database_url(self) -> str:
        if self.database.url is None:
            raise ConfigurationError("DATABASE_URL (owner role) is required for migrations")
        return str(self.database.url)


class Settings(BaseSettings):
    model_config = _ENV

    log_level: str = "INFO"
    github: GitHubSettings
    api: ApiSettings | None = None
    session: SessionSettings | None = None
    worker: WorkerSettings | None = None
    sync: SyncSettings = SyncSettings()
    access: AccessSettings = AccessSettings()

    def require_api(self) -> tuple[ApiSettings, SessionSettings]:
        if self.api is None or self.session is None:
            raise ConfigurationError("API_DATABASE_URL and SESSION_SECRET must be set for the API")
        if not (self.github.app_client_id and self.github.app_client_secret):
            raise ConfigurationError("GITHUB_APP_CLIENT_ID and GITHUB_APP_CLIENT_SECRET are required for sign-in")
        self.api.require_transport_security()
        return self.api, self.session

    def require_worker(self) -> WorkerSettings:
        if self.worker is None:
            raise ConfigurationError("WORKER_DATABASE_URL must be set for the sync worker")
        return self.worker

    def require_app_credentials(self) -> tuple[int, str]:
        g = self.github
        if g.app_id is None or g.app_private_key_path is None:
            raise ConfigurationError("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY_PATH are required for syncing")
        return g.app_id, g.app_private_key_path.read_text(encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # populated from the environment
