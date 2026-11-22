# Contributing

Thanks for helping. Bug reports, fixes, docs and features are all welcome.

**Security issues:** please don't open an issue. Report them privately as described in
[SECURITY.md](SECURITY.md).

## Issues

- **Bugs:** what you did, what you expected, what happened. Add the version
  (`copilot-metrics --version`, or the image tag), how you deploy it, and the relevant logs.
  Leave out secrets, tokens and people's data.
- **Features and larger changes:** open an issue first and describe the problem you want to
  solve. Agreeing on the approach before you write the code saves both sides a rewrite.

## Pull requests

1. Fork the repository and create a branch from `main`.
2. Set up the [dev container](docs/development.md#getting-started-dev-container). It has every
   tool and a Postgres with the app's roles. You only need a development GitHub App to run the
   whole app, not for the tests.
3. Make the change, following the
   [backend](docs/development.md#backend-conventions) and
   [frontend](docs/development.md#frontend-conventions) conventions. Add or update tests, and
   update the docs in the same pull request when behaviour or settings change.
4. Run the checks:

   ```bash
   just check   # formatting, lint, types (also the git hook)
   just test    # backend and frontend tests, integration tests included
   ```

5. Open a pull request against `main`. Say what it changes and why, and link the issue.

Things that are easy to miss:

- **UI changes:** regenerate the documentation screenshots with `just screenshots` and commit
  `docs/images/`. A release stops when they're out of date
  ([details](tools/screenshots/README.md)).
- **Schema changes:** add a new Alembic revision in `backend/migrations/versions/`, including
  grants and row-level security for new tables. Never edit a released revision.
- **New settings:** document them in [docs/configuration.md](docs/configuration.md) and the
  `.env.example` files.
- **Titles:** pull requests are squash-merged, so the title becomes the commit message. Use a
  [Conventional Commits](https://www.conventionalcommits.org/) prefix: `feat:`, `fix:`, `docs:`,
  `refactor:`, `test:`, `chore:`.

On a first pull request, CI starts once a maintainer has approved the run. It runs the same
containers as `just ci-test`, plus the dependency audit. All checks must pass before a merge.

By contributing, you agree that your contribution is licensed under the [MIT License](LICENSE),
like the rest of the project.

## Maintainers

The project is maintained by [@InsaneDwayne](https://github.com/InsaneDwayne). Maintainers
review and merge pull requests, triage issues, and approve releases. Contributors need no
access to the repository: forks and pull requests are enough. Regular contributors may be
given the *Triage* role to help sort issues and pull requests, and maintainers get write access.
How releases work and how the repository is protected is in
[CI and releasing](docs/releasing.md).
