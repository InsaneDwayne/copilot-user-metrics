# Documentation screenshots

The screenshots in `docs/images/` are generated, not taken by hand. A
Playwright script signs in as fictional people of a fictional organization (`acme-labs`) and
captures every page in light and dark mode.

**A release requires them to be current:** the [release workflow](#the-release-check)
regenerates them and stops if they differ from the committed ones. Run the script after a UI
change and commit the images with it, or to add a new shot. The [Screenshots
workflow](#the-screenshots-workflow) does the same for `main` and pushes the result to a branch.

No real data, no GitHub App and no sign-in are involved:

1. **Demo database.** The script drops and recreates a separate database, `copilot_demo`, on
   the dev container's Postgres, migrates it, and fills it with
   [`demo_data.py`](demo_data.py): 26 people in 6 teams, 180 days of AI credits, 120 days of
   activity metrics, budgets, seat cost and sync history. The data is written through the sync
   worker's own store, as the worker role, so it takes the same path as a real sync. Your dev
   database (`copilot_metrics`) is not touched.
2. **Demo API.** It runs the API on port 8100, serving the built dashboard from
   `frontend/dist`, with a throwaway session secret. Its settings are passed in directly, so
   your `.devcontainer/.env` isn't read.
3. **A fixed date.** The data, the API's clock and the browser's clock are all set to the same
   moment: `AS_OF` in [`screenshots.py`](screenshots.py) (2026-11-20, 14:00 UTC). So "this
   cycle", "synced 9 minutes ago" and every number come out the same on each run.
4. **Personas.** It signs each persona in by minting the session cookie with that secret, the
   same cookie the API sets after a real GitHub sign-in:

   | Persona | Role | Used for |
   | --- | --- | --- |
   | `dana-dev` | member, heavy user, personal budget | Usage, Activity |
   | `olivia-owner` | admin (org owner) | admin console, Sync |
   | `rui-reader` | organization reader | admin console without Sync |
   | `pat-personal` | outsider (not in the org) | no-access page |

5. **Capture.** Headless Chromium at 1440×900, in UTC and `en-US`, waits until nothing is
   loading and the fonts are ready, then takes a full-page screenshot. The script stops with an
   error if a section fails to load or a page redirects, so a broken page never ends up in the
   docs as a screenshot.
6. **Offline, with a fixed font.** The theme loads Inter from Google Fonts, which can change the
   font or be unreachable at any time. The capture serves the copy in [`fonts/`](fonts/)
   instead (Inter 4.1, the full variable font, so no character falls back to a system font)
   and blocks every other request that doesn't go to the demo API. Font hinting, grayscale
   anti-aliasing and the color profile are fixed too, so they don't depend on the system's
   fontconfig (Ubuntu turns on sub-pixel text, Debian doesn't), Skia (Chromium's graphics
   library) uses its portable code rather than a variant picked for the CPU, and Chromium
   always redraws whole tiles (no partial raster), so a page that re-renders after loading
   doesn't leave timing-dependent edges behind. Updating Inter means
   replacing `fonts/InterVariable.woff2` and refreshing the screenshots.
7. **Save only what changed.** Chromium doesn't encode the same pixels to the same PNG bytes
   on every run, and the settings above still leave room for an anti-aliased edge to come
   out a color level or two apart between machines. So the script compares the pixels with the image
   already in `docs/images/` and leaves the file untouched unless a pixel differs by more than
   `PIXEL_TOLERANCE` (8 of 255 per channel) in [`screenshots.py`](screenshots.py). Real UI
   changes differ by far more. A changed image is written with Pillow, whose output is stable,
   and the script prints how many pixels differ and by how much. An unchanged UI leaves
   `docs/images/` byte for byte as it was, and `git status docs/images` shows only real
   changes.

## Run it

In the dev container, which brings everything this needs: Postgres, Playwright (a locked
dependency of the backend's `screenshots` group, which `just install` installs), and the
Chromium build that Playwright version expects, with its system libraries and fonts. The
Chromium comes from Microsoft's Playwright image (`/ms-playwright`), so nothing is downloaded
from Playwright's host:

```bash
just screenshots           # builds the frontend, then regenerates every screenshot
```

A dev container created before Chromium was added needs a rebuild once (*Dev Containers:
Rebuild Container*).

Output, about a minute later:

```text
docs/images/
├── signin.png               signin-dark.png
├── my-usage.png             my-usage-dark.png
├── my-activity.png          my-activity-dark.png
├── no-access.png            no-access-dark.png
├── admin-overview.png       admin-overview-dark.png
├── admin-adoption.png       admin-adoption-dark.png
├── admin-members.png        admin-members-dark.png
├── admin-member-detail.png  admin-member-detail-dark.png
├── admin-seats.png          admin-seats-dark.png
├── admin-team.png           admin-team-dark.png
├── admin-sync.png           admin-sync-dark.png
└── reader-overview.png      reader-overview-dark.png
```

Look through the images (`git status docs/images` shows which changed) and commit them.

The release check runs `just screenshots` in the dev container itself, so your local images
are exactly what it expects, as long as your dev container is up to date with `.devcontainer/`
(see [The release check](#the-release-check)).

### Options

Everything after `just screenshots` goes to the script:

| Option | Default | What it does |
| --- | --- | --- |
| `--only NAME ...` | all | only these shots, e.g. `--only my-usage admin-overview` |
| `--scale N` | `1` | device pixel ratio. `2` gives retina-sharp images at four times the file size. |
| `--width`, `--height` | `1440`, `900` | viewport. Full-page shots grow taller as needed. |
| `--out DIR` | `docs/images` | output directory |
| `--as-of DATE` | `AS_OF` | the moment shown: `2027-03-15` (14:00 UTC), a full ISO time, or `now` |
| `--skip-seed` | | reuse the demo database from the last run (faster when only the UI changed). Use the same `--as-of` as that run. |
| `--browser PATH` | `$SCREENSHOTS_BROWSER`, else Playwright's, else a system `chromium` | Chromium executable to use |
| `--serve` | | seed, start the demo API on http://127.0.0.1:8100 and wait. It prints a session cookie per persona: set it as `copilot_session` in your browser's dev tools to look around as that persona, e.g. to frame a new shot. Your browser's own clock isn't stopped, so add `--as-of now` to see the current cycle. |
| `--port N` | `8100` | port of the demo API |

### Outside the dev container

The script needs:
- a Postgres with the app's `copilot_api` and `copilot_worker` roles;
- `DATABASE_URL` for a role that may create databases (or `DEMO_ADMIN_DATABASE_URL`, which
  wins), and `API_DATABASE_URL` and `WORKER_DATABASE_URL` for the two roles. The database
  name in these URLs is ignored: the script always uses `copilot_demo`.
- `uv` and Node, as for development, and `uv sync --directory backend --group screenshots`
  (`just install` does it).
- a browser: `just screenshots-setup` installs Playwright's Chromium with its system
  libraries, or Debian's `chromium` where Playwright's download host is blocked.

## Change it

- **Add or change a shot:** edit `SHOTS` in [`screenshots.py`](screenshots.py): a file name, a
  path (query strings work, e.g. a period), the persona, and whether to capture the full page.
- **Change the data:** edit [`demo_data.py`](demo_data.py). Keep it fictional: no real logins,
  names or avatars. Avatars are left empty on purpose, so the dashboard shows initials and
  never loads an image from GitHub. The random generator is seeded, and every date is relative
  to the `--as-of` moment, so the same moment gives the same data and the current billing
  cycle is always filled. Changing the data changes the images, and the next refresh opens a
  pull request for them.
- **Move the date forward:** change `AS_OF` in `screenshots.py`, e.g. once a year, so the
  screenshots don't show an old month.
- **A new field in GitHub's reports:** add it to the generated records in `demo_data.py`, or
  the related cards stay empty in the screenshots.
- **Use them in the docs:** every shot appears in the [user guide](../../docs/user-guide.md),
  in the section for its page, and `my-usage` and `admin-overview` also in the main README.
  Add a new shot there too. In the guide, use a plain Markdown image of the light version,
  which every viewer shows (GitHub, the VS Code preview and its Markdown editor):

  ```markdown
  ![The Usage page: AI credits this month, per model, with the budget](images/my-usage.png)
  ```

  The README, which is mostly read on GitHub, uses `<picture>` so GitHub shows the dark image
  to readers in dark mode. Some viewers drop that HTML and show no image:

  ```html
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/my-usage-dark.png">
    <img alt="The Usage page: AI credits this month, per model, with the budget" src="docs/images/my-usage.png">
  </picture>
  ```

## The Screenshots workflow

[`.github/workflows/screenshots.yml`](../../.github/workflows/screenshots.yml) runs by hand
(*Actions → Screenshots → Run workflow*):

1. It checks out `main` and regenerates the images exactly as the release check does (below).
2. If `docs/images/` changed, it commits the images on top of `main` and force-pushes them to
   the `docs/screenshots` branch. If nothing changed, it stops there. The run's summary links
   to *open a pull request* from the branch, and the run's page has the images as an artifact.

Review the images in the pull request's *Files changed* (GitHub shows image diffs side by side,
swipe or onion skin) and merge it like any other change. Nothing is pushed to `main`.

The workflow doesn't open the pull request itself, so no repository setting or token is
needed. A push with the default token doesn't start CI; it runs once you open the pull request.

## The release check

The [release workflow](../../docs/releasing.md) starts the dev container for the commit it
releases, with [`devcontainers/ci`](https://github.com/devcontainers/ci) (the same build,
database and `just install` as in VS Code), and runs `just screenshots` in it, alongside CI. The
dev container image's layers are kept in the GitHub Actions cache, so only what changed in
`.devcontainer/Dockerfile` is rebuilt. If the regenerated images differ from the committed ones, it fails before
anything is published. Run the [Screenshots workflow](#the-screenshots-workflow) or
`just screenshots`, merge the new images, then start the release
again: see [Outdated screenshots](../../docs/releasing.md#outdated-screenshots) for how, since
a re-run would release the same commit. The failed run also has the images it generated as
the `screenshots` artifact. Both this check and the Screenshots workflow use the capture steps
in [`.github/actions/screenshots`](../../.github/actions/screenshots/action.yml).

Because an unchanged UI leaves the images untouched, any difference stops the release: a
changed page, changed demo data, a new `AS_OF`, a new copy of Inter, or a Playwright update that
renders differently. The job summary lists which images changed.

Playwright is locked in `backend/uv.lock` (group `screenshots`). The dev container's Chromium
comes from the Playwright image in [`.devcontainer/Dockerfile`](../../.devcontainer/Dockerfile),
whose tag must name the same version. Dependabot proposes both updates on the same Monday: the
package with the other backend dependencies, the image with the other images. Merge both,
rebuild the dev container and run `just screenshots`. Until then the script stops with a
message saying the browsers don't match.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `No browser found` | In the dev container: rebuild it, it ships Chromium. Elsewhere: `just screenshots-setup`. |
| `The browsers in /ms-playwright (...) aren't the ones Playwright X needs` | The Playwright package and the Playwright image in `.devcontainer/Dockerfile` don't match. The image must be the Python one, `mcr.microsoft.com/playwright/python:vX-noble`, at the package's version (or merge Dependabot's update of it); the Node.js image of the same version can ship another Chromium build. Then rebuild the dev container. |
| `No module named 'playwright'` | `just install` (it syncs the backend's `screenshots` group). |
| `just screenshots-setup`: `Request to https://cdn.playwright.dev/... timed out` | The network blocks Playwright's download host. The recipe then installs Debian's `chromium` instead, and the script uses it automatically. |
| `error while loading shared libraries` | The browser's system libraries are missing. Outside the dev container: `just screenshots-setup` installs them (`--with-deps`). |
| `frontend/dist is missing` | `just screenshots` builds it. When calling the script directly, run `npm --prefix frontend run build` first. |
| `<page> as <persona>: a section failed to load` | An API call failed for that page. Run with `--serve`, open the page with that persona's cookie, and check the browser console and the API output. Often a new endpoint needs more demo data. |
| `redirected to /no-access` (or `/`) | The persona lacks the role or seat the page needs. Check `ROLES` in `screenshots.py` and the seats in `demo_data.py`. |
| `permission denied to create database` | `DATABASE_URL` (or `DEMO_ADMIN_DATABASE_URL`) must be a role with `CREATEDB`, e.g. the dev container's `copilot` superuser. |
| Port 8100 in use | `--port 8101` |
