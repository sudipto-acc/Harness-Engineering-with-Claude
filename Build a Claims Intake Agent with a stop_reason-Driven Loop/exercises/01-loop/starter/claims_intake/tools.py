"""Tool schemas and dispatcher.

Seven tools, registered with Anthropic tool-use shape. The dispatcher returns
serialized JSON strings to be wrapped as `tool_result` content. Errors follow
the Playbook "Graceful Tool Failure" shape:

    {"is_error": true,
     "error_category": "transient"|"permanent",
     "is_retryable": bool,
     "message": "..."}

Errors are never raised to the loop.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from claims_intake.session import ClaimSession

CLAIM_TYPES = ["property_damage", "theft", "liability", "auto"]
SEVERITIES = ["low", "medium", "high"]

# ----------------------------------------------------------------------------
# Schemas — passed verbatim to the Anthropic Messages API as the `tools` arg.
# ----------------------------------------------------------------------------

# TOOL_SCHEMAS holds every tool schema. Each schema
# is a dict with "name", "description", and "input_schema". Tool descriptions are read by
# the model on every turn — write them as if you were teaching the model what each tool is
# for and *when* to call it. Categorical fields ("claim_type", "severity") must use
# Anthropic's tool-use `enum` shape against CLAIM_TYPES and SEVERITIES.
#
#   - lookup_policy(policy_id: str)
#     Returns the policy record. Used early in the conversation.
#   - record_claim_fact(field: str, value: str)
#     Records one normalized fact (incident_date, location, items_lost, ...).
#   - classify_claim(claim_type: enum CLAIM_TYPES, confidence: number in [0,1], rationale: str)
#     Commits the model to a claim type with a confidence score.
#   - assess_severity(severity: enum SEVERITIES, rationale: str)
#     Commits the model to a severity bucket.
#
# The last three tools (request_clarification, route_to_adjuster, escalate_to_human) follow
# the same shape; the last two are terminal.
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "lookup_policy",
        "description": (
            "Look up an insurance policy using its policy ID. "
            "Call this early in the claims intake process to retrieve "
            "the policy record before making routing decisions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "policy_id": {
                    "type": "string",
                    "description": "The claimant's insurance policy ID."
                }
            },
            "required": ["policy_id"],
            "additionalProperties": False
        }
    },
    {
        "name": "record_claim_fact",
        "description": (
            "Record one distinct, normalized fact about the claim. "
            "Call once for each new fact as information arrives. "
            "Examples of fields include incident_date, location, "
            "items_lost, damage_description, estimated_loss, and injuries. "
            "Do not record duplicate facts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "description": "The normalized name of the claim fact."
                },
                "value": {
                    "type": "string",
                    "description": "The value of the claim fact."
                }
            },
            "required": ["field", "value"],
            "additionalProperties": False
        }
    },
    {
        "name": "classify_claim",
        "description": (
            "Commit to exactly one claim category after gathering "
            "sufficient facts. Select the best-supported category and "
            "provide a confidence score between 0 and 1 and a rationale. "
            "Call exactly once."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_type": {
                    "type": "string",
                    "enum": CLAIM_TYPES,
                    "description": "The selected claim category."
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Confidence in the classification."
                },
                "rationale": {
                    "type": "string",
                    "description": "Why this claim category was selected."
                }
            },
            "required": ["claim_type", "confidence", "rationale"],
            "additionalProperties": False
        }
    },
    {
        "name": "assess_severity",
        "description": (
            "Commit to one severity level based on estimated financial "
            "loss, physical damage, injuries, and safety concerns. "
            "Call exactly once and explain the assessment."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": SEVERITIES,
                    "description": "The assessed claim severity."
                },
                "rationale": {
                    "type": "string",
                    "description": "Evidence supporting the severity."
                }
            },
            "required": ["severity", "rationale"],
            "additionalProperties": False
        }
    },
    {
        "name": "request_clarification",
        "description": (
            "Ask the claimant one focused question when information "
            "needed to distinguish between claim categories is missing. "
            "Specify at least two competing categories in ambiguity_between. "
            "Call only once per missing piece of information."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to ask the claimant."
                },
                "ambiguity_between": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": CLAIM_TYPES
                    },
                    "minItems": 2,
                    "description": "The competing claim categories."
                }
            },
            "required": ["question", "ambiguity_between"],
            "additionalProperties": False
        }
    },
    {
        "name": "route_to_adjuster",
        "description": (
            "Terminal action: route a sufficiently classified and assessed "
            "claim to an adjuster queue. Use only when classification "
            "confidence is at least 0.6 and severity has been assessed. "
            "Call exactly one terminal tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "queue": {
                    "type": "string",
                    "enum": CLAIM_TYPES,
                    "description": "The adjuster queue to receive the claim."
                },
                "claim_summary": {
                    "type": "string",
                    "description": "A concise summary of the claim."
                }
            },
            "required": ["queue", "claim_summary"],
            "additionalProperties": False
        }
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Terminal action: escalate a claim to a human reviewer when "
            "classification confidence is insufficient, severity cannot "
            "be established reliably, or safe routing is not possible. "
            "Provide a reason and all required structured summary fields. "
            "Call exactly one terminal tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why human intervention is required."
                },
                "structured_summary": {
                    "type": "object",
                    "properties": {
                        "policy_id": {"type": "string"},
                        "root_cause": {"type": "string"},
                        "candidate_claim_types": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": CLAIM_TYPES
                            }
                        },
                        "case_facts": {"type": "object"},
                        "recommended_action": {"type": "string"},
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1
                        }
                    },
                    "required": [
                        "policy_id",
                        "root_cause",
                        "candidate_claim_types",
                        "case_facts",
                        "recommended_action",
                        "confidence"
                    ],
                    "additionalProperties": False
                }
            },
            "required": ["reason", "structured_summary"],
            "additionalProperties": False
        }
    }
]

# ----------------------------------------------------------------------------
# Errors — Graceful Tool Failure shape
# ----------------------------------------------------------------------------

def _err(category: str, retryable: bool, message: str) -> str:
    return json.dumps({
        "is_error": True,
        "error_category": category,
        "is_retryable": retryable,
        "message": message
    })


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps(payload)


# ----------------------------------------------------------------------------
# Tool implementations
# ----------------------------------------------------------------------------


def _t_lookup_policy(session: ClaimSession, inp: dict[str, Any]) -> str:
    policy_id = inp.get("policy_id")

    if not isinstance(policy_id, str):
        return _err("permanent", False, "policy_id must be a string")

    policy = session.policies.get(policy_id)

    if policy is None:
        return _err(
            "permanent",
            False,
            f"Policy not found: {policy_id}"
        )

    return _ok(policy)


def _t_record_claim_fact(session: ClaimSession, inp: dict[str, Any]) -> str:
    field = inp.get("field")
    value = inp.get("value")

    if not isinstance(field, str) or not isinstance(value, str):
        return _err(
            "permanent",
            False,
            "Both field and value must be strings"
        )

    session.case_facts[field] = value

    return _ok({
        "recorded": True,
        "field": field,
        "case_facts_count": len(session.case_facts)
    })


def _t_classify_claim(session: ClaimSession, inp: dict[str, Any]) -> str:
    claim_type = inp.get("claim_type")
    confidence = inp.get("confidence")
    rationale = inp.get("rationale")

    if claim_type not in CLAIM_TYPES:
        return _err("permanent", False, "Invalid claim_type")

    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        return _err(
            "permanent",
            False,
            "confidence must be a number between 0 and 1"
        )

    if not isinstance(rationale, str):
        return _err("permanent", False, "rationale must be a string")

    session.classification = {
        "claim_type": claim_type,
        "confidence": confidence,
        "rationale": rationale
    }

    return _ok({
        **session.classification,
        "recorded": True
    })


def _t_assess_severity(session: ClaimSession, inp: dict[str, Any]) -> str:
    severity = inp.get("severity")
    rationale = inp.get("rationale")

    if severity not in SEVERITIES:
        return _err("permanent", False, "Invalid severity")

    if not isinstance(rationale, str):
        return _err("permanent", False, "rationale must be a string")

    session.severity = {
        "severity": severity,
        "rationale": rationale
    }

    return _ok({
        **session.severity,
        "recorded": True
    })


def _t_request_clarification(session: ClaimSession, inp: dict[str, Any]) -> str:
    question = inp.get("question")
    ambiguity_between = inp.get("ambiguity_between")

    if not isinstance(question, str):
        return _err("permanent", False, "question must be a string")

    if (
        not isinstance(ambiguity_between, list)
        or len(ambiguity_between) < 2
    ):
        return _err(
            "permanent",
            False,
            "ambiguity_between must be a list with at least 2 entries"
        )

    session.clarifications_asked.append({
        "question": question,
        "ambiguity_between": ambiguity_between
    })

    question_lower = question.lower()

    for key, reply in session.clarification_responses.items():
        if key.lower() in question_lower:
            return _ok({
                "claimant_reply": reply
            })

    return _ok({
        "claimant_reply": "NO_RESPONSE"
    })

def _get_run_dir(session: ClaimSession) -> Path:
    """
    Resolve the directory for the current run.

    Supports either a session.run_dir attribute or a session.run_id
    attribute.
    """
    run_dir = getattr(session, "run_dir", None)

    if run_dir is not None:
        return Path(run_dir)

    run_id = getattr(session, "run_id", None)

    if run_id is None:
        raise AttributeError(
            "ClaimSession must provide run_dir or run_id"
        )

    return Path("runs") / str(run_id)


def _t_route_to_adjuster(session: ClaimSession, inp: dict[str, Any]) -> str:
    if session.terminal_called:
        return _err(
            "permanent",
            False,
            "terminal tool already called for this claim"
        )

    queue = inp.get("queue")
    claim_summary = inp.get("claim_summary")

    if not isinstance(queue, str) or queue not in CLAIM_TYPES:
        return _err("permanent", False, "Invalid adjuster queue")

    if not isinstance(claim_summary, str):
        return _err(
            "permanent",
            False,
            "claim_summary must be a string"
        )

    if session.classification is None:
        return _err(
            "permanent",
            False,
            "classify_claim must be called before routing"
        )

    if session.severity is None:
        return _err(
            "permanent",
            False,
            "assess_severity must be called before routing"
        )

    classification = session.classification
    severity = session.severity

    record = {
        "claim_id": session.claim_id,
        "policy_id": session.policy_id,
        "claim_type": classification["claim_type"],
        "severity": severity["severity"],
        "confidence": classification["confidence"],
        "rationale": classification["rationale"],
        "claim_summary": claim_summary,
        "case_facts": dict(session.case_facts)
    }

    path = _get_run_dir(session) / "queues" / f"{queue}.jsonl"

    _append_jsonl(path, record)

    session.routing = record

    return _ok({
        "routed": True,
        "queue": queue
    })



def _t_escalate_to_human(session: ClaimSession, inp: dict[str, Any]) -> str:
    # Escalation terminal tool:
    #   1. Guard against double-terminal: if session.terminal_called, return an error.
    #   2. Validate inp["reason"] is a string and inp["structured_summary"] is a dict
    #      containing all required keys: policy_id, root_cause, candidate_claim_types,
    #      case_facts, recommended_action, confidence. Return an error listing any missing
    #      fields by name.
    #   3. Build the escalation record (claim_id, policy_id, reason, **structured_summary,
    #      case_facts_at_escalation) and assign it to session.escalation.
    #   4. Append it to runs/<run>/escalations.jsonl via _append_jsonl.
    #   5. Return _ok({"escalated": True}).
    if session.terminal_called:
        return _err(
            "permanent",
            False,
            "terminal tool already called for this claim"
        )

    reason = inp.get("reason")
    structured_summary = inp.get("structured_summary")

    if not isinstance(reason, str):
        return _err("permanent", False, "Invalid reason")

    if not isinstance(structured_summary, dict):
        return _err("permanent", False, "structured_summary must be an object")

    required_keys = [
        "policy_id",
        "root_cause",
        "candidate_claim_types",
        "case_facts",
        "recommended_action",
        "confidence"
    ]
    missing_keys = [key for key in required_keys if key not in structured_summary]
    if missing_keys:
        return _err("permanent", False, f"Missing structured_summary keys: {', '.join(missing_keys)}")

    record = {
        "claim_id": session.claim_id,
        "policy_id": session.policy_id,
        "reason": reason,
        **structured_summary,
        "case_facts_at_escalation": dict(session.case_facts)
    }

    path = _get_run_dir(session) / "escalations.jsonl"
    _append_jsonl(path, record)

    session.escalation = record

    return _ok({"escalated": True})



# ----------------------------------------------------------------------------
# Dispatcher
# ----------------------------------------------------------------------------


_DISPATCH = {
    "lookup_policy": _t_lookup_policy,
    "record_claim_fact": _t_record_claim_fact,
    "classify_claim": _t_classify_claim,
    "assess_severity": _t_assess_severity,
    "request_clarification": _t_request_clarification,
    "route_to_adjuster": _t_route_to_adjuster,
    "escalate_to_human": _t_escalate_to_human,
}


def make_executor(session: ClaimSession) -> Executor:
    """Return a ToolExecutor callable bound to this session."""

    def execute(name: str, tool_input: dict[str, Any]) -> str:
        handler = _DISPATCH.get(name)
        if handler is None:
            return _err("permanent", False, f"unknown tool: {name}")
        try:
            return handler(session, tool_input)
        except Exception as exc:
            # Defensive: anything raised inside a handler becomes a graceful error,
            # never crashes the loop.
            return _err("transient", True, f"{type(exc).__name__}: {exc}")

    return execute


# Type alias for clarity; the loop only sees a Callable.
Executor = Any


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
