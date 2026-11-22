# Development

How to run the app from source, test it, and follow the code conventions. For how the code is
organized, see [Architecture](architecture.md).

## Getting started (dev container)

The [dev container](../.devcontainer/) has Python, Node, `uv`, `just`, pre-commit, Playwright's
Chromium (for the [documentation screenshots](../tools/screenshots/README.md)) and a Postgres with the app's
roles already set up.

1. **Register a development GitHub App**, separate from production. Use the same read-only
   permissions as in [the deployment guide](deployment/docker-compose.md#1-create-the-github-app),
   with the callback URL `http://localhost:5173/auth/github/callback` (the Vite dev server) and
   no webhook. An org owner installs it and enables the Copilot usage metrics policy.
2. `cp .devcontainer/.env.example .devcontainer/.env` and fill it in. Put the private key under
   `.secrets/`, which is gitignored.
3. Open the repository in the dev container. It runs `just install` on creation.
4. In VS Code → *Run and Debug*:
   - **Backend: Migrate DB** (once, and after pulling new migrations)
   - **Full stack**, or start **API**, **Sync worker** and **Vite dev server** separately
5. Open http://localhost:5173.

On start, the worker catches up with GitHub: it queues every day within GitHub's retention that
the database doesn't have yet.

### From the terminal

[`just`](https://just.systems) runs the same tasks. `just` alone lists every recipe:

| Recipe | What it does |
| --- | --- |
| `just install` | backend and frontend dependencies, plus the git hook |
| `just migrate [revision]` | apply migrations (default `head`) |
| `just downgrade [revision]` | roll back (default one step, `base` for an empty schema) |
| `just db-reset` | drop and recreate the dev schema (deletes all synced data) |
| `just api` | API with auto-reload on http://127.0.0.1:8000 |
| `just worker` | sync worker |
| `just web` | Vite dev server on http://localhost:5173 (proxies `/api` and `/auth` to the API) |
| `just backfill` | re-fetch all history, synced or not |
| `just check` | formatting, lint and type checks (the pre-commit hook, on all files) |
| `just test` | backend (pytest, including integration) and frontend (vitest) tests |
| `just ci-test` | the CI test containers, locally (needs Docker) |
| `just image [tag]` | build the runtime image and smoke-test it (needs Docker) |
| `just screenshots` | regenerate the docs' screenshots from demo data, see [the playbook](../tools/screenshots/README.md) |
| `just release <version>` | tag and push a release, see [Releasing](releasing.md#releasing) |

Run `just api`, `just worker` and `just web` in separate terminals.

### Running the full image locally

To try the production image with your changes, use the build override of a deploy stack. See
[Building from source](deployment/docker-compose.md#building-from-source).

## Configuration in development

The backend reads `.devcontainer/.env` (and a `.env` in its working directory). The commented
[`.devcontainer/.env.example`](../.devcontainer/.env.example) lists what you need. Every setting
is in the [Configuration reference](configuration.md). Useful in development:

- `API_PUBLIC_URL` defaults to `http://localhost:5173`, the Vite dev server, so the session
  cookie and the OAuth callback live on one origin.
- `API_DOCS=true` serves the interactive API docs at `/docs`.
- `VITE_API_BASE_URL` (default: same origin) and `API_PROXY_TARGET` (default
  `http://127.0.0.1:8000`) control where the frontend sends API calls.

## Tests and checks

```bash
just check       # the pre-commit hook on all files: formatting, lint, types
just test        # backend (pytest, incl. integration) and frontend (vitest)
```

The git hook ([`.pre-commit-config.yaml`](../.pre-commit-config.yaml), installed by
`just install`) runs on each commit: whitespace and end-of-file fixes, merge markers, private
keys, then ruff (check and format) and mypy for the backend, and prettier, oxlint and tsc for the
frontend. The tools come from `backend/.venv` and `frontend/node_modules`, so they match the
lockfiles. Tests are not part of the hook. Run `just test`.

Backend integration tests run against `TEST_DATABASE_URL` (migrated from scratch on each run) and
exercise RLS, grants and the session guards end to end. Numbers are computed in `usage/domain/`,
so most logic is unit-tested without a database.

CI runs the same checks in containers: see [CI and releasing](releasing.md#ci).

## Backend conventions

See [`backend/README.md`](../backend/README.md) for the module rules, and
[Architecture](architecture.md#backend-layout) for the layout and the error model. In short:

- Modules talk through their public services and ports, never through another module's adapters.
- Routes raise domain errors from `shared/errors.py`, never `HTTPException`.
- The API process never queues jobs and never uses the GitHub App client.
- Schema changes are Alembic revisions in `backend/migrations/versions/`, including grants and RLS
  policies for new tables.

## Frontend conventions

- **Imports.** `@/…` is `frontend/src/…` (`paths` in `tsconfig.app.json`, `resolve.alias` in
  `vite.config.ts`). Import from another folder with `@/`, from the same folder with `./`, and
  from another feature only through its `index.ts` (`@/features/session`).
- **Styling.** Tailwind CSS 4, with every design token in `@theme` in
  `frontend/src/shared/styles/index.css`. Tailwind's default palette is switched off, so only
  theme colours exist. Colours come in three layers: base (`canvas`, `surface`, `fg`, `accent`),
  generated ramps (`accent-*`, `neutral-*`) and roles (`fg-muted`, `line`, `tint`, `series-*`,
  `chart-*`, …) that default to ramp steps. **Components use base colours and roles only**,
  never ramp steps, arbitrary colours or `var(--color-…)`, so a theme can restyle every role.
  `shared/theme/tokens.test.ts` fails on a violation. Need a new kind of colour? Add a role to
  `index.css` and to `ROLE_TOKENS` in `shared/theme/tokens.ts`. Type sizes, radii and shadows
  are tokens too (`text-lead`, `rounded-tag`, `shadow-raised`, `inset-ring-line`, …).
- **Components.** Shared building blocks (`Button`/`buttonClass`, `Tag`, `Table`/`Th`/`Td`,
  `Surface`, `Card`, `ShareBar`, …) are in `shared/components/ui/`. They take everything through
  props and know nothing about the app (no API types, hooks, router or theme config). Shared
  components that do (`BudgetMeter`, `PeriodPicker`, `QueryState`, `Tabs`, …) sit one level up in
  `shared/components/`, and charts in `charts/`. `cn()` merges class names so a later class wins.
- **Theme internals.** The SPA fetches `/theme/theme.json` before the first render, and its paths
  resolve relative to that file. The default theme lives only in `frontend/public/theme/` (used by
  the dev server and baked into the image). The accent and each mode's background expand into
  the 100–900 OKLCH ramps (`shared/theme/ramps.ts`). `applyTheme.ts` writes both modes, plus the
  theme's token overrides, into one `<style>` at `:root` specificity, then loads the theme's
  stylesheet. The shared accent is darkened or lightened per mode just enough to reach 4.5:1
  contrast. `npm run theme:schema` regenerates `theme.schema.json` next to the default theme.
  User-facing docs: [Branding](branding.md).
- **Light and dark mode.** The header toggle cycles System → Light → Dark. The choice is kept in
  `localStorage` (`theme-mode`) and synced across tabs, and an inline script in `index.html`
  applies it before the first paint. Light mode mirrors the ramps around the ground (100 furthest
  from the canvas, 900 closest), so roles keep their contrast in both modes without `dark:`
  variants. `dark:` follows the toggle, for the rare case that needs it (e.g. the dark-mode logo).
