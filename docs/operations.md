# Operations

Day-2 tasks for a [Docker Compose deployment](deployment/docker-compose.md). The commands run
in the stack's directory: the release bundle, or `deploy/` in a checkout.

- [Upgrading](#upgrading)
- [Downgrading](#downgrading)
- [Backup and restore](#backup-and-restore)
- [Syncing](#syncing)
- [Health checks and monitoring](#health-checks-and-monitoring)
- [Changing secrets](#changing-secrets)
- [Troubleshooting](#troubleshooting)

## Upgrading

1. Read the release notes of every release between yours and the target.
2. [Back up](#backup-and-restore) the database.
3. Set `APP_VERSION` in `.env` to the new release, then:

   ```bash
   docker compose pull && docker compose up -d
   ```

`migrate` applies new migrations before `api` and `worker` restart. In the worker-migrates
stack the worker applies them before it starts syncing.

If you leave `APP_VERSION` empty, the stack follows `latest`, and every `pull` moves it to the
newest stable release, migrations included. Pin a version in production.

**From a new release bundle**, carry over your `.env`, `secrets/`, and any `compose.override.yaml`,
`theme/` into the new directory, and run the commands there. The compose files
fix the project name (`copilot-usage`), so the new directory uses the same containers and
database volume.

**Postgres minor updates** (`postgres:18`): `pull` leaves the locally built `db` image alone.
Rebuild it:

```bash
docker compose build --pull db && docker compose up -d
```

## Downgrading

Undo the newer release's migrations **with the newer image, while it is still the one in use**:

```bash
docker compose run --rm migrate copilot-metrics migrate <revision>
# worker-migrates stack: docker compose run --rm worker copilot-metrics migrate <revision>
```

`<revision>` is the latest migration of the older release (see
[`backend/migrations/versions/`](../backend/migrations/versions/) at that release's tag). Then
lower `APP_VERSION` and run `docker compose up -d`.

An older image can't do this itself: it doesn't contain the newer migrations, so it can't undo
them. Started against a newer schema, its migration fails with Alembic's *"Can't locate
revision"*, and `api` and `worker` don't start. Downgrades may drop data that the newer release
added, so back up first.

## Backup and restore

Everything lives in the Postgres volume `copilot-usage_pgdata`. All usage data can be loaded
from GitHub again, but only within GitHub's retention (about 24 months of credits, 12 months of
metrics). A backup keeps older history.

**Back up** (online, consistent):

```bash
docker compose exec -T db pg_dump -U copilot -Fc copilot_metrics > copilot-$(date +%F).dump
```

**Restore** into an empty database, e.g. on a new host or after `docker compose down -v`:

```bash
docker compose up -d db                       # creates the roles; wait until it is healthy
docker compose exec -T db pg_restore -U copilot -d copilot_metrics --exit-on-error < copilot-2026-11-20.dump
docker compose up -d                          # migrate finds the schema up to date
```

The dump keeps object owners and grants, and the roles already exist because `db` creates them
on start, so the restored database works with the app's roles as it is. Restore into the same
or an older release than the one that made the dump. Test your restore before you need it.

## Syncing

The worker runs these on its own:

| What | Default schedule | Setting |
| --- | --- | --- |
| AI credits, recent days (re-fetches the last 2 days) | every 20 min | `SYNC_CREDITS_CRON` |
| Seats | hourly | `SYNC_SEATS_CRON` |
| Budgets | hourly, at :10 | `SYNC_BUDGETS_CRON` |
| Activity metrics (re-fetches the last 3 days) | daily, 06:00 UTC | `SYNC_METRICS_CRON` |
| Catch up on missing days | on every start | `SYNC_CATCH_UP_ON_START` |
| Prune the sync's own bookkeeping | daily, 03:30 UTC | `SYNC_PRUNE_CRON` |

**Run or stop a sync now:** *Admin console → Sync*, as an admin. Stopping also cancels a long
history load.

**Re-fetch all history**, synced or not (e.g. after GitHub corrected old numbers):

```bash
docker compose run --rm worker copilot-metrics backfill
# limit it:  ... backfill --credits-days 90 --metrics-days 30
```

This only queues the jobs. The running worker does them.

## Health checks and monitoring

| Check | Healthy when |
| --- | --- |
| `api`: `GET /healthz` (Compose health check) | the API is up and can reach the database (`503` otherwise) |
| `worker`: `copilot-metrics healthcheck` (Compose health check) | the worker is alive (recent heartbeat) and no job has failed `SYNC_ALERT_AFTER_FAILURES` (3) times in a row since its last success |
| `db`: `pg_isready` over TCP | Postgres accepts connections (only after the roles are set up) |

`docker compose ps` shows the states. To be alerted, point your monitoring at the containers'
health status or at `https://<your host>/healthz`. A job that keeps failing is also logged as an
error by the worker. In the dashboard, a banner tells everyone when credits haven't synced for
`SYNC_STALE_AFTER_HOURS` (3).

Logs: `docker compose logs -f api worker`. Set `LOG_LEVEL=DEBUG` for more detail.

## Changing secrets

| Secret | How |
| --- | --- |
| `API_DB_PASSWORD`, `WORKER_DB_PASSWORD`, `OWNER_DB_PASSWORD` | change in `.env`, then `docker compose up -d`. `db` restarts and sets the new passwords before it accepts connections. |
| `POSTGRES_PASSWORD` | only used when the volume is first created. Changing it in `.env` later has no effect. Change it inside Postgres (`ALTER ROLE copilot PASSWORD ...`) if you need to. |
| `SESSION_SECRET` | change in `.env`, then `docker compose up -d`. Everyone is signed out. |
| GitHub App client secret | generate a new one on the App's page, update `.env`, `up -d`, then delete the old one in GitHub. |
| GitHub App private key | generate a new one, replace `secrets/github-app.pem`, `docker compose up -d --force-recreate worker`, then delete the old key in GitHub. |

## Troubleshooting

**A service won't start.** `docker compose ps -a` and `docker compose logs <service>`. The app
checks its settings on start and names what is missing or wrong.

| Symptom | Cause and fix |
| --- | --- |
| `docker compose up` stops with `set GITHUB_ORG in .env` (or another variable) | A required value is empty in `.env`. |
| API log: `API_PUBLIC_URL ... is plain HTTP` | `PUBLIC_URL` is `http://` on a host other than `localhost`. Put HTTPS in front ([guide](deployment/docker-compose.md#6-put-it-behind-https)), or set `ALLOW_HTTP=true` on a test host. |
| API log: `SESSION_SECRET must be at least 32 characters` | Generate one with `python3 -c "import secrets; print(secrets.token_hex(32))"`. |
| Worker log: `Permission denied` on `/run/secrets/github_app_key` | The key file isn't readable by the container user: `chmod 644 secrets/github-app.pem`. |
| `migrate` fails: `password authentication failed` | The volume was created with other passwords and `db` hasn't restarted since. Run `docker compose up -d` (which restarts `db` when `.env` changed) and check `docker compose logs db`. |
| `migrate` fails: `Can't locate revision` | The database is from a newer release. See [Downgrading](#downgrading). |
| GitHub says *"The redirect_uri is not associated with this application"* | The App's callback URL must be exactly `<PUBLIC_URL>/auth/github/callback`. |
| Signed in, but *"No Copilot usage on record"* | The account isn't an active org member (e.g. a personal account), has no seat, or the seat was assigned in the last hour (wait for the next seat sync). |
| Org owner, but no admin console | Roles are taken at sign-in. Sign out and in again. |
| A team member doesn't get their role | Check the slug (from the team's URL, not its display name), that they're an active org member and not only invited, and that they have signed in again since. |
| Activity pages are empty, credits are fine | The org's *Copilot usage metrics* policy is off, or GitHub hasn't published the day yet (metrics arrive a day late, synced at 06:00 UTC). |
| Worker unhealthy: `failing: sync_... (3x since its last success)` | `docker compose logs worker` shows GitHub's error. Usually a missing App permission (`403`): add it to the App, then the org owner accepts the updated permissions under *Settings → GitHub Apps*. |
| Worker log warns that GitHub's report format changed | GitHub changed a report's fields. Syncing goes on with the fields the app knows. Check for a newer release. |
| Dashboard shows "may be behind" | Credits haven't synced for 3 hours. Check the worker's health and the Sync page. |
| Branding changes don't show | See [Branding](branding.md#3-edit-themejson-and-reload-the-page): the browser console logs why a theme was rejected. |
