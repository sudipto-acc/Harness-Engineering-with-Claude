"""Incremental crash-recovery manifest backed by JSON lines + fsync."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

InvocationShape = Literal["thin", "rich", "resumed"]


class Step(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: str
    name: str
    ts: datetime
    invocation_shape: InvocationShape
    payload: dict[str, Any]


class ManifestState(BaseModel):
    complete: bool
    steps: list[Step]


class Manifest:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append_step(self, step: Step) -> None:
        # Appends a single JSON line for `step` and makes it durable.
        #
        #   1. Make sure self.path.parent exists.
        #   2. Open the file in binary append mode: open(self.path, "ab").
        #      Text mode buffers the write through Python's text layer, so
        #      `flush()` + `os.fsync()` won't actually guarantee bytes hit disk.
        #      Use binary append ("ab") for fsync semantics.
        #   3. Encode `step.model_dump_json() + "\n"` as UTF-8 and write it.
        #   4. Flush and fsync the file descriptor *before* returning, so a
        #      crash one nanosecond after this call still leaves the line on disk.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "ab") as f:
            line = (step.model_dump_json() + "\n").encode("utf-8")
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    @classmethod
    def load(cls, path: Path) -> ManifestState:
        # Reads the manifest at `path`.
        #
        #   - If the file does not exist, return ManifestState(complete=False, steps=[]).
        #   - Otherwise, parse each non-empty line as a Step (Step.model_validate_json).
        #   - `complete` is True iff there is at least one step AND the last
        #     step's name == "complete". (An empty manifest is *not* complete.)
        if not path.exists():
            return ManifestState(complete=False, steps=[])
        steps: list[Step] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    steps.append(Step.model_validate_json(line))
        complete = bool(steps) and steps[-1].name == "complete"
        return ManifestState(complete=complete, steps=steps)
