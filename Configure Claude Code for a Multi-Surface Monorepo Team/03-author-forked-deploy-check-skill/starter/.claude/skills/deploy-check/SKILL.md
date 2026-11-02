---
name: deploy-check
description: Run the team's read-only pre-deployment validation checklist in a forked sub-agent
context: fork
argument-hint: "[target] (defaults to main)"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(gh pr view:*)
  - Bash(gh pr checks:*)
---

# /deploy-check

Runs the team's pre-deployment validation checklist against the current working tree and the branch you're about to ship. Read-only by design — this skill never modifies files, never pushes, never deploys. It returns a single structured summary so the calling session can decide whether to proceed.

## Why this is a skill (not a CLAUDE.md addition)

`/deploy-check` is on-demand, forked, and task-specific: you only need it right before
a deploy, and it produces verbose intermediate output (file enumeration, diff parsing,
check execution traces) that has no value once the summary is known. CLAUDE.md is for
always-loaded, universal conventions that must be present in every session (e.g.
"tests are co-located", "throw ApiError for validation failures"). Rule of thumb:
on-demand / forked / task-specific → skill; always-loaded / universal → CLAUDE.md.
Without this contrast, teammates default to dumping everything into CLAUDE.md and end
up with a 600-line monolith that wastes context on every session.

## Why `context: fork`

The goal of `context: fork` is to keep verbose intermediate output out of the main
session: a deploy check walks the working tree, inspects diffs, and runs several
enumeration passes, none of which has any value to the calling conversation once we
know whether to ship. Only the structured summary should return to the main session.
`context: fork` is a Claude Code product feature operating at the skill-invocation
layer, conceptually analogous to the Architect's Playbook *Branching Reality* pattern
(which describes session-level forking via `fork_session`) — if you know that
Playbook pattern, this is the same idea applied at the skill layer.

## Checks

Run all three. Each check produces a pass-or-fail verdict; if any fails, the overall summary is **fail**.

### Uncommitted changes

- **Detect:** Run `git status --porcelain`.
- **Pass:** The command returns empty output — the working tree is clean.
- **Fail:** Any line is returned. Surface the modified/untracked file list in the verdict detail so the author knows what to commit or stash.

### Migrations up-to-date with code

- **Detect:** For every new repository import under `src/db/repositories/` introduced in the diff since the target branch, check whether a matching migration file exists in the same branch.
- **Pass:** Every new repository import has a corresponding migration file.
- **Fail:** At least one new repository import has no matching migration. Surface the repository module path(s) missing a migration in the verdict detail.

### CI checks green on the open PR

- **Detect:** Run `gh pr view --json statusCheckRollup` against the current branch's PR.
- **Pass:** Every required check in `statusCheckRollup` reports `SUCCESS`.
- **Fail:** Any required check is missing, pending, or reports a non-success state. Surface the failing check name(s) in the verdict detail.

## Output format

Return exactly this shape to the main session:

```
verdict: pass | fail
checks:
  - name: <check-name>
    status: pass | fail
    detail: <one line or empty>
```

Do not include the raw `git status`, raw diff hunks, or full check logs in the returned summary — those stay in the fork. If the author wants to investigate a failed check, they can re-invoke the skill targeting that single check or run the underlying command themselves.

## Personalization

This skill is project-scoped (`.claude/skills/deploy-check/`) so the whole team runs
the same checks. A teammate who wants a stricter personal variant — say, one that
additionally fails when the diff exceeds 500 lines without a long enough PR
description — can create a parallel skill at `~/.claude/skills/deploy-check-strict/`
under a different name. Their variant lives only on their machine and will not be
committed to the repo or affect teammates.

## What this skill deliberately does not do

- It never pushes, deploys, or runs migrations. The `allowed-tools` allowlist is read-only by construction; even if a future maintainer adds `Write` here, the team's `/review` command should catch the change.
- It does not run the test suite. Tests have their own pre-merge gate in CI; duplicating that here would slow every deploy check without adding signal.
- It does not check for secrets in code. That's the job of the `gitleaks` pre-commit hook, which fails the commit, not the deploy.
