# Security policy

## Reporting a vulnerability

Please don't open a public issue. Report it privately through GitHub instead:
**[Report a vulnerability](https://github.com/InsaneDwayne/copilot-user-metrics/security/advisories/new)**
(*Security → Report a vulnerability* on the repository).

Include what is affected (version or commit, component), how to reproduce it, and what an
attacker gains. You'll get an answer within a week. Once a fix is released, the advisory is
published, with credit to you if you want it.

## Supported versions

Only the latest release gets security fixes. Fixes ship as a new release; images that have
been published are never changed.

## Scope

In scope: the code in this repository, the container image
`ghcr.io/insanedwayne/copilot-user-metrics`, and the self-hosting stack in `deploy/` as
shipped. Examples: one person seeing another person's data, a role reaching more than it
should, a session or OAuth flaw, a way around row-level security.

Out of scope: GitHub itself, a deployment that departs from the documented setup (say, TLS
turned off or the database exposed), and findings that only list outdated dependencies
without a way to exploit them here.

How the app is protected is described in the [security model](docs/security.md).
