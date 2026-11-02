"""Extra evidence for System 4. Run from the solution directory after `run-shift`.

Uses only the solution's public API; writes only under data/fork_demo/.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from shift_monitor import fork, recovery
from shift_monitor.manifest import ManifestState, Step
from shift_monitor.scratchpad import Scratchpad, ScratchpadEntry
from shift_monitor.state import HOT_STATE_BYTE_BUDGET
from shift_monitor.warm import WarmStore

DATA = Path("data")
HOT = DATA / "hot_state.json"
SINCE = "2026-04-01T00:00:00Z"

warm = WarmStore(DATA / "warm.sqlite")
print("== warm tier (SQL pre-filter) ==")
print("warm-tier total rows:", warm.count())
print(f"rows returned by defects_since(ts > {SINCE}, limit=50):", len(warm.defects_since(SINCE, limit=50)))
for row in warm.explain_defects_since(SINCE, limit=50):
    print("EXPLAIN QUERY PLAN:", row[-1])

print("== hot state size ==")
print(f"{HOT.name}: {HOT.stat().st_size} bytes (budget {HOT_STATE_BYTE_BUDGET})")

print("== crash recovery: resume vs fresh ==")
print("STALE_RESUME_THRESHOLD_MINUTES =", recovery.STALE_RESUME_THRESHOLD_MINUTES)
now = datetime.now(UTC)


def _step(name: str, minutes_ago: int) -> Step:
    return Step(
        step_id=f"demo-{name}",
        name=name,
        ts=now - timedelta(minutes=minutes_ago),
        invocation_shape="rich",
        payload={},
    )


cases = {
    "incomplete manifest, last step 10 min ago": ManifestState(complete=False, steps=[_step("gather", 10)]),
    "incomplete manifest, last step 45 min ago": ManifestState(complete=False, steps=[_step("gather", 45)]),
    "complete manifest, last step 5 min ago": ManifestState(complete=True, steps=[_step("complete", 5)]),
    "empty manifest": ManifestState(complete=False, steps=[]),
}
for label, state in cases.items():
    print(f"{label}: {recovery.decide(state, now)}")

print("== fork isolation ==")
base_sha = hashlib.sha256(HOT.read_bytes()).hexdigest()
forks_root = DATA / "fork_demo" / "forks"
main_pad = DATA / "fork_demo" / "main_scratchpad.jsonl"
hypotheses = {
    "H1-lot-contamination": "Lot 2026-0430-B has a dielectric defect; quarantine the lot.",
    "H2-test-station-drift": "Bank C-7 probe contacts drifted; recalibrate before blaming the lot.",
}
fork_pads = []
for hypothesis_id, conclusion in hypotheses.items():
    fork_dir = fork.fork_for_hypothesis(HOT, hypothesis_id, forks_root)
    pad = Scratchpad(fork_dir / "scratchpad.jsonl")
    pad.append(
        ScratchpadEntry(hypothesis_id=hypothesis_id, evidence="fork demo", conclusion=conclusion, ts=now)
    )
    fork_pads.append(pad.path)
    print(f"{pad.path.relative_to(DATA).as_posix()}: {len(pad.read())} entry")
print("base hot_state.json unchanged after forking:", hashlib.sha256(HOT.read_bytes()).hexdigest() == base_sha)
for pad_path in fork_pads:
    others = [p for p in fork_pads if p != pad_path]
    leaked = any(Scratchpad(pad_path).read()[0].hypothesis_id in p.read_text(encoding="utf-8") for p in others)
    print(f"{pad_path.parent.name} findings visible in the other fork:", leaked)
fork.merge_findings(fork_pads, main_pad)
print("merged main scratchpad:", [e.hypothesis_id for e in Scratchpad(main_pad).read()])
