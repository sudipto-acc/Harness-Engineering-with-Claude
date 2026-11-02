# Plan mode vs. direct execution — team decision guide

Choosing between Claude Code's **plan mode** (investigate and propose before changing anything) and **direct execution** (change code immediately) is the single biggest leverage point in how the team uses the harness day-to-day. The wrong mode at either extreme costs us: plan mode for trivial fixes is friction; direct execution for architectural changes burns context and produces rework.

> **Knight-Webb, "SWE Is Becoming Plan and Review"** — anchor talk cited in the Module 8
> curriculum doc's anchor-talks table. The throughline: as agentic coding tools get more
> capable, more of the software engineer's day shifts from writing code to planning and
> reviewing it before committing to an approach.

This doc walks four concrete decisions against our codebase: one plan-mode example, one direct-execution example, one Explore-subagent example, and one combined-workflow example.

---

## 1. Plan-mode example

**Task:** Extract a shared `useCart(userId)` hook out of three components that each
duplicate the same cart-fetching and total-calculation logic: `src/components/Cart/Cart.tsx`,
`src/components/Checkout/Checkout.tsx`, and `src/components/MiniCart/MiniCart.tsx`.

**Why plan mode:** This is a large-scale, multi-file modification with more than one
valid approach (where the new hook lives, what its return shape is, whether to migrate
all three call sites in one pass or stage them) — exactly the architectural-decision
shape Task 3.4 calls out for plan mode. Investigating the three components' duplicated
logic and proposing a shared hook shape before touching any file prevents costly
rework: if the hook's signature were wrong, we would otherwise discover that only after
editing all three call sites.

**Flow:** Claude reads all three components, proposes a new hook (a prose target — the
file does not exist yet, so we don't reference it in backticks) and the call-site diff
for each of the three existing files; you review and approve the plan; direct execution
then applies it across all three files in one pass.

---

## 2. Direct-execution example

**Task:** Add a `min: 0` validation to the `quantity` field in `src/api/_schemas/orders.ts`.

**Why direct execution:** This is a simple, well-scoped change confined to one function
— the order-schema validator — matching Task 3.4's guidance that direct execution fits
simple, well-scoped changes. You already know what the diff looks like before invoking
Claude: add a `.min(0)` constraint to the existing `quantity` field. If you can describe
the change in one sentence and predict the patch, skip planning and go straight to
direct execution.

---

## 3. Explore-subagent example

**Task:** Find every call site of `processRefund` before deciding how to change its
signature. The call sites live in `src/api/orders/refund.ts`, `src/api/billing/issue.ts`,
and `src/services/payment.ts`.

**Why Explore subagent:** This is a discovery task per Task 3.4 — isolating verbose
discovery output (file reads, grep hits, false-positive matches) out of the main
conversation and returning only a summary. Let the Explore subagent walk the codebase
and write its running inventory to a scratchpad file (the scratchpad pattern from the
Architect's Playbook) — e.g. a working-notes file under `tmp/` — so the call-site list
survives even if the subagent's own context window fills up, and only the final summary
returns to the main session.

---

## 4. Combined workflow — plan mode for investigation, then direct execution

**Task:** Rename `ordersRepo.findById` to `ordersRepo.getById` in `src/db/orders.ts` to
align with the team's naming convention (`get*` for single-row reads, `find*` for
multi-row reads).

**Why a combined workflow:** Task 3.4 describes combining plan mode for investigation
with direct execution for implementation. We don't yet know every call site of
`findById`, and some lookups could be constructed dynamically in ways a plain grep would
miss — that uncertainty is exactly what plan mode is for. Once the call-site list is
known, the rename itself is mechanical keystrokes: direct execution.

**Flow:**
1. Plan mode investigates `src/db/orders.ts` and its callers, and proposes the rename
   plus the full list of call sites to update.
2. You review and approve the plan.
3. Direct execution applies the rename across every call site and runs the test suite.

---

## Quick reference

| Situation | Mode |
|-----------|------|
| Single function, fix is obvious, you can predict the diff | Direct execution |
| Multi-file refactor, API shape is debatable | Plan mode |
| Discovery / inventory across the codebase, you'll throw away the intermediate steps | Explore subagent |
| Investigation-then-mechanical-change | Plan mode → direct execution |
| Architectural decision (which database, which queue) | Plan mode, possibly with a fork to compare options |

When in doubt: plan mode is recoverable (you can switch to execution), but direct execution on a complex change is not. Default to plan when uncertain.
