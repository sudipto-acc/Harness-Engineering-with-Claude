# E-Commerce Platform — Shared Claude Code Conventions

This file is the **project-level** entry point for the e-commerce monorepo. Every teammate's Claude session loads it automatically.

## Scope: what belongs here vs. elsewhere

| Scope | Location | Shared with teammates via version control? | Example content |
|---|---|---|---|
| Project-level | `./CLAUDE.md`, `.claude/` | Yes — committed to the repo | Shared coding standards, path-scoped rules, team commands |
| User-level | `~/.claude/` | No — lives only on your machine, never shared via version control | Your preferred commit message style |
| Directory-level | subdirectory `CLAUDE.md` | Yes — committed alongside the subdirectory | Conventions specific to one package in the monorepo |

Project-level and directory-level configuration encode team-wide agreements, so they belong in version control where every teammate's session picks them up automatically. User-level configuration is personal preference — it should never dictate how the team writes code, so keep it out of this repo entirely.

## Shared standards (modular via @-imports)

The actual conventions live in focused files so this entry point stays scannable:

@.claude/standards/frontend.md
@.claude/standards/api.md
@.claude/standards/database.md
@.claude/standards/testing.md

Path-scoped rules in [.claude/rules/](.claude/rules/) layer on top of these standards and activate only when Claude is editing matching files (React components, API handlers, test files).

## Repository layout

```
src/components/   React components (functional + hooks)
src/pages/        Top-level routes
src/api/          Node.js API handlers
src/db/           PostgreSQL repository-pattern modules
```

Tests are co-located: `Foo.tsx` lives next to `Foo.test.tsx`.

## Troubleshooting

If a CLAUDE.md instruction doesn't seem to be followed, run `/memory` to see exactly which configuration files loaded for the current session.

## Team workflows

- `/review <pr-ref>` — codified PR review checklist. (You will author this in Exercise 2.)
- `/deploy-check` — read-only pre-deployment validation. (You will author this in Exercise 3.)

For decisions about when to use plan mode vs. direct execution on this codebase, you will produce a team decision doc in Exercise 4.
