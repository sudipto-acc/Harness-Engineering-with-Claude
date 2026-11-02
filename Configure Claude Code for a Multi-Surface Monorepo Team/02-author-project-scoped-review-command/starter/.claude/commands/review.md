---
description: Review a PR diff against this repo's conventions and report findings
argument-hint: "<pr-ref|diff-range|file-path>"
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git show:*)
  - Bash(gh pr diff:*)
  - Bash(gh pr view:*)
  - Bash(gh pr checks:*)
---

# /review — team PR review

You are reviewing the diff identified by `$ARGUMENTS` against this repository's conventions. Apply the path-scoped rules in `.claude/rules/` (they auto-load based on the files touched) and the shared standards in `.claude/standards/`.

## Phase 1 — Interview pattern

Before reporting any findings, ask the author a clarifying question whenever intent is
genuinely ambiguous. Reporting a confidently-wrong verdict on an ambiguous change is
worse than asking — e.g. flagging "no test coverage" on a refactor that is already
covered by an upstream test forces the author to argue against a finding that was
never true. Interview first in at least these cases:

- A dependency change (`package.json` or `pyproject.toml` diff) with no explanation of why the new dependency is needed.
- A public API response shape change or a DB column change with no corresponding migration or client update in the diff.
- A refactor that touches production code but has no corresponding test changes — ask whether coverage already exists upstream before flagging it as missing.
- A change that touches multiple surfaces at once (API + components + DB) — ask which surface is the primary intent before reviewing the rest as side effects.

## Phase 2 — Review criteria

Must-report and skip are both explicit so two teammates running this command on the
same PR reach the same verdict.

**Must report:**
- Bugs: logic errors, missing `await`, race conditions, off-by-one errors.
- Security: raw SQL built from user input, missing auth checks, secrets committed in code, `dangerouslySetInnerHTML`.
- Convention violations caught by the path-scoped rules in `.claude/rules/` or the shared standards in `.claude/standards/`.
- Breaking changes: removed/renamed public API fields, incompatible DB migrations.
- Migration safety: a migration that is not backward-compatible with the currently deployed code.

**Skip (do not report):**
- Minor formatting — Prettier already handles it.
- Naming bikeshedding when the existing name is clear enough.
- Personal stylistic preferences not encoded in any rule or standard file.
- TODO/FIXME comments that already reference a tracked ticket.

The skip list exists because false positives are what destroy author trust in this command.

## Phase 3 — Bundling: interacting vs. independent findings

**Interacting findings** overlap or share a fix — bundle them into a single message
with all the context the author needs, because fixing one line affects the others.
Example: a missing `await` and a missing transaction wrapper on the same function are
interacting — the fix touches both at once.

**Independent findings** live in separate functions or files and share no common fix —
report them separately, one at a time, as discrete items, so each piece of feedback
stays actionable on its own.

Heuristic: if fixing finding A would change the code that finding B references, they
are interacting and should be bundled; otherwise report them independently and
separately.

## Phase 4 — Output format

For each finding, produce:

```
[severity] path/to/file.ts:line
finding: <one-sentence description>
fix: <one-sentence recommendation>
```

Severity is `bug` | `security` | `convention` | `breaking`. End with a one-line verdict: `approve`, `comment`, or `request-changes`.

## Examples

### Example 1 — Independent findings

Input:
```
diff --git a/src/api/orders/getOrder.ts b/src/api/orders/getOrder.ts
+ export async function getOrder(req: ApiRequest): Promise<ApiResponse> {
+   const order = await db.query(`SELECT * FROM orders WHERE id = ${req.params.id}`);
+   if (!order) return { status: 404 };
+   return { status: 200, body: order };
+ }
```

Output:
```
[security] src/api/orders/getOrder.ts:2
finding: Raw SQL interpolates `req.params.id` directly into the query string.
fix: Use a parameterized query via the repository-pattern module instead of string interpolation.

[convention] src/api/orders/getOrder.ts:3
finding: Handler returns `{ status: 404 }` directly instead of throwing `ApiError(404, ...)`.
fix: Throw `ApiError(404, "not_found", ...)` so the middleware produces the structured response.

verdict: request-changes
```

These two findings are independent — the SQL fix and the error-type fix touch
different lines and neither fix changes the other — so they are reported as
separate items.

### Example 2 — Interacting findings

Input:
```
diff --git a/src/api/orders/refundOrder.ts b/src/api/orders/refundOrder.ts
+ export async function refundOrder(req: ApiRequest): Promise<ApiResponse> {
+   paymentService.refund(req.body.orderId);
+   db.repositories.orders.markRefunded(req.body.orderId);
+   return { status: 200 };
+ }
```

Output:
```
[bug] src/api/orders/refundOrder.ts:2-4
finding: `paymentService.refund` and `markRefunded` are both missing `await`, they run
  with no transaction wrapper, and the DB write is ordered before confirming the
  payment refund succeeded — if the refund call fails, the order is already marked
  refunded.
fix: `await` both calls, wrap them in a DB transaction, and only call `markRefunded`
  after `paymentService.refund` resolves successfully.

verdict: request-changes
```

These three issues are interacting — fixing the ordering and the transaction wrapper
changes the same three lines, so they are bundled into one finding rather than
reported separately.

## Notes

- This command is project-scoped (`.claude/commands/review.md`) so everyone on the team gets the same review. If you want to layer personal preferences (e.g. a stricter accessibility check on your own PRs), put a `~/.claude/commands/review-strict.md` in your home directory — it will not affect teammates.
- If a finding requires running code or modifying files to verify, ask the author to run a specific check rather than attempting it from the review session. This command's `allowed-tools` are read-only by design.
