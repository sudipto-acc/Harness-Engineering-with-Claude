"""Tiered compression: summarize resolved segments; preserve active verbatim.

Resolved segments are condensed by a single Claude call per segment using the
prompt template at `retail_context/prompts/compression_prompt.md`. The active
segment is **never** summarized — it is preserved byte-exact.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

from retail_context.client import complete_with_system
from retail_context.transcript import Segment, Transcript


@dataclass
class Summary:
    issue_id: str
    text: str
    input_tokens: int
    output_tokens: int


@dataclass
class Compressed:
    summaries: dict[str, Summary]
    active_text: str
    active_issue_id: str


def _load_prompt() -> str:
    return resources.files("retail_context.prompts").joinpath(
        "compression_prompt.md"
    ).read_text()


def summarize_segment(segment: Segment, *, model: str | None = None) -> Summary:
    # Summarizes ONE resolved segment via a single Claude call.
    #
    # 1. Guard. Refuse to summarize anything whose status is not "resolved".
    #    Raise ValueError naming the issue_id and status and stating explicitly
    #    that only resolved segments are compressed — the active segment must be
    #    preserved byte-exact.
    #
    # 2. Load the compression prompt template via _load_prompt(). This is the
    #    system message for the Claude call.
    #
    # 3. Build the user message naming the issue_id and turn range so the model
    #    knows where the segment sits in the transcript:
    #        f"Source segment — issue_id `{segment.issue_id}`, turns "
    #        f"{segment.turn_range[0]}-{segment.turn_range[1]}:\n\n{segment.text}"
    #
    # 4. Call complete_with_system(system, user, model=model, max_tokens=1024).
    #    It returns a (text, input_tokens, output_tokens) tuple.
    #
    # 5. Return a Summary carrying the issue_id, the response text (the
    #    structured summary), and the token counts.
    if segment.status != "resolved":
        raise ValueError(
            f"Refusing to summarize segment {segment.issue_id!r} with status {segment.status!r}."
            " Only resolved segments are compressed; the active segment is preserved verbatim."
        )
    system = _load_prompt()
    user = (
        f"Source segment — issue_id `{segment.issue_id}`, turns "
        f"{segment.turn_range[0]}-{segment.turn_range[1]}:\n\n{segment.text}"
    )
    text, in_tok, out_tok = complete_with_system(
        system, user, model=model, max_tokens=1024
    )
    return Summary(
        issue_id=segment.issue_id,
        text=text,
        input_tokens=in_tok,
        output_tokens=out_tok,
    )


def compress(transcript: Transcript, *, model: str | None = None) -> Compressed:
    # Orchestrates compression across all segments.
    #
    # For each segment in transcript.segments:
    #   - if segment.status == "resolved":
    #       call summarize_segment(segment, model=model) and store the result
    #       keyed by segment.issue_id in a dict[str, Summary].
    #   - if segment.status == "active":
    #       preserve byte-exact by rendering the raw turns:
    #           "\n\n".join(t.render() for t in segment.turns)
    #       Record the active_text and the active_issue_id.
    #
    # If no active segment is present in the transcript, raise RuntimeError
    # naming the missing-active condition — the assembled context requires
    # exactly one active segment at the bottom boundary.
    #
    # Return a Compressed carrying the summaries dict, the active_text, and
    # the active_issue_id.
    summaries: dict[str, Summary] = {}
    active_text = ""
    active_id = ""
    for seg in transcript.segments:
        if seg.status == "resolved":
            summaries[seg.issue_id] = summarize_segment(seg, model=model)
        else:
            # Byte-exact preservation — exactly the raw rendered turns.
            active_text = "\n\n".join(t.render() for t in seg.turns)
            active_id = seg.issue_id
    if not active_id:
        raise RuntimeError("Transcript has no active segment.")
    return Compressed(summaries=summaries, active_text=active_text, active_issue_id=active_id)
