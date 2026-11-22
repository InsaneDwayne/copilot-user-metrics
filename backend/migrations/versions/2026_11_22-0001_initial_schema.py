"""initial schema: usage tables, grants, row-level security and the job queue

The API role may only read (plus add run/stop requests); the worker role is the only
writer. Per-person tables carry RLS policies keyed on the numeric GitHub user id that
the API sets per transaction (``app.user_id`` / ``app.role``): admins and organization
readers see every member's rows, everyone else only their own.

The procrastinate job queue schema is owned by the migration role and used by the
worker. Future procrastinate upgrades ship SQL migrations in
``procrastinate/sql/migrations``; add them as new Alembic revisions
(see https://procrastinate.readthedocs.io/en/stable/howto/production/migrations.html).

Revision ID: 0001
Revises:
Create Date: 2026-11-22 14:40:11.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from procrastinate.schema import SchemaManager
from sqlalchemy.dialects import postgresql

from copilot_metrics.settings import MigrationSettings

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

Money = sa.Numeric(precision=14, scale=4)

# Frozen at this revision (not imported from the app), so the migration never changes under it.
PER_USER_TABLES = ("seat", "credit_usage", "user_activity", "user_team_day", "user_budget")
ORG_TABLES = (
    "org_seat_summary",
    "org_credit_day",
    "org_activity_day",
    "org_budget",
    "org_seat_cost",
    "sync_run",
    "sync_day",
)

_USER_ID = "nullif(current_setting('app.user_id', true), '')::bigint"
_READS_ORG = "current_setting('app.role', true) IN ('admin', 'org_reader')"
_IS_ADMIN = "current_setting('app.role', true) = 'admin'"

# GitHub's org-wide daily report: counts it may leave out, hence nullable.
_ORG_ACTIVITY_COUNTS = (
    "daily_active_users",
    "weekly_active_users",
    "monthly_active_users",
    "missing_telemetry_users",
    "below_minimum_users",
    "prs_created",
    "prs_created_by_copilot",
    "prs_reviewed",
    "prs_reviewed_by_copilot",
    "prs_merged",
    "prs_merged_created_by_copilot",
    "pr_suggestions",
    "pr_applied_suggestions",
    "pr_copilot_suggestions",
    "pr_copilot_applied_suggestions",
)


def upgrade() -> None:
    _create_tables()
    _grant_and_protect()
    _create_job_queue()


def downgrade() -> None:
    _drop_job_queue()
    for table in (*PER_USER_TABLES, *ORG_TABLES, "sync_request"):
        op.drop_table(table)


# ---------------------------------------------------------------- tables


def _create_tables() -> None:
    # Seats and per-person usage
    op.create_table(
        "seat",
        sa.Column("user_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("login", sa.Text(), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_cancellation_date", sa.Date(), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_editor", sa.Text(), nullable=True),
        sa.Column("plan_type", sa.Text(), nullable=True),
        sa.Column("assigning_team", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "credit_usage",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("login", sa.Text(), nullable=False),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("gross_qty", Money, nullable=False),
        sa.Column("gross_usd", Money, nullable=False),
        sa.Column("discount_usd", Money, nullable=False),
        sa.Column("net_qty", Money, nullable=False),
        sa.Column("net_usd", Money, nullable=False),
        sa.PrimaryKeyConstraint("user_id", "day", "model"),
    )
    op.create_table(
        "user_activity",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("login", sa.Text(), nullable=False),
        sa.Column("prompts", sa.Integer(), nullable=False),
        sa.Column("generations", sa.Integer(), nullable=False),
        sa.Column("acceptances", sa.Integer(), nullable=False),
        sa.Column("loc_suggested", sa.Integer(), nullable=False),
        sa.Column("loc_added", sa.Integer(), nullable=False),
        sa.Column("used_agent", sa.Boolean(), nullable=False),
        sa.Column("used_chat", sa.Boolean(), nullable=False),
        sa.Column("used_cli", sa.Boolean(), nullable=False),
        sa.Column("used_cloud_agent", sa.Boolean(), nullable=False),
        sa.Column("used_app", sa.Boolean(), nullable=False),
        sa.Column("used_review", sa.Boolean(), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "day"),
    )
    # The admin pages read one period across everyone, but these keys start with user_id.
    # user_team_day needs no such index: it is looked up by its key or read up to a day.
    op.create_index("ix_credit_usage_day", "credit_usage", ["day"])
    op.create_index("ix_user_activity_day", "user_activity", ["day"])
    op.create_table(
        "user_team_day",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("team_slug", sa.Text(), nullable=False),
        sa.Column("login", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "day", "team_slug"),
    )
    op.create_table(
        "user_budget",
        sa.Column("user_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("login", sa.Text(), nullable=False),
        sa.Column("budget_id", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("sku", sa.Text(), nullable=False),
        sa.Column("amount_usd", Money, nullable=False),
        sa.Column("consumed_usd", Money, nullable=False),
        sa.Column("prevent_further_usage", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Org totals
    op.create_table(
        "org_seat_summary",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("added_this_cycle", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pending_invitation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pending_cancellation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active_this_cycle", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inactive_this_cycle", sa.Integer(), server_default="0", nullable=False),
        sa.Column("plan_type", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "org_credit_day",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("gross_qty", Money, nullable=False),
        sa.Column("gross_usd", Money, nullable=False),
        sa.Column("discount_usd", Money, nullable=False),
        sa.Column("net_qty", Money, nullable=False),
        sa.Column("net_usd", Money, nullable=False),
        sa.PrimaryKeyConstraint("day", "model"),
    )
    op.create_table(
        "org_activity_day",
        sa.Column("day", sa.Date(), nullable=False),
        *(sa.Column(name, sa.Integer(), nullable=True) for name in _ORG_ACTIVITY_COUNTS),
        sa.Column("median_minutes_to_merge", sa.Float(), nullable=True),
        sa.Column("median_minutes_to_merge_copilot", sa.Float(), nullable=True),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("day"),
    )
    op.create_table(
        "org_budget",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("entity_name", sa.Text(), nullable=True),
        sa.Column("sku", sa.Text(), nullable=False),
        sa.Column("budget_type", sa.Text(), nullable=True),
        sa.Column("amount_usd", Money, nullable=False),
        sa.Column("consumed_usd", Money, nullable=False),
        sa.Column("prevent_further_usage", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "org_seat_cost",
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("seats", Money, nullable=False),
        sa.Column("price_per_seat_usd", Money, nullable=False),
        sa.Column("gross_usd", Money, nullable=False),
        sa.Column("net_usd", Money, nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("month"),
    )

    # Operations
    op.create_table(
        "sync_run",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("job", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sync_run_job"), "sync_run", ["job"], unique=False)
    # Which days the worker has synced, for its startup catch-up.
    op.create_table(
        "sync_day",
        sa.Column("job", sa.Text(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("job", "day"),
    )
    # Run/stop requests from the admin console: the API stays out of the job queue and only
    # adds a request; the worker listens for them and applies them.
    op.create_table(
        "sync_request",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("admin_user_id", sa.BigInteger(), nullable=False),
        sa.Column("admin_login", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


# ---------------------------------------------------------------- grants and row-level security


def _roles() -> tuple[str, str]:
    roles = MigrationSettings().database
    return _ident(roles.api_role), _ident(roles.worker_role)


def _grant_and_protect() -> None:
    api, worker = _roles()
    # Org-wide tables have no row-level security: the API's guards serve them to admins and
    # organization readers only.
    tables = ", ".join((*PER_USER_TABLES, *ORG_TABLES))
    op.execute(f"GRANT SELECT ON {tables} TO {api}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tables} TO {worker}")

    for table in PER_USER_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY own_rows ON {table} FOR SELECT TO {api} USING ({_READS_ORG} OR user_id = {_USER_ID})"
        )
        op.execute(f"CREATE POLICY sync_writes ON {table} TO {worker} USING (true) WITH CHECK (true)")

    # Run/stop requests are admin-only (not organization readers), and always in the admin's own name.
    # The worker applies them, and prunes handled ones after SYNC_HISTORY_RETENTION_DAYS.
    op.execute(f"GRANT SELECT, INSERT ON sync_request TO {api}")
    op.execute(f"GRANT SELECT, UPDATE, DELETE ON sync_request TO {worker}")
    op.execute("ALTER TABLE sync_request ENABLE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY admin_reads ON sync_request FOR SELECT TO {api} USING ({_IS_ADMIN})")
    op.execute(
        f"""CREATE POLICY admin_requests_own ON sync_request FOR INSERT TO {api} WITH CHECK (
            {_IS_ADMIN} AND admin_user_id = {_USER_ID})"""
    )
    op.execute(f"CREATE POLICY worker_applies ON sync_request TO {worker} USING (true) WITH CHECK (true)")


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


# ---------------------------------------------------------------- procrastinate job queue


def _create_job_queue() -> None:
    # Run through the raw DBAPI cursor: the schema is many statements and contains
    # "%" and ":" which SQLAlchemy's text() would otherwise try to interpret.
    dbapi = op.get_bind().connection.dbapi_connection
    with dbapi.cursor() as cursor:
        cursor.execute(SchemaManager.get_schema())

    api, worker = _roles()
    op.execute(f"""
        DO $$
        DECLARE t text;
        BEGIN
            FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'procrastinate%' LOOP
                EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO {worker}', t);
            END LOOP;
            -- Every sequence but sync_request's: the worker never adds run/stop requests.
            FOR t IN SELECT sequencename FROM pg_sequences
                     WHERE schemaname = 'public' AND sequencename <> 'sync_request_id_seq' LOOP
                EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE public.%I TO {worker}', t);
            END LOOP;
        END $$""")
    # The Sync page shows how many jobs wait and run; reading the queue never changes it.
    op.execute(f"GRANT SELECT ON procrastinate_jobs TO {api}")


def _drop_job_queue() -> None:
    op.execute("""
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'procrastinate%' LOOP
                EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.tablename);
            END LOOP;
            FOR r IN SELECT p.oid::regprocedure AS sig FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                     WHERE n.nspname = 'public' AND p.proname LIKE 'procrastinate%' LOOP
                EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.sig);
            END LOOP;
            FOR r IN SELECT t.typname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                     WHERE n.nspname = 'public' AND t.typname LIKE 'procrastinate%' AND t.typtype IN ('e', 'c') LOOP
                EXECUTE format('DROP TYPE IF EXISTS public.%I CASCADE', r.typname);
            END LOOP;
        END $$""")
