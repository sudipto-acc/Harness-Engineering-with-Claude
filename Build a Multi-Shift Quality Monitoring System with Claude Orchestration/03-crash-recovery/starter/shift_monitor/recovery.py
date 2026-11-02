"""Resume-vs-fresh decision logic for crash recovery.

The 30-minute threshold is ~1/16 of an 8-hour shift cycle: a resume inside this
window is still operating on the same shift's working set; anything older is
treated as a stale partial that should be re-started from scratch with whatever
findings the manifest already captured injected as a summary.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from .manifest import ManifestState

# One-sixteenth of an 8-hour shift: a resume inside this window is still
# operating on the same shift's working set.
STALE_RESUME_THRESHOLD_MINUTES = 30

Decision = Literal["resume", "fresh"]


def decide(state: ManifestState, now: datetime) -> Decision:
    # Returns "resume" or "fresh" based on three cases.
    #
    #   1. If the manifest has no steps at all, return "fresh".
    #      (An empty manifest is a special case that is easy to forget alongside
    #       the complete-vs-incomplete path.)
    #   2. If the manifest is complete (last step name == "complete"), return "fresh".
    #   3. Otherwise the manifest is incomplete. Compare `now` to the last step's
    #      `ts`: if the gap is <= STALE_RESUME_THRESHOLD_MINUTES, return "resume";
    #      otherwise return "fresh".
    #
    # Boundary note: at exactly 30 minutes, "resume" wins. Use `<=`, not `<`.
    if not state.steps:
        return "fresh"
    if state.complete:
        return "fresh"
    gap = now - state.steps[-1].ts
    if gap <= timedelta(minutes=STALE_RESUME_THRESHOLD_MINUTES):
        return "resume"
    return "fresh"
