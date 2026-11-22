---
name: pr-description
description: "Generate PR descriptions following project template. Use when: creating a pull request, need formatted PR description with Summary/Changes/Links sections. Input: issue numbers only (optional), uses current branch by default."
---

# PR Description Generator

## When to Use

- Creating a new pull request
- Need formatted PR description following project template (Summary/Changes/Links)
- Want to analyze diffs automatically between feature branch and main
- Need copy-pastable markdown code block output

## Quick Start

1. Check out your feature branch (or specify the branch)
2. Provide issue numbers (optional, e.g., `JRT-123 JRT-124`)
3. Skill analyzes diff and generates formatted output

## Procedure

### Step 1: Input (Optional Issue Numbers)

Provide issue numbers if applicable:

- Leave blank for no issues
- Format: space-separated (e.g., `JRT-123 JRT-456`)

Optionally specify a different branch (default is current branch):

- If not specified, uses current checked-out branch

### Step 2: Validate & Analyze

The skill will:

1. Verify current/specified branch is rebased on `origin/main` (warns if not)
2. Run [rebase check script](./scripts/check-rebase.sh)
3. If not rebased, rebase now:
   ```bash
   git fetch origin main && git rebase origin/main
   ```

### Step 3: Parse Git Diff

Analyzes changes between branch and `origin/main`:

- Extracts file paths
- Categorizes by Backend/Frontend/Config
- Identifies key changes (max 5-7 items)

### Step 4: Generate Description

Combines:

- **Summary**: Generated from diff context (can be refined)
- **Changes**: Auto-categorized changes in present passive tense
- **Links**: Issue numbers formatted as `Closes #JRT-123`

### Step 5: Copy Output

Final markdown code block is provided ready to copy-paste into GitHub PR description field.

## Output Template

The skill generates this structure:

```markdown
## Summary:

In this PR <present passive tense description of what was achieved>

## Changes:

- <Backend/Frontend/Config area>: <Change in present passive tense>
- <Another change area>: <Another change>

## Links:

Issues:

- Closes #JRT-123
- Closes #JRT-456
```

If no issues provided, Links section is omitted.

## Examples

**Example 1: Simple feature branch**

```
Input:
- Current branch: feature/quota-system
- Issues: JRT-42

Output: Analyzes feature/quota-system..origin/main diff, generates PR description
```

**Example 2: Different branch with multiple issues**

```
Input:
- Branch: refactor/auth-flow
- Issues: JRT-15 JRT-18

Output: Analyzes refactor/auth-flow..origin/main diff, creates multi-issue PR
```

**Example 3: No issues**

```
Input:
- Current branch: docs/update-readme
- Issues: (blank)

Output: Generates PR description without Links section
```

## Tips

- **Minimal input**: Just issues (optional) + branch (optional, defaults to current)
- **Present passive tense**: Changes auto-formatted as "X has been Y"
- **Issue format**: Space-separated (`JRT-123 JRT-456`) or leave blank
- **Branch override**: Specify if different from current checkout
- **Most important changes only**: Script omits minor formatting/comment-only changes

## Troubleshooting

**"Your branch is not rebased on origin/main"**

```bash
git fetch origin main
git rebase origin/main
```

**"No changes detected"**

- Verify current branch: `git status`
- Ensure not on `main`
- Verify there are commits: `git log origin/main..HEAD`

**"Branch name not recognized"**

- Specify full branch path if using short name alias

**Script permission error**

```bash
chmod +x .agents/skills/pr-description/scripts/check-rebase.sh
```

## References

- [Commit Message Conventions](../../../README.md)
