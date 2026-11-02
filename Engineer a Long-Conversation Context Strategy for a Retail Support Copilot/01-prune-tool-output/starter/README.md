# Retail Customer Support Context Strategy

**Course:** Claude Certified Architect — Foundations / Course 1, Harness Engineering
**Module:** 2 — Context Engineering Foundations
**Status:** Starter scaffold — all stubbed sections implemented (reference solution in `../solution/`)
**Build:** Python 3.11+, `anthropic` SDK, runs in Docker with `$ANTHROPIC_API_KEY`

This is the starter scaffold — every stubbed section is now filled in; the reference solution lives in `../solution/`. The system designs a context-management strategy for a 48-turn retail customer-support conversation that spans three issues — a refund inquiry (resolved), a subscription cancellation (resolved), and a payment-method update (active). The raw transcript is ~35,000 tokens; the assembled context is **the project's measurable output**, recorded in `runs/<run_id>/context.md` alongside `budget.json` (token accounting) and `eval.jsonl` (evaluation results against the compressed context).

The defining architectural choice is **application-side context engineering**: the harness owns the assembly, compression, and pruning decisions, not the model. This is the pattern to apply for context engineering ("trim verbose tool outputs … *before they accumulate in context*"). The cookbook labs demonstrate the *server-side* counterpart (`clear_tool_uses_20250919`, `compact_20260112`) — see "What I'd do next" below for the contrast.

---

## Context-window anatomy

```
┌────────────────────────────────────────────────────────┐
│ Layer 5  System prompt                                 │  set at session start
├────────────────────────────────────────────────────────┤
│ Layer 4  CLAUDE.md  (project + user + directory)       │  walked once at boot
├────────────────────────────────────────────────────────┤
│ Layer 3  Memory / scratchpad files                     │  loaded on demand
├────────────────────────────────────────────────────────┤
│ Layer 2  Conversation history  <== THIS PROJECT        │  appended each turn
├────────────────────────────────────────────────────────┤
│ Layer 1  Current turn                                  │  the user's new message
└────────────────────────────────────────────────────────┘
```

This project operates on **Layer 2**, the conversation history. Everything in `runs/<run_id>/context.md` is a rendering of that layer: the `# Case Facts` block, the two `# Resolved: ...` summaries and the `# Active issue: ...` verbatim turns. We do not write CLAUDE.md or memory files; the strategy below decides what survives compression and where it sits inside the history block.

## Why this layout?

The assembled context places **case facts at the top boundary**, **resolved-issue summaries in the compressible middle** and **the active issue verbatim at the bottom boundary**, directly above the new user turn. (a) *Lost in the middle*: models attend best to the start and end of a long input, so the decision-load-bearing content (identifiers in the case facts, the live turn-by-turn conversation) sits at the boundaries and the resolved narrative takes the lower-attention middle. (b) *Resolved vs active fidelity*: for resolved issues the facts that matter have stabilized (amounts, IDs, statuses, dates) and condense without loss, while the active issue is still being worked out, so every turn stays byte-exact. (c) *The pass-complete-history baseline*: the standard guidance is to send the full conversation history to preserve coherence; this project deviates from that only for resolved threads, where coherence is no longer load-bearing, and the case-facts block (the "scratchpad" in other write-ups) keeps compression from dropping a fact the agent needs later.

## Before / after token budget

Token-counting methodology: **Anthropic `messages.count_tokens` endpoint** (model-authoritative) when `ANTHROPIC_API_KEY` is set, otherwise a documented `len(text) / 3.8` heuristic. Both paths go through the single canonical `retail_context.tokens.count` function, and `tokens.methodology()` records the active one in `budget.json`.

The table below is the course reference run, `runs/20260519-124910/budget.json` (Haiku 4.5, heuristic counter); `python -m retail_context.run --build` regenerates it (expect a few percent of drift if the Anthropic endpoint is used).

| Section | Tokens |
|---|---:|
| `case_facts` | 149 |
| `resolved_refund` | 296 |
| `resolved_subscription` | 365 |
| `active` (verbatim) | 19,538 |
| **Assembled total** | **20,350** |
| Baseline transcript | 47,144 |
| **Reduction vs baseline** | **56.83%** |

The active segment is about 96% of the assembled context by design; compression recovers roughly 27,000 tokens, all from the two resolved segments and the case-facts distillation.

## Eval results

Six questions span all three issues. Pass threshold ≥ 5/6 against the assembled context. A control variant strips the case-facts block; at least one of Q1/Q6 must fail in the control, proving the block carries information the summaries don't.

From `runs/20260519-124910/eval.jsonl`:

| # | Question (source) | Result | Model answer (excerpt) |
|---|---|:-:|---|
| Q1 | Actual refund amount for ORD-77310? (case facts) | ✅ | "...processed for order ORD-77310 was **$22.14**..." |
| Q2 | Why did the customer cancel their subscription? (subscription summary) | ✅ | "...due to a **duplicate charge**..." |
| Q3 | Failure code on the current payment-method update? (active verbatim) | ✅ | "...is **AVS_MISMATCH**..." |
| Q4 | Last-4 of the new card the customer is trying to add? (active verbatim) | ✅ | "...are **7782**..." |
| Q5 | Did the customer receive their subscription proration refund? (subscription summary) | ✅ | "...not yet... processed and initiated, but not yet received..." |
| Q6 | Structured status of the payment-method update issue? (case facts) | ✅ | "...the structured status token... is `in_progress`..." |
|   | **Total** | **6/6** |   |

**Control variant** (case-facts block stripped, Q1 + Q6 only):

| # | Result | Notes |
|---|:-:|---|
| Q1 | ✅ (unexpected pass) | The refund summary preserved `$22.14` verbatim, so the answer is still recoverable without the case-facts block. |
| Q6 | ❌ (expected fail) | The structured token `in_progress` appears only in the case-facts block; the active verbatim describes the state in prose ("still trying to figure out...") but never uses the snake_case status token. This is the strict load-bearing demonstration. |

The mixed control result is honest about how compression works in practice: when the summarizer preserves a numeric value (Q1), the case-facts block becomes a *cheaper* path to the same answer rather than the *only* path. Q6 demonstrates the strict case — case-facts is the only source of structured tokens.

See [`runs/20260519-124910/eval.jsonl`](runs/20260519-124910/eval.jsonl) and [`eval_control.jsonl`](runs/20260519-124910/eval_control.jsonl) for raw model answers.

## Quickstart

```bash
export ANTHROPIC_API_KEY=<your-key>

# Build the assembled context + run all evals + control:
python -m retail_context.run --all

# Build the assembled context only (no eval calls):
python -m retail_context.run --build

# Try a stronger summarization model:
python -m retail_context.run --all --model claude-sonnet-4-6
```

Artifacts land in `runs/<run_id>/`:
- `context.md`         — the assembled context (read this first)
- `budget.json`        — token accounting + methodology
- `case_facts_call.json` — LLM call log for case-facts extraction
- `eval.jsonl`         — per-question results
- `eval_control.jsonl` — control variant (Q1, Q6 with case facts stripped)

## What I'd do next

- **Session resumption** — when the same customer returns 4 hours later, do we reload the verbatim active segment or re-extract case facts and start fresh? The case-facts block is the right *durable* artifact to carry across `--resume`; the verbatim active section becomes stale (tool results referenced by turn-id may have expired in the backend).

- **Server-side context editing** is the modern API-level alternative this project deliberately does not use. The Anthropic Messages API exposes:
  - **`clear_tool_uses_20250919`** (beta `context-management-2025-06-27`) — drops stale tool-result blocks server-side, transparent to the model. Preferable to this project's `pruner.py` when the *whole tool result* can be dropped (vs preserving 5 of 40 fields).
  - **`compact_20260112`** (beta `compact-2026-01-12`) — server-side rolling compression of old turns. Preferable to this project's resolved-segment summarizer when the cutoff between "compressible" and "not" is *temporal* rather than *issue-based*.
  Application-side pruning (this project) wins when (a) the field-level keep-set is decision-specific, (b) the resolved-vs-active boundary is semantic, not chronological, or (c) you need the auditable artifact (`context.md`) for compliance review. Server-side editing wins on simplicity and zero application-layer state.

- **"Lost in the middle" negative variant** — re-run eval against an assembled context where the case-facts block is placed in the middle instead of the top. If Q1 and Q6 degrade, the position effect is empirically demonstrated, not just diagrammed.

- **Summarize the active segment too** — a stand-out experiment that demonstrates the fidelity-loss the verbatim choice avoids. Run Q3 and Q4 against a context where the active segment was *also* run through the compressor.

---

## Repo layout

```
module-02-retail-context-strategy/
├── pyproject.toml
├── README.md
├── retail_context/
│   ├── __init__.py
│   ├── __main__.py
│   ├── client.py               # Claude API + Claude Code CLI fallback
│   ├── tokens.py               # canonical token-count function
│   ├── transcript.py           # loader + segmentation
│   ├── case_facts.py           # extraction into persistent block
│   ├── pruner.py               # deterministic tool-output pruning
│   ├── compressor.py           # resolved-segment summarization
│   ├── assemble.py             # position-aware assembly
│   ├── evaluate.py             # eval-question runner
│   ├── run.py                  # CLI entry point
│   └── prompts/
│       └── compression_prompt.md
├── data/
│   ├── transcript_48turns.json     # 48-turn fixture, 3 issues
│   ├── lookup_order_response.json  # 57-field tool response fixture
│   └── eval_questions.json
├── scripts/
│   └── generate_transcript.py      # one-shot fixture authoring (Sonnet 4.6)
├── tests/
│   ├── test_transcript.py
│   ├── test_pruner.py
│   ├── test_assemble.py
│   └── test_antipatterns.py
└── runs/
    └── <run_id>/
        ├── context.md
        ├── budget.json
        ├── case_facts_call.json
        ├── eval.jsonl
        └── eval_control.jsonl
```
