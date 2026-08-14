"""Small append-only JSONL write-ahead log with explicit durability."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

from .contracts import CycleSnapshot, Event


class JsonlWal:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: dict[str, Any]) -> None:
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
        with self.path.open("a", encoding="ascii", newline="\n") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def append_event(self, event: Event) -> None:
        self._append({"record_type": "event", "event": event.model_dump(mode="json")})

    def append_checkpoint(self, snapshot: CycleSnapshot) -> None:
        self._append({"record_type": "checkpoint", "snapshot": snapshot.model_dump(mode="json")})

    def records(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="ascii") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"invalid WAL record at line {line_number}") from error

    def replay_events(self) -> Iterator[Event]:
        for record in self.records():
            if record.get("record_type") == "event":
                yield Event.model_validate(record["event"])

    def latest_checkpoint(self) -> CycleSnapshot | None:
        checkpoint: CycleSnapshot | None = None
        for record in self.records():
            if record.get("record_type") == "checkpoint":
                checkpoint = CycleSnapshot.model_validate(record["snapshot"])
        return checkpoint
