"""Deterministic tool-output pruning for the verbose `lookup_order` response.

The "Tool Context Pruning" pattern: application-side filtering
of a verbose tool result so only the fields needed for the immediate decision survive
into context. For return/refund reasoning, exactly five fields matter — order identity,
when it was placed, what it cost, whether it shipped, and the return-window deadline.

Why each kept field is the only one that matters for return/refund reasoning:
  - order_id: identifies which order the refund or return decision applies to.
  - order_date: anchors when the order was placed, which the return window is measured from.
  - order_total_usd: caps the maximum refund amount the agent can authorize.
  - fulfillment_status: determines whether the request is a return (already delivered) or a cancellation (not yet shipped).
  - return_eligible_until: the deadline the agent must check before approving a return.

Implementation: deterministic field selection (no LLM call). The pruner has no
`anthropic` import — enforced by an AST audit.
"""
from __future__ import annotations

# The 5 fields: order_id, order_date, order_total_usd, fulfillment_status,
# return_eligible_until — chosen because they are the *only* fields needed for
# the agent's return/refund decision.
KEPT_FIELDS: tuple[str, ...] = (
    "order_id",
    "order_date",
    "order_total_usd",
    "fulfillment_status",
    "return_eligible_until",
)


class PrunerMissingFieldError(KeyError):
    """Raised when the raw tool response is missing one of the required kept fields."""


def prune_lookup_order(raw: dict) -> dict:
    # Deterministic field selection.
    #
    # 1. Check that every name in KEPT_FIELDS is present as a key in `raw`.
    #    If any are missing, raise PrunerMissingFieldError with a message
    #    that lists the missing field names — the agent needs to *notice*
    #    the upstream tool returned an incomplete record, not silently
    #    propagate it.
    #
    # 2. Return a new dict containing exactly the KEPT_FIELDS, in their
    #    declaration order. (Preserving the order is part of the contract;
    #    tests/test_pruner.py asserts on it.)
    #
    # Do NOT add an `anthropic` import here — the pruner is deterministic by
    # design. The AST audit will flag any LLM-driven implementation.
    missing = [field for field in KEPT_FIELDS if field not in raw]
    if missing:
        raise PrunerMissingFieldError(f"lookup_order response missing required fields: {missing}")
    return {field: raw[field] for field in KEPT_FIELDS}
