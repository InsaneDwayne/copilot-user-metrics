"""Database schema (SQLAlchemy Core). Alembic migrations are written against it.

Per-person tables are keyed on the numeric GitHub ``user_id`` (logins can be
renamed) and protected by row-level security - see the initial migration.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

Money = Numeric(14, 4)
Quantity = Numeric(14, 4)

seat = Table(
    "seat",
    metadata,
    Column("user_id", BigInteger, primary_key=True, autoincrement=False),
    Column("login", Text, nullable=False),
    Column("avatar_url", Text),
    Column("assigned_at", DateTime(timezone=True)),
    Column("ended_at", DateTime(timezone=True)),
    Column("pending_cancellation_date", Date),
    Column("last_activity_at", DateTime(timezone=True)),
    Column("last_activity_editor", Text),
    Column("plan_type", Text),
    Column("assigning_team", Text),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

# Snapshot of GET /orgs/{org}/copilot/billing (single row, id = 1). Org totals only.
org_seat_summary = Table(
    "org_seat_summary",
    metadata,
    Column("id", SmallInteger, primary_key=True),
    Column("total", Integer, nullable=False),
    Column("added_this_cycle", Integer, nullable=False, server_default="0"),
    Column("pending_invitation", Integer, nullable=False, server_default="0"),
    Column("pending_cancellation", Integer, nullable=False, server_default="0"),
    Column("active_this_cycle", Integer, nullable=False, server_default="0"),
    Column("inactive_this_cycle", Integer, nullable=False, server_default="0"),
    Column("plan_type", Text),
    Column("synced_at", DateTime(timezone=True), nullable=False),
)

credit_usage = Table(
    "credit_usage",
    metadata,
    Column("user_id", BigInteger, primary_key=True),
    Column("day", Date, primary_key=True),
    Column("model", Text, primary_key=True),
    Column("login", Text, nullable=False),
    Column("sku", Text),
    Column("gross_qty", Quantity, nullable=False),
    Column("gross_usd", Money, nullable=False),
    Column("discount_usd", Money, nullable=False),
    Column("net_qty", Quantity, nullable=False),
    Column("net_usd", Money, nullable=False),
    # The admin pages read a period across everyone; the key starts with user_id.
    Index("ix_credit_usage_day", "day"),
)

org_credit_day = Table(
    "org_credit_day",
    metadata,
    Column("day", Date, primary_key=True),
    Column("model", Text, primary_key=True),
    Column("gross_qty", Quantity, nullable=False),
    Column("gross_usd", Money, nullable=False),
    Column("discount_usd", Money, nullable=False),
    Column("net_qty", Quantity, nullable=False),
    Column("net_usd", Money, nullable=False),
)

user_activity = Table(
    "user_activity",
    metadata,
    Column("user_id", BigInteger, primary_key=True),
    Column("day", Date, primary_key=True),
    Column("login", Text, nullable=False),
    Column("prompts", Integer, nullable=False),
    Column("generations", Integer, nullable=False),
    Column("acceptances", Integer, nullable=False),
    Column("loc_suggested", Integer, nullable=False),
    Column("loc_added", Integer, nullable=False),
    Column("used_agent", Boolean, nullable=False),
    Column("used_chat", Boolean, nullable=False),
    Column("used_cli", Boolean, nullable=False),
    Column("used_cloud_agent", Boolean, nullable=False),
    Column("used_app", Boolean, nullable=False),
    Column("used_review", Boolean, nullable=False),
    # The full NDJSON record, so new GitHub fields can be surfaced without re-fetching.
    Column("raw", JSONB, nullable=False),
    Index("ix_user_activity_day", "day"),
)

# GitHub's org-wide daily report (organization-1-day): numbers the per-user rows don't have,
# like pull requests, MCP servers and data coverage. Nullable where GitHub may leave them out.
org_activity_day = Table(
    "org_activity_day",
    metadata,
    Column("day", Date, primary_key=True),
    Column("daily_active_users", Integer),
    Column("weekly_active_users", Integer),
    Column("monthly_active_users", Integer),
    Column("missing_telemetry_users", Integer),
    Column("below_minimum_users", Integer),
    Column("prs_created", Integer),
    Column("prs_created_by_copilot", Integer),
    Column("prs_reviewed", Integer),
    Column("prs_reviewed_by_copilot", Integer),
    Column("prs_merged", Integer),
    Column("prs_merged_created_by_copilot", Integer),
    Column("pr_suggestions", Integer),
    Column("pr_applied_suggestions", Integer),
    Column("pr_copilot_suggestions", Integer),
    Column("pr_copilot_applied_suggestions", Integer),
    Column("median_minutes_to_merge", Float),
    Column("median_minutes_to_merge_copilot", Float),
    # The full record, so new GitHub fields can be surfaced without re-fetching.
    Column("raw", JSONB, nullable=False),
)

user_team_day = Table(
    "user_team_day",
    metadata,
    Column("user_id", BigInteger, primary_key=True),
    Column("day", Date, primary_key=True),
    Column("team_slug", Text, primary_key=True),
    Column("login", Text, nullable=False),
)

sync_run = Table(
    "sync_run",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("job", Text, nullable=False, index=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", Text, nullable=False),  # running | succeeded | failed | aborted
    Column("rows", Integer, nullable=False, server_default="0"),
    Column("error", Text),
)

# Last successful sync per job and day. Days without usage leave no rows in the data tables,
# so this is how the worker's startup catch-up knows which days it still has to fetch.
sync_day = Table(
    "sync_day",
    metadata,
    Column("job", Text, primary_key=True),  # sync-credits | sync-metrics
    Column("day", Date, primary_key=True),
    Column("synced_at", DateTime(timezone=True), nullable=False),
)

# Run/stop requests from the admin console. The API may only add them (admins, in their own
# name); the worker applies each to the job queue and records the outcome.
sync_request = Table(
    "sync_request",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("requested_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("admin_user_id", BigInteger, nullable=False),
    Column("admin_login", Text, nullable=False),
    Column("action", Text, nullable=False),  # run | stop
    Column("target", Text, nullable=False),  # credits | seats | budgets | metrics | history
    Column("handled_at", DateTime(timezone=True)),
    Column("outcome", Text),
)

# GitHub budgets for Copilot spend (organization-level scopes). Org totals only.
org_budget = Table(
    "org_budget",
    metadata,
    Column("id", Text, primary_key=True),
    Column("scope", Text, nullable=False),
    Column("entity_name", Text),
    Column("sku", Text, nullable=False),
    Column("budget_type", Text),
    Column("amount_usd", Money, nullable=False),
    Column("consumed_usd", Money, nullable=False),
    Column("prevent_further_usage", Boolean, nullable=False),
    Column("expires_at", DateTime(timezone=True)),
    Column("synced_at", DateTime(timezone=True), nullable=False),
)

# The budget GitHub applies to each seat holder (a personal one, else the org-wide one),
# with that person's consumption against it.
user_budget = Table(
    "user_budget",
    metadata,
    Column("user_id", BigInteger, primary_key=True, autoincrement=False),
    Column("login", Text, nullable=False),
    Column("budget_id", Text, nullable=False),
    Column("scope", Text, nullable=False),
    Column("sku", Text, nullable=False),
    Column("amount_usd", Money, nullable=False),
    Column("consumed_usd", Money, nullable=False),
    Column("prevent_further_usage", Boolean, nullable=False),
    Column("expires_at", DateTime(timezone=True)),
    Column("synced_at", DateTime(timezone=True), nullable=False),
)

# Copilot seat charges per month, from GitHub's billing usage summary.
org_seat_cost = Table(
    "org_seat_cost",
    metadata,
    Column("month", Date, primary_key=True),
    Column("seats", Quantity, nullable=False),
    Column("price_per_seat_usd", Money, nullable=False),
    Column("gross_usd", Money, nullable=False),
    Column("net_usd", Money, nullable=False),
    Column("synced_at", DateTime(timezone=True), nullable=False),
)
