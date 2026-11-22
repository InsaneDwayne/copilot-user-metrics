# CI and releasing

How changes are checked, and how a release gets built and published. For the checks you run
locally, see [Development](development.md#tests-and-checks).

## CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on pull requests and pushes to `main`,
and is reused by the release workflow for `v*` tags. Everything runs in containers built from the
root [`Dockerfile`](../Dockerfile):

- **backend-test** (`backend-test` target): ruff, mypy and pytest. Integration tests run against
  a throwaway Postgres 18 from [`ci/compose.yaml`](../ci/compose.yaml); `TEST_DATABASE_REQUIRED=1`
  makes an unreachable database fail the run instead of skipping the tests.
- **frontend-test** (`frontend-test` target): oxlint, prettier, tsc and vitest.
- **image** (`app` target, after both test jobs): builds the runtime image and smoke-tests it
  with [`ci/smoke-test.sh`](../ci/smoke-test.sh): the CLI and `--version`, then the API started
  without a database, serving the dashboard (including client-side routes) and JSON under
  `/api`. It also checks that the `deploy/` stack is valid and runs the release image. CI doesn't
  push the image; publishing is the [release workflow](#releasing)'s job.

Run the same containers locally with `just ci-test`, and `just image` for the runtime image.

[`.github/workflows/audit.yml`](../.github/workflows/audit.yml) checks the lockfiles for known
vulnerabilities: `pip-audit` over `backend/uv.lock` and `npm audit --audit-level=high` over
`frontend/package-lock.json`. It runs on pull requests, pushes to `main` and weekly, because a
new advisory can affect lockfiles that haven't changed. [Dependabot](../.github/dependabot.yml)
proposes updates weekly for the backend, the frontend, GitHub Actions, the base images, the CI
stack's Postgres and the dev container features. The self-hosting stacks' `postgres:18` (inline
in their compose files) follows its major tag: minor updates come with `docker compose build --pull db`. Minor and patch bumps are grouped,
and a release has to be a week old before Dependabot proposes it. Turn on *Dependabot security
updates* in the repository settings so fixes for advisories arrive right away.

## Releasing

The release artifact is the runtime container image, published to GitHub Container Registry
as **`ghcr.io/insanedwayne/copilot-user-metrics`** for `linux/amd64` and `linux/arm64`. The one
image runs every part of the app (`copilot-metrics api | worker | migrate | backfill`).
Versions follow [PEP 440](https://peps.python.org/pep-0440/): `X.Y.Z`, optionally followed by
`aN`, `bN`, `rcN` or `.devN` (e.g. `1.4.0`, `1.5.0rc1`). You choose the version when you
release, and the git tag `v<version>` records it. Nothing in the repository holds the version:
`version` in `backend/pyproject.toml` is a placeholder (`0.0.0`), and the release build bakes the
real one into the image, where `copilot-metrics --version` reports it (`dev` for local and
CI builds).

**Start a release** in one of two ways:
- **From GitHub**: *Actions → Release → Run workflow*. Keep `main` selected, enter the version
  (e.g. `1.4.0`) and run. This releases `main`'s latest commit, and the workflow creates the
  tag `v1.4.0` once the image is published.
- **From a terminal**: on an up-to-date `main`, run `just release 1.4.0`. It checks the version
  and that the tree is clean and in sync with `origin/main`, then creates and pushes the
  annotated tag `v1.4.0`, which starts the workflow.

[`.github/workflows/release.yml`](../.github/workflows/release.yml) then runs:
- **verify**: the version is valid and the commit is on `main`. For a button run, the run must
  also be on `main`, and `v<version>` must not exist yet, since releases can't be overwritten.
- **ci**: the full CI workflow (tests and image build) runs against that commit.
- **screenshots** (alongside **ci**): regenerates the documentation screenshots of that commit
  from demo data by running `just screenshots` in the dev container (built from
  [`.devcontainer/`](../.devcontainer/)), and compares them with `docs/images/`. If they differ, the docs show an
  outdated UI and the release stops here, before anything is published (see
  [Outdated screenshots](#outdated-screenshots)).
- **publish**: builds the multi-arch image with the version baked in and pushes it with an SBOM
  and BuildKit provenance, plus a signed GitHub build-provenance attestation (public repo only,
  see below). It then pulls the image back and runs [`ci/smoke-test.sh`](../ci/smoke-test.sh) on
  each platform, including that `copilot-metrics --version` reports the version.
- **release**: builds the self-hosting bundle (`deploy/` without the build override, with
  `APP_VERSION` set to the release, checked with `docker compose config`). It then creates the
  GitHub Release with the bundle attached, setup and upgrade instructions, generated notes, and
  the image reference and digest, plus the tag on button runs. Pre-releases (`a`, `b`, `rc`,
  `.dev`) are marked as such.

Image tags for `1.4.2`: `1.4.2`, `1.4`, `1` and `latest`. Pre-releases only get their exact
version and never move `latest`. While on `0.x`, no bare major tag (`0`) is published. Pin
production to an exact version or to the digest from the release notes. To check where an
image came from:
`gh attestation verify oci://ghcr.io/insanedwayne/copilot-user-metrics@<digest> --repo InsaneDwayne/copilot-user-metrics`.
GitHub doesn't store attestations for private repositories on personal accounts, so while
this repo is private the attestation step is skipped. The image's BuildKit SBOM and provenance
are still published (`docker buildx imagetools inspect <image> --format '{{ json .Provenance }}'`).
It switches on by itself once the repo is public.

**One-time repository setup**
- The publish job runs in the `release` [environment](https://docs.github.com/actions/deployment/targeting-different-environments/managing-environments-for-deployment).
  GitHub creates it on the first run. Add required reviewers there to approve each release
  before anything is pushed.
- After the first release, set the GHCR package's visibility (*Packages → copilot-user-metrics →
  Package settings*). New packages start private.
- Recommended: a tag ruleset that limits who can create `v*` tags. Button runs create the tag
  as *GitHub Actions*, so add that app to the ruleset's bypass list.

If **verify**, **ci** or **screenshots** fails, nothing is published. If **publish** fails after the push
(the smoke test, say), the image tags exist but there's no GitHub Release, and on a button
run no git tag either. If the failure was transient (a registry or network hiccup), re-run
the failed jobs. Otherwise fix it on `main` and release a new version. Don't move or reuse a
tag that has been pushed.

### Outdated screenshots

When the **screenshots** job finds that the UI changed, it fails; its summary lists the images
that differ, and the run's `screenshots` artifact has the images it generated. Then:

1. Refresh them, either way:
   - *Actions → Screenshots → Run workflow*: pushes the new images to the `docs/screenshots`
     branch. Open a pull request from it (the run's summary links to it), review and merge.
   - In the dev container, on an up-to-date `main`: `just screenshots`, then commit
     `docs/images/` and merge it into `main` like any other change.
2. Start the release again, with the same version:
   - **From GitHub**: *Actions → Release → Run workflow* on `main`. No tag was created, since
     the release job never ran.
   - **From a terminal**: the tag points at the commit with the old screenshots, so move it to
     the new `main`: `git push --delete origin v1.4.0 && git tag -d v1.4.0`, then `git pull`
     and `just release 1.4.0`. Nothing was published under that tag, so this is safe. A tag
     ruleset that blocks deletion needs a bypass for this.

*Re-run failed jobs* doesn't help: a re-run releases the same commit, with the same old
screenshots.

To avoid the round trip, run `just screenshots` in the pull request that changes the UI, or
run the Screenshots workflow before releasing, and merge what changed. The release check uses
the dev container itself, so the images you generate locally are exactly what it expects, as
long as your dev container is up to date with `.devcontainer/` (rebuild it after changes).
