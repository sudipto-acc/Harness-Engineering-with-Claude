---
description: Conventions for Node.js API handler files
paths:
  - "src/api/**/*"
---

# API handler rules

Loads when editing any file under `src/api/`.

## Handler signature

- Every handler exported from `src/api/` matches the shape `async (req: ApiRequest) => ApiResponse` — no extra positional arguments, no `(req, res)` Express-style signatures.
- Handlers never import from `src/db/` directly. Go through the repository-pattern module (`src/db/repositories/*`) so the data-access boundary stays enforceable in one place.
- One handler per file, named after the route it serves (`createOrder.ts` exports `createOrder`).

## Error typing

- Only `ApiError(status, code, message)` may cross a handler boundary. If you catch a lower-level error (e.g. a Postgres error), rethrow it as an `ApiError` with a code specific enough for the client to act on — do not pass the raw driver error through.
- Do not add a bare `catch {}` that swallows an error silently; every catch block either rethrows as `ApiError` or logs with the request id attached.
- Validation errors use `ApiError(400, "validation_error", ...)` consistently — do not invent a new code per handler.

## Schemas

- When a handler's request or response shape changes, update the matching file in `src/api/_schemas/` in the same change — a handler and its schema must never drift.
- Parse the request body through the `zod` schema before touching `req.body` directly; never read a field off the raw body.

## Forbidden

- Direct `fetch`/`axios` calls to other internal services from inside a handler — route through the shared `src/api/_clients/` wrapper so retries and timeouts stay consistent.
- Mutating `req` or attaching ad hoc properties to it for downstream middleware to read.
