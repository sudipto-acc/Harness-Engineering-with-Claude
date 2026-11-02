---
description: Conventions for co-located test files across the React and API trees
paths:
  - "**/*.test.tsx"
  - "**/*.test.ts"
---

# Test file rules

Loads when editing any co-located test file (`*.test.ts` / `*.test.tsx`), layering on
top of whichever directory rule (`react.md` or `api.md`) also matches the file under test.

## Assertions

- Use the project's `expect(...)` matcher library consistently — no mixing in `assert` from `node:assert` inside the same test file.
- Assert on behavior (return value, thrown `ApiError`, rendered text) rather than implementation details like internal state or private function calls.
- One behavior per `it(...)` block — if a test needs "and" to describe it, split it into two.

## Test data

- Build fixtures through the shared `*.factory.ts` builders under `src/**/__fixtures__/`, not ad hoc inline object literals repeated across tests.
- Name factory overrides for the specific thing the test is exercising, e.g. `buildOrder({ status: "refunded" })`, not a copy-pasted full object literal.

## Forbidden

- No snapshot tests (`toMatchSnapshot()`) — they drift silently and stop encoding intent.
- No real `setTimeout`/`sleep` to wait for async work; await the promise or use the test runner's fake timers.
- No mocking the database layer directly — mock the repository-pattern module (`src/db/repositories/*`) instead so the contract stays honest.
- No `describe.only`/`it.only` left in committed test files — they silently skip the rest of the suite in CI.
