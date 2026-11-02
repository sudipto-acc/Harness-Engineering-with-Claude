"""Three invocation shapes.

thin     — prompt only.
rich     — hot state + new defects.
resumed  — prior partial findings + new defects since the last manifest step.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from .state import HotState

InvocationShape = Literal["thin", "rich", "resumed"]


@dataclass(frozen=True)
class Invocation:
    shape: InvocationShape
    prompt: str


def thin(prompt: str) -> Invocation:
    # Return an Invocation with shape="thin" and the prompt unchanged.
    # The thin shape is for one-shot calls that don't need any project state.
    return Invocation(shape="thin", prompt=prompt)


def rich(
    role: str, hot_state: HotState, new_defects: Sequence[Mapping[str, Any]]
) -> Invocation:
    # Builds a rich prompt that includes:
    #   - A one-line role framing ("You are the on-call {role} for Northridge Plant 3.")
    #   - A "## Current hot state" section listing recent_defect_hashes,
    #     current_shift_summary, active_alerts, threshold_statuses.
    #   - A "## New defects since last shift" section enumerating each new defect
    #     (id / ts / shift / component / severity / description).
    #   - A trailing instruction asking for: Summary, Findings, Recommended
    #     actions, and an Updated hot state proposal as a JSON block.
    # Return an Invocation with shape="rich" and the rendered prompt.
    prompt_lines = [
        f"You are the on-call {role} for Northridge Plant 3.",
        "## Current hot state",
        f"- recent_defect_hashes: {hot_state.recent_defect_hashes}",
        f"- current_shift_summary: {hot_state.current_shift_summary}",
        f"- active_alerts: {hot_state.active_alerts}",
        f"- threshold_statuses: {hot_state.threshold_statuses}",
        "## New defects since last shift"
    ]
    if new_defects:
        for defect in new_defects:
            prompt_lines.append(
                f"- {defect['id']} / {defect['ts']} / {defect['shift']} / {defect['component']} / {defect['severity']} / {defect['description']}"
            )
    else:
        prompt_lines.append("- (none)")
    prompt_lines.append(
        "## Instructions\nSummary, Findings, Recommended actions, and Updated hot state proposal as a JSON block."
    )
    return Invocation(shape="rich", prompt="\n".join(prompt_lines))


def resumed(
    session_id: str,
    summary: str,
    latest_message: str,
    prior_steps: Sequence[Mapping[str, Any]],
    new_defects: Sequence[Mapping[str, Any]],
) -> Invocation:
    # Builds a resumed prompt with three required sections:
    #   - "## Prior partial findings" — one line per prior step, showing its
    #     `name` and a truncated representation of its `payload`.
    #   - "## Prior summary" — the supplied summary string.
    #   - "## New defects since last partial step" — enumerate new_defects
    #     (id / ts / component / severity / description), or "- (none)" if empty.
    # Close with the latest_message under "## Latest instruction".
    # Return an Invocation with shape="resumed".
    prompt_lines = [
        "## Prior partial findings"
    ]
    if prior_steps:
        for step in prior_steps:
            prompt_lines.append(f"- {step['name']}: {str(step['payload'])[:100]}")
    else:
        prompt_lines.append("- (none)")

    prompt_lines.append("## Prior summary")
    prompt_lines.append(summary)

    prompt_lines.append("## New defects since last partial step")
    if new_defects:
        for defect in new_defects:
            prompt_lines.append(
                f"- {defect['id']} / {defect['ts']} / {defect['component']} / {defect['severity']} / {defect['description']}"
            )
    else:
        prompt_lines.append("- (none)")

    prompt_lines.append("## Latest instruction")
    prompt_lines.append(latest_message)

    return Invocation(shape="resumed", prompt="\n".join(prompt_lines))
