"""Alembic environment. Runs as the owner role (DATABASE_URL)."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from copilot_metrics.settings import MigrationSettings
from copilot_metrics.shared.adapters.outbound.postgres.engine import sqlalchemy_url
from copilot_metrics.shared.adapters.outbound.postgres.tables import metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or sqlalchemy_url(MigrationSettings().require_owner_database_url())


def include_object(obj: object, name: str | None, type_: str, reflected: bool, compare_to: object) -> bool:
    """procrastinate's tables come from its own SQL (in migration 0001), not from our metadata."""
    return not (name or "").startswith("procrastinate")


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata, include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
