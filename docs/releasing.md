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
The SBOM and BuildKit provenance are also in the image itself
(`docker buildx imagetools inspect <image> --format '{{ json .Provenance }}'`). The attestation
step is skipped if the repository is ever made private, since GitHub doesn't store
attestations for private repositories on personal accounts.

If **verify**, **ci** or **screenshots** fails, nothing is published. If **publish** fails after the push
(the smoke test, say), the image tags exist but there's no GitHub Release, and on a button
run no git tag either. If the failure was transient (a registry or network hiccup), re-run
the failed jobs. Otherwise fix it on `main` and release a new version. Don't move or reuse a
tag that has been pushed.

### One-time repository setup

Only accounts with write access can start a release (*Run workflow* or a pushed `v*` tag), and
pull requests from forks run with a read-only token and no secrets. The settings below keep
it that way and make every release wait for an approval.

**Release gate**, *Settings → Environments → `release`* (the **publish** job runs in it, and
**release** only runs after **publish**):
- *Required reviewers*: the maintainers. Each release then waits for approval before anything
  is pushed. Leave *Prevent self-review* off while there's a single maintainer, or nobody can
  approve.
- *Deployment branches and tags → Selected*: the branch `main` and the tag pattern `v*`. A run
  from another branch, even with a changed `release.yml`, can't use the environment.
- Turn off *Allow administrators to bypass configured protection rules*.

**Tag ruleset**, *Settings → Rules → Rulesets → New tag ruleset*, targeting `v*`: restrict
updates and deletions, so a published release tag can't be moved or removed. Bypass:
*Repository admin*, for moving a tag after [outdated screenshots](#outdated-screenshots).
Don't restrict creations: button runs create the tag as GitHub Actions, which a repository on
a personal account can't add to the bypass list, so the release would fail after the image
was pushed. Creating a tag needs write access anyway, and the release it starts still waits
for the `release` environment's approval.

**Branch ruleset** targeting `main` only (the Screenshots workflow pushes
`docs/screenshots`):
- Block force pushes and deletions.
- Require a pull request: 0 approvals with a single maintainer, more once there are others.
  With a second maintainer, also add a `.github/CODEOWNERS` file (at least for `.github/`, the
  `Dockerfile`, `ci/`, `deploy/` and the dependency manifests) and turn on *Require review from
  Code Owners*. Not before: GitHub doesn't count an author's own review, so with a single code
  owner every pull request would be blocked.
- Required status checks: `backend-test`, `frontend-test`, `image` (CI) and `backend`,
  `frontend` (Audit). They can be picked once they have run. Require branches to be up to
  date.
- Bypass: *Repository admin* only.

Since **verify** only releases commits on `main`, this ruleset also decides what can be released.

**Merging**, *Settings → General → Pull Requests*: allow squash merging only, with the pull
request title as the commit message ([CONTRIBUTING.md](../CONTRIBUTING.md) asks for
Conventional Commits titles), and turn on *Automatically delete head branches*.

**Actions**, *Settings → Actions → General*:
- *Fork pull request workflows*: require approval for all external contributors, so a
  stranger's pull request runs nothing until approved.
- *Workflow permissions*: read repository contents, and don't allow GitHub Actions to create or
  approve pull requests. Jobs that write ask for it themselves.
- *Allowed actions*: GitHub's own plus `docker/*`, `astral-sh/setup-uv@*` and
  `devcontainers/ci@*` (the screenshots check).

**Security**, *Settings → Advanced Security*: Dependabot alerts and security updates, secret
scanning with push protection, CodeQL default setup (Python, JavaScript/TypeScript, Actions),
and private vulnerability reporting, which [`SECURITY.md`](../SECURITY.md) points to.

**Package**: after the first release, make the GHCR package public (*Packages →
copilot-user-metrics → Package settings*; new packages start private), and under *Manage
Actions access* keep this repository as the only one with write access.

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
