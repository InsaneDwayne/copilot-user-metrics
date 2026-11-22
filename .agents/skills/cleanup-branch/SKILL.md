---
name: cleanup-branch
description: "Review and refine the current work-in-progress, defined as the git diff between the current branch and origin/main. Use when: user asks to clean up, refine, or polish current changes, wants a pre-PR code quality pass, or asks to check the diff for KISS/DRY/dead code/coupling issues."
---

# Cleanup Branch

## When to Use

- Before opening a PR, to polish the changes on the current branch
- User asks to "clean up my work", "refine the current changes", or "review the diff"
- A pre-PR quality pass focused on maintainability, not correctness review (use `pr-review` for that)

## Model Requirement

This skill requires judgment calls (KISS/DRY/coupling trade-offs, spotting mixed concerns, honoring user refactor intent) that small/fast models get wrong. Do not run this skill with lightweight or speed-optimized models (e.g. Haiku-class, "flash"/"mini"/"lite" code models). Use a medium-or-larger reasoning-capable model. If the active model is a small/fast tier, tell the user to switch model before proceeding.

## Scope

The "current work" is exactly the diff between `HEAD` and `origin/main`. Do not touch files or lines outside this diff unless a change inside the diff requires a small adjustment elsewhere (e.g. removing a now-unused helper).

## User-Directed Input

The user may point to specific files/functions in the diff and describe their own refactor idea or concept (e.g. "extract this into a hook", "merge these two branches of logic"). When that happens:

- Treat the user's pointer as the primary target instead of scanning the whole diff blindly.
- Apply the user's concept as stated; do not silently replace it with a different approach.
- Still validate the result against the [Quality Criteria](#quality-criteria) below, and flag (don't silently override) if the user's idea conflicts with a criterion.
- If the user's idea is ambiguous or underspecified, ask a clarifying question before making structural changes.
- Continue reviewing the rest of the diff against the full criteria unless the user says to focus only on the pointed-to code.

## Procedure

1. Fetch `origin/main` and diff against it (`git diff origin/main...HEAD`) to get the full list of changed files and hunks.
2. If the user provided specific pointers or a refactor concept, note them before reviewing (see [User-Directed Input](#user-directed-input)).
3. Read each changed file in full (not just the diff hunks) to understand surrounding context before editing.
4. Review each changed file against the [Quality Criteria](#quality-criteria) below. Note concrete violations with file/line references.
5. If no violations are found and there is no user-directed input, make no edits — do not rewrite, rename, or reformat code just to have something to show.
6. Apply fixes for real violations and any user-directed refactor, smallest safe change first. Prefer editing over rewriting.
7. After edits, re-run `git diff origin/main...HEAD` to confirm the change set is still coherent and no unrelated files were touched.
8. Run the project's lint/typecheck/tests for touched files (see `docs/development.md` for the commands) to confirm nothing broke.
9. Summarize what was changed and why, grouped by criterion (and by user request, if any), or state plainly that the branch is already clean and nothing needed to change.

## Quality Criteria

- **Project conventions**: changed files follow the conventions in `docs/development.md` and the layering in `docs/architecture.md`. These take precedence over generic preferences below (e.g. keep class/static-method helpers, keep constants in their constants module). If a fix reveals a recurring pattern the guidelines don't cover, propose a guideline addition in the summary instead of silently inventing a convention.
- **KISS**: no unnecessary abstraction, indirection, or cleverness; prefer the simplest implementation that satisfies the requirement.
- **DRY**: no duplicated logic within the diff or between the diff and existing codebase; extract shared logic only when duplication is real (2+ call sites), not speculative.
- **Modular**: each function/module has one clear responsibility; large functions/files are split along natural seams.
- **Generalized/reusable**: code that could apply beyond the current use case is written generically, but only when there is a concrete second use — don't over-generalize speculatively.
- **No dead code**: no unused imports, variables, functions, branches, or commented-out code blocks.
- **No migration/back-compat artifacts**: no feature flags, legacy fallbacks, or compatibility shims left over from the implementation process unless the task explicitly requires supporting an old contract/consumer. Released versions are in production, so never remove compatibility for external contracts or persisted data as a "cleanup" — flag it instead.
- **No mixed concerns per file**: a file should not mix, e.g., API contracts + business logic + presentation; split by concern following the project's layering (hexagonal backend / vertical slices frontend).
- **Low coupling**: minimize cross-module imports and hidden dependencies; prefer passing data through explicit interfaces/params over reaching into other modules' internals.

## Completion Check

- Every changed file in the diff has been reviewed against all criteria above.
- All applied fixes are within the diff's scope (no unrelated files modified).
- Lint/typecheck/tests pass for touched files.
- Final summary lists concrete changes per criterion, or explicitly states "no issues found" for criteria with nothing to fix.
- If the entire diff already satisfies every criterion, no files are modified and the summary says so directly instead of introducing changes for their own sake.
