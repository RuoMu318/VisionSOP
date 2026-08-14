"""Adapter contracts and deterministic P0-only simulated implementations."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from .contracts import Evidence, Event


class Adapter(Protocol):
    def probe(self) -> bool: ...
    def start(self) -> tuple[Event, ...]: ...
    def stop(self) -> tuple[Event, ...]: ...
    def health(self) -> dict[str, str]: ...
    def configuration_schema(self) -> dict[str, Any]: ...


class _SimulatedAdapter:
    def __init__(self, name: str, source_instance: str | None = None) -> None:
        self.name = name
        self.source_instance = source_instance or f"simulated-{name}-1"
        self._sequence = 0
        self._started = False
        self._origin = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def probe(self) -> bool:
        return True

    def start(self) -> tuple[Event, ...]:
        self._started = True
        return (self._event(f"{self.name.upper()}_ONLINE"),)

    def stop(self) -> tuple[Event, ...]:
        self._started = False
        return (self._event(f"{self.name.upper()}_OFFLINE"),)

    def health(self) -> dict[str, str]:
        return {"status": "ONLINE" if self._started else "STOPPED", "adapter": self.name}

    def configuration_schema(self) -> dict[str, Any]:
        return {"type": "object", "additionalProperties": False, "properties": {}}

    def _event(self, event_type: str, **values: Any) -> Event:
        self._sequence += 1
        when = self._origin + timedelta(seconds=self._sequence)
        return Event(
            event_id=f"{self.source_instance}-{self._sequence}", event_type=event_type,
            source=self.name, source_instance=self.source_instance, source_seq=self._sequence,
            occurred_at=when, ingested_at=when, idempotency_key=str(self._sequence), **values,
        )


class SimulatedCameraAdapter(_SimulatedAdapter):
    def __init__(self) -> None:
        super().__init__("camera")

    def calibration_invalid(self) -> Event:
        return self._event("CAMERA_CALIBRATION_INVALID")


class SimulatedModelAdapter(_SimulatedAdapter):
    def __init__(self) -> None:
        super().__init__("model")

    def evidence(self, evidence: Evidence) -> Event:
        return self._event(
            "EVIDENCE", cycle_id=evidence.cycle_id, step_id=evidence.step_id,
            runtime_bundle_id=evidence.runtime_bundle_id,
            payload={"evidence": evidence.model_dump(mode="json")},
        )


class SimulatedDeviceAdapter(_SimulatedAdapter):
    def __init__(self) -> None:
        super().__init__("device")

    def signal(self, event_type: str, cycle_id: str, runtime_bundle_id: str, payload: dict[str, Any] | None = None) -> Event:
        return self._event(event_type, cycle_id=cycle_id, runtime_bundle_id=runtime_bundle_id, payload=payload or {})


class LocalEvidenceAdapter(_SimulatedAdapter):
    def __init__(self, output_directory: Path | str) -> None:
        super().__init__("evidence")
        self.output_directory = Path(output_directory)

    def capture(self, cycle_id: str, runtime_bundle_id: str) -> Event:
        self.output_directory.mkdir(parents=True, exist_ok=True)
        video = self.output_directory / f"{cycle_id}.mp4"
        screenshot = self.output_directory / f"{cycle_id}.jpg"
        manifest = self.output_directory / f"{cycle_id}.json"
        video.write_bytes(b"P0 simulated MP4 placeholder\n")
        screenshot.write_bytes(b"P0 simulated screenshot placeholder\n")
        manifest.write_text(json.dumps({"cycle_id": cycle_id, "runtime_bundle_id": runtime_bundle_id}), encoding="ascii")
        return self._event(
            "EVIDENCE_READY", cycle_id=cycle_id, runtime_bundle_id=runtime_bundle_id,
            payload={"video": str(video), "screenshot": str(screenshot), "manifest": str(manifest)},
        )
