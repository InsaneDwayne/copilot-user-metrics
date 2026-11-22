# Backend — `copilot_metrics`

A modular monolith. Each module is hexagonal: `domain.py` (pydantic models, pure logic; in `usage`
and `sync` a `domain/` package with one file per area) →
`ports.py` (ABCs every adapter subclasses) → `service.py` (use cases) → `adapters/` (HTTP, Postgres, GitHub, jobs).

```
src/copilot_metrics/
  settings.py      pydantic-settings, one group per env prefix
  api.py           composition root: FastAPI app factory
  worker.py        composition root: create_worker(settings) -> procrastinate app + SyncRuntime
  cli.py           copilot-metrics api | worker | migrate | backfill | healthcheck
  shared/          kernel (Period, Viewer, Role), tables, db (RLS scope), GitHub HTTP basics
  identity/        sign-in (GitHub App user authorization), session guards
  usage/           read side: /api/me, /api/org, /api/admin
  sync/            write side: GitHub App client, upserts, scheduled tasks
migrations/        Alembic revisions: schema, grants, RLS policies, procrastinate queue
tests/unit         domain logic, settings, GitHub client (fake transport), SPA path containment
tests/integration  real Postgres: worker writes, API reads through RLS
```

Rules of thumb: modules talk through their public services/ports, never another module's
adapters; the API process never queues or cancels jobs and never uses the GitHub App client:
from `sync` it imports only the Sync page's HTTP router, `SyncControlService` and the
`sync_request` Postgres adapter (which also reads queue counts), so an admin's run/stop is a
row the worker picks up. Numbers are computed in `usage/domain/` so they're unit-tested
without a database.

Procrastinate upgrades: add the SQL from `procrastinate/sql/migrations` as a new Alembic revision.

More: [Architecture](../docs/architecture.md) (components, sync jobs, error model) and
[Development](../docs/development.md) (running and testing it).
