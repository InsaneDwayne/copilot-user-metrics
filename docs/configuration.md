# Configuration reference

The app reads its configuration from environment variables, parsed by pydantic-settings in
[`backend/src/copilot_metrics/settings.py`](../backend/src/copilot_metrics/settings.py). Each
process checks the settings it needs when it starts, and stops with a clear message if one is
missing or invalid.

With Docker Compose you don't set the app's variables directly. You fill in `.env` next to the
compose file, and the compose file passes each container only what it needs, sometimes under
another name (`PUBLIC_URL` becomes `API_PUBLIC_URL`, the passwords become connection URLs).
So there are two levels:

1. [**Stack variables**](#stack-variables-env): what you put in `.env`.
2. [**App settings**](#app-settings): what the processes read. The ones marked **✓ compose** are
   passed through from `.env` under the same name. To set any other one, add it to the service's
   `environment:` in a `compose.override.yaml`.

Generate secrets with `python3 -c "import secrets; print(secrets.token_hex(32))"`. Use hex for
database passwords, since they end up inside connection URLs.

## Stack variables (`.env`)

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `APP_VERSION` | | `latest` | Image tag to run. The release bundle pins it. Pin it in production. |
| `COMPOSE_FILE` | | `compose.yaml` | Which stack `docker compose` runs without `-f`, e.g. `compose.worker-migrates.yaml`. |
| `GITHUB_ORG` | ✔ | | Login of the organization (one per deployment). |
| `GITHUB_APP_ID` | ✔ | | The GitHub App's ID (worker). |
| `GITHUB_APP_CLIENT_ID` | ✔ | | The App's client ID (API, sign-in). |
| `GITHUB_APP_CLIENT_SECRET` | ✔ | | The App's client secret (API, sign-in). |
| `GITHUB_APP_PRIVATE_KEY_FILE` | | `./secrets/github-app.pem` | Host path of the App's private key, mounted into the worker only. |
| `PUBLIC_URL` | | `http://localhost:8000` | The URL people open. Also the base of the OAuth callback. Must be `https://` unless the host is `localhost` or `ALLOW_HTTP=true`. |
| `ALLOW_HTTP` | | `false` | Allow an `http://` `PUBLIC_URL` on other hosts. Test hosts only. |
| `APP_BIND` | | `127.0.0.1` | Host address the API is published on. Use `0.0.0.0` when the reverse proxy runs on another machine. |
| `APP_PORT` | | `8000` | Host port the API is published on. |
| `SESSION_SECRET` | ✔ | | Signs the session cookie, at least 32 characters. Whoever knows it can forge an admin session. |
| `POSTGRES_PASSWORD` | ✔ | | Postgres superuser. Only used inside the `db` container, to set up the roles. Takes effect when the volume is created. |
| `OWNER_DB_PASSWORD` | ✔ | | Owner role: runs migrations, owns the tables. |
| `API_DB_PASSWORD` | ✔ | | API role: read-only, under row-level security. |
| `WORKER_DB_PASSWORD` | ✔ | | Worker role: the only writer. |

The three role passwords are applied on every start of `db`, so changing one in `.env` and
running `docker compose up -d` changes it.

## App settings

Variables are grouped by prefix: `GITHUB_APP_ID` is `github.app_id` in `settings.py`,
`SYNC_CREDITS_CRON` is `sync.credits_cron`, and so on. Outside Compose, for example in
development, the app also reads a `.env` file in its working directory and
`.devcontainer/.env`.

### GitHub

| Variable | Process | Default | Meaning |
| --- | --- | --- | --- |
| `GITHUB_ORG` ✓ compose | both | | Organization login. |
| `GITHUB_APP_ID` ✓ compose | worker | | App ID, for the installation token. |
| `GITHUB_APP_PRIVATE_KEY_PATH` | worker | | Path of the private key in the container. Compose sets `/run/secrets/github_app_key`. |
| `GITHUB_APP_CLIENT_ID` ✓ compose | API | | For user sign-in. |
| `GITHUB_APP_CLIENT_SECRET` ✓ compose | API | | For user sign-in. |
| `GITHUB_API_URL` | both | `https://api.github.com` | REST API base URL. |
| `GITHUB_WEB_URL` | API | `https://github.com` | Base URL for sign-in and links. |
| `GITHUB_API_VERSION` | both | `2026-03-10` | `X-GitHub-Api-Version` header sent with every request. |
| `GITHUB_TIMEOUT_SECONDS` | both | `30` | Timeout per GitHub request. |

### API

| Variable | Default | Meaning |
| --- | --- | --- |
| `API_DATABASE_URL` | | Connection as the API role. Compose builds it from `API_DB_PASSWORD`. |
| `API_PUBLIC_URL` | `http://localhost:5173` | Compose sets it from `PUBLIC_URL`. The default suits the Vite dev server. |
| `API_ALLOW_HTTP` | `false` | Compose sets it from `ALLOW_HTTP`. |
| `API_STATIC_DIR` | none | Directory of the built dashboard to serve. The image has it at `/app/static`, and Compose sets that. |
| `API_POOL_SIZE` | `5` | Database connections per API process. |
| `API_DOCS` | `false` | Serve the interactive API docs at `/docs`, `/redoc`, `/openapi.json`. For development only. The compose files never set it. |
| `SESSION_SECRET` ✓ compose | | See above. |
| `SESSION_MAX_AGE_HOURS` ✓ compose | `4` | Session lifetime. Roles are re-checked with GitHub at each sign-in, so this bounds how stale a role can get. |
| `SESSION_COOKIE_NAME` | `copilot_session` | Name of the session cookie. |
| `ACCESS_ADMIN_TEAMS` ✓ compose | empty | Comma-separated team slugs whose members are admins (org owners always are). See [Security model](security.md#roles). |
| `ACCESS_ORG_READER_TEAMS` ✓ compose | empty | Comma-separated team slugs whose members are organization readers. |
| `SYNC_STALE_AFTER_HOURS` ✓ compose | `3` | The dashboard shows a "may be behind" banner when credits haven't synced for this long. |
| `FORWARDED_ALLOW_IPS` ✓ compose | `127.0.0.1` | Proxies whose `X-Forwarded-*` headers uvicorn trusts. Only affects the client address in logs: sign-in URLs come from `API_PUBLIC_URL`. |

### Worker and sync

| Variable | Default | Meaning |
| --- | --- | --- |
| `WORKER_DATABASE_URL` | | Connection as the worker role. Compose builds it from `WORKER_DB_PASSWORD`. |
| `WORKER_CONCURRENCY` | `1` | Jobs a worker process runs at once. |
| `WORKER_QUEUE` | `sync` | Job queue name. |
| `SYNC_CREDITS_CRON` ✓ compose | `*/20 * * * *` | Recent AI credit usage. |
| `SYNC_SEATS_CRON` ✓ compose | `0 * * * *` | Copilot seats and seat cost. |
| `SYNC_BUDGETS_CRON` ✓ compose | `10 * * * *` | Org and per-person budgets. |
| `SYNC_METRICS_CRON` ✓ compose | `0 6 * * *` | Activity metrics (GitHub publishes a day late). |
| `SYNC_PRUNE_CRON` ✓ compose | `30 3 * * *` | Prunes the sync's bookkeeping. |
| `SYNC_RECOVER_STALLED_CRON` | `*/5 * * * *` | Re-queues jobs a stopped or crashed worker left running. |
| `SYNC_CREDITS_LOOKBACK_DAYS` | `2` | Recent days each credits run re-fetches, to pick up late corrections. |
| `SYNC_METRICS_LOOKBACK_DAYS` | `3` | Recent days each metrics run re-fetches. |
| `SYNC_CATCH_UP_ON_START` ✓ compose | `true` | On start, queue every day within the backfill windows that isn't synced yet. |
| `SYNC_BACKFILL_CREDITS_DAYS` | `730` | Credit history window: GitHub keeps about 24 months. |
| `SYNC_BACKFILL_METRICS_DAYS` | `365` | Metrics history window: GitHub keeps about 12 months. |
| `SYNC_PARALLEL_REQUESTS` ✓ compose | `8` | GitHub calls a credit sync makes at once. |
| `SYNC_HISTORY_RETENTION_DAYS` ✓ compose | `90` (min 7) | Sync runs, handled run/stop requests and finished queue jobs older than this are pruned. Each job's latest success stays. Usage data is never pruned. |
| `SYNC_ALERT_AFTER_FAILURES` ✓ compose | `3` | A job failing this often since its last success is logged as an error and marks the worker unhealthy. |

Cron expressions are evaluated in the container's time zone, UTC unless you set `TZ`.

### Migrations

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | | Connection as the owner role, used by `copilot-metrics migrate` only. Compose builds it from `OWNER_DB_PASSWORD`. |
| `DATABASE_API_ROLE` | `copilot_api` | Role the migrations grant API access to. |
| `DATABASE_WORKER_ROLE` | `copilot_worker` | Role the migrations grant worker access to. |

### Common

| Variable | Default | Meaning |
| --- | --- | --- |
| `LOG_LEVEL` ✓ compose | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

## Frontend (development only)

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_API_BASE_URL` | same origin | API base URL baked into a frontend build. |
| `API_PROXY_TARGET` | `http://127.0.0.1:8000` | Where the Vite dev server proxies `/api` and `/auth`. |

The dashboard's look is configured at runtime through `theme.json`, not through environment
variables: see [Branding](branding.md).
