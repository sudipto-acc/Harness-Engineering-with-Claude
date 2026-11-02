"""Case-facts extraction into a persistent block at the top of context.

Extraction is LLM-driven: one Claude call against the full transcript that returns
strict JSON for the 12 required fields. This is commonly called a *scratchpad* — same
concept, different word: a dense structured block that survives compression and is
placed at the top boundary of context so the model can recover transactional facts
without scanning thousands of tokens of narrative.

Missing-field behavior raises `CaseFactExtractionError` listing the gaps — silent
null-fill is forbidden.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from retail_context.client import complete_with_system, get_model
from retail_context.transcript import Transcript

# The 12-field contract for the case-facts block.
# Order matters — the to_markdown() rendering uses this order so the block is
# reviewer-readable and the model can re-find a value by name. Each name appears
# verbatim in the extraction system prompt as the JSON key the LLM must return.
#
# Required fields (12 total): customer_id; refund_order_id, refund_amount_usd,
# refund_status; subscription_id, subscription_plan, subscription_cancel_reason,
# subscription_status; active_payment_method_last4, new_payment_method_last4,
# payment_update_failure_code, payment_update_status.
REQUIRED_FIELDS: tuple[str, ...] = (
    "customer_id",
    "refund_order_id",
    "refund_amount_usd",
    "refund_status",
    "subscription_id",
    "subscription_plan",
    "subscription_cancel_reason",
    "subscription_status",
    "active_payment_method_last4",
    "new_payment_method_last4",
    "payment_update_failure_code",
    "payment_update_status",
)


# A dataclass that carries the 12 fields above
# with explicit Python types (str for IDs / status tokens / last4 strings,
# float for refund_amount_usd). Then implement to_markdown(self) -> str so the
# block renders with a level-1 `# Case Facts` header and the three subgroups
# (Customer / Refund (resolved) / Subscription (resolved) / Payment update
# (active)) as bold inline labels. The rendering is part of the contract:
# fixed key order, Markdown headers, reviewer-readable.
@dataclass
class CaseFacts:
    customer_id: str
    refund_order_id: str
    refund_amount_usd: float
    refund_status: str
    subscription_id: str
    subscription_plan: str
    subscription_cancel_reason: str
    subscription_status: str
    active_payment_method_last4: str
    new_payment_method_last4: str
    payment_update_failure_code: str
    payment_update_status: str

    def to_markdown(self) -> str:
        return (
            "# Case Facts\n\n"
            "**Customer.**\n"
            f"- `customer_id`: {self.customer_id}\n\n"
            "**Refund (resolved).**\n"
            f"- `refund_order_id`: {self.refund_order_id}\n"
            f"- `refund_amount_usd`: ${self.refund_amount_usd:.2f}\n"
            f"- `refund_status`: {self.refund_status}\n\n"
            "**Subscription (resolved).**\n"
            f"- `subscription_id`: {self.subscription_id}\n"
            f"- `subscription_plan`: {self.subscription_plan}\n"
            f"- `subscription_cancel_reason`: {self.subscription_cancel_reason}\n"
            f"- `subscription_status`: {self.subscription_status}\n\n"
            "**Payment update (active).**\n"
            f"- `active_payment_method_last4`: {self.active_payment_method_last4}\n"
            f"- `new_payment_method_last4`: {self.new_payment_method_last4}\n"
            f"- `payment_update_failure_code`: {self.payment_update_failure_code}\n"
            f"- `payment_update_status`: {self.payment_update_status}\n"
        )


class CaseFactExtractionError(ValueError):
    def __init__(self, missing: list[str], raw: dict[str, Any]):
        super().__init__(f"case-facts extraction missing required fields: {missing}")
        self.missing = missing
        self.raw = raw


# The system prompt that drives the extraction.
# The prompt must require Claude to return EXACTLY one JSON object with the
# 12 REQUIRED_FIELDS as keys, with the right types (refund_amount_usd is a
# number, last4 are zero-padded strings, status tokens preserved verbatim).
# Missing fields are null — DO NOT invent. Output is JSON only — no prose,
# no markdown, no code fences. The prompt is reviewed for its strict-schema
# intent; the reviewer reads it to decide whether following it would reliably
# produce a parseable JSON with every required field.
_SYSTEM_PROMPT = """You are extracting structured transactional facts from a long customer-support
transcript. The transcript spans three issues for the same customer at the fictional
retailer "Pantry Plus": a refund inquiry (resolved), a subscription cancellation
(resolved), and an in-progress payment-method update (active).

Return ONE JSON object with EXACTLY these keys and types:

  customer_id                  : string         (e.g., "CUST-88421")
  refund_order_id              : string         (e.g., "ORD-77310")
  refund_amount_usd            : number         (e.g., 48.99 — numeric, not "$48.99")
  refund_status                : string         (e.g., "processed")
  subscription_id              : string         (e.g., "SUB-22119")
  subscription_plan            : string         (e.g., "Pantry Plus Monthly")
  subscription_cancel_reason   : string         (e.g., "duplicate_charge")
  subscription_status          : string         (e.g., "cancelled_with_prorated_refund")
  active_payment_method_last4  : string         (e.g., "4242" — keep leading zeros if any)
  new_payment_method_last4     : string         (e.g., "7782")
  payment_update_failure_code  : string         (e.g., "AVS_MISMATCH")
  payment_update_status        : string         (e.g., "in_progress")

Rules:
- Every field is required. If a field cannot be located in the transcript, set it to
  the JSON value null — DO NOT invent.
- Preserve identifiers verbatim. Preserve `last4` values as zero-padded strings.
- Preserve status tokens verbatim (snake_case strings exactly as they appear in the
  transcript or system).
- `refund_amount_usd` is a number (48.99), not a string. Strip "$".
- Output ONLY the JSON object. No prose, no markdown, no code fences."""


def _parse_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.rstrip().endswith("```"):
            raw = raw.rsplit("```", 1)[0]
    return json.loads(raw)


def extract(
    transcript: Transcript,
    *,
    model: str | None = None,
    log_path: Path | None = None,
) -> CaseFacts:
    # Runs the extraction call and validates the result.
    #
    # 1. Build the user message: f"Transcript:\n\n{transcript.full_text}".
    #
    # 2. Call complete_with_system(_SYSTEM_PROMPT, user, model=model,
    #    max_tokens=2048). It returns (text, input_tokens, output_tokens).
    #
    # 3. Parse the response text with _parse_json (handles a stray ``` fence).
    #
    # 4. If a `log_path` was given, write a JSON log containing the model
    #    name, the input/output token counts, and the raw parsed dict. This
    #    is the `case_facts_call.json` artifact the reviewer audits.
    #
    # 5. Validate that every name in REQUIRED_FIELDS is present in the parsed
    #    dict and is not None and not the empty string. If anything is
    #    missing, raise CaseFactExtractionError(missing=..., raw=...) — DO
    #    NOT silently fill with null.
    #
    # 6. Construct and return a CaseFacts. Cast types explicitly:
    #    str(...) for ID/status fields, float(...) for refund_amount_usd.
    user = f"Transcript:\n\n{transcript.full_text}"
    text, in_tok, out_tok = complete_with_system(
        _SYSTEM_PROMPT, user, model=model, max_tokens=2048
    )
    raw = _parse_json(text)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            json.dumps(
                {
                    "model": model or get_model(),
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "raw_output": raw,
                },
                indent=2,
            )
        )

    missing = [
        f for f in REQUIRED_FIELDS if f not in raw or raw[f] is None or raw[f] == ""
    ]
    if missing:
        raise CaseFactExtractionError(missing=missing, raw=raw)

    return CaseFacts(
        customer_id=str(raw["customer_id"]),
        refund_order_id=str(raw["refund_order_id"]),
        refund_amount_usd=float(raw["refund_amount_usd"]),
        refund_status=str(raw["refund_status"]),
        subscription_id=str(raw["subscription_id"]),
        subscription_plan=str(raw["subscription_plan"]),
        subscription_cancel_reason=str(raw["subscription_cancel_reason"]),
        subscription_status=str(raw["subscription_status"]),
        active_payment_method_last4=str(raw["active_payment_method_last4"]),
        new_payment_method_last4=str(raw["new_payment_method_last4"]),
        payment_update_failure_code=str(raw["payment_update_failure_code"]),
        payment_update_status=str(raw["payment_update_status"]),
    )


def to_dict(facts: CaseFacts) -> dict[str, Any]:
    return asdict(facts)
