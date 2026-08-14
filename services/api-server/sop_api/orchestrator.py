"""Software-only station orchestration around the real deterministic engine."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from core_runtime import (
    ConformanceResult,
    CycleSnapshot,
    CycleState,
    Disposition,
    DispositionCommand,
    Evidence,
    EvidenceKind,
    Event,
    EvidenceRequirement,
    JsonlWal,
    RuntimeBundle,
    SopDefinition,
    SopEngine,
    SopStep,
)
from core_runtime.adapters import LocalEvidenceAdapter

from .config import Settings
from .repository import Repository


SCENARIOS = {"normal", "nonconforming", "hold", "system_hold", "aborted", "rework"}
STEP_NAMES = {
    "S01": "扫描产品码",
    "S02": "产品放入治具",
    "S03": "安装垫片",
    "S04": "插入螺丝",
    "S05": "锁紧并确认扭矩",
    "S06": "完成下料",
}


@dataclass(frozen=True)
class OrderedBatch:
    ordered: tuple[Event, ...]
    late_count: int


class EventTimeReorderBuffer:
    """Order one ingress batch by event time and append outside-window inputs last.

    Appending late inputs after the watermark lets the engine durably classify them
    without allowing them to mutate Cycle state.
    """

    def __init__(self, lateness_seconds: int) -> None:
        self.window = timedelta(seconds=lateness_seconds)

    def order(self, events: list[Event]) -> OrderedBatch:
        if not events:
            return OrderedBatch((), 0)
        watermark = max(item.occurred_at for item in events)
        cutoff = watermark - self.window
        eligible = sorted(
            (item for item in events if item.occurred_at >= cutoff),
            key=lambda item: (item.occurred_at, item.source_instance, item.source_seq),
        )
        late = sorted(
            (item for item in events if item.occurred_at < cutoff),
            key=lambda item: (item.occurred_at, item.source_instance, item.source_seq),
        )
        return OrderedBatch(tuple(eligible + late), len(late))


def build_bundle() -> RuntimeBundle:
    return RuntimeBundle(
        bundle_id="ST01-P0-R01", revision="R01", sop_version="1.0",
        configuration=(
            ("camera", "simulated"),
            ("device", "simulated"),
            ("evidence", "local"),
            ("model", "simulated"),
        ),
    )


def build_sop() -> SopDefinition:
    requirements = (
        ("S01", "scanner_ok", EvidenceKind.HARD),
        ("S02", "product_in_fixture", EvidenceKind.STATE),
        ("S03", "washer_present", EvidenceKind.STATE),
        ("S04", "screw_present", EvidenceKind.STATE),
        ("S05", "torque_ok", EvidenceKind.HARD),
        ("S06", "product_removed", EvidenceKind.HARD),
    )
    return SopDefinition(
        sop_id="SOP_001", version="1.0",
        steps=tuple(
            SopStep(step_id, (EvidenceRequirement(key, kind, True, 60),), timeout_seconds=30)
            for step_id, key, kind in requirements
        ),
    )


class StationOrchestrator:
    def __init__(self, settings: Settings, repository: Repository) -> None:
        self.settings = settings
        self.repository = repository
        self.bundle = build_bundle()
        self.sop = build_sop()
        self.reorder = EventTimeReorderBuffer(settings.event_lateness_seconds)
        self._engine: SopEngine | None = None
        self._scenario: str | None = None
        self._subscribers: set[asyncio.Queue[dict]] = set()
        self._seed()

    def _seed(self) -> None:
        sop_json = {
            "sop_id": self.sop.sop_id, "version": self.sop.version,
            "steps": [
                {
                    "id": step.step_id, "name": STEP_NAMES[step.step_id],
                    "timeout_seconds": step.timeout_seconds,
                    "completion": [
                        {"key": req.key, "kind": req.kind.value, "expected_value": req.expected_value}
                        for req in step.required
                    ],
                }
                for step in self.sop.steps
            ],
        }
        self.repository.seed(
            self.settings.station_id, self.settings.station_name, self.settings.runtime_mode.value,
            {
                "bundle_id": self.bundle.bundle_id, "revision": self.bundle.revision,
                "sop_version": self.bundle.sop_version,
                "configuration": dict(self.bundle.configuration),
            },
            sop_json,
        )

    def run_scenario(self, scenario: str) -> dict:
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario: {scenario}")
        cycle_id = f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"
        wal_path = self.settings.data_dir / "wal" / self.settings.station_id / f"{cycle_id}.jsonl"
        engine = SopEngine(
            self.sop, self.bundle, JsonlWal(wal_path), self.settings.runtime_mode,
            lateness_window_seconds=self.settings.event_lateness_seconds,
        )
        events = self._scenario_events(cycle_id, scenario)
        for item in self.reorder.order(events).ordered:
            engine.ingest(item)
        if scenario == "rework":
            command = DispositionCommand(
                cycle_id=cycle_id, disposition=Disposition.REWORK, actor_id="quality-sim",
                reason="simulate controlled rework", client_id="simulation-console",
            )
            disposition_event = self._event(cycle_id, "DISPOSITION_SUBMITTED", 9)
            engine.apply_disposition(command, disposition_event)
            for item in self._completion_events(cycle_id, start_sequence=10, attempt=1):
                engine.ingest(item)
        self._engine = engine
        self._scenario = scenario
        self._persist_engine(engine, scenario, wal_path)
        return self.station_snapshot(self.settings.station_id)

    def _scenario_events(self, cycle_id: str, scenario: str) -> list[Event]:
        events = [
            self._event(cycle_id, "CYCLE_ARMED", 1, {"serial_number": f"SN-{cycle_id[-6:].upper()}"}),
            self._event(cycle_id, "CYCLE_STARTED", 2),
        ]
        if scenario == "aborted":
            events.extend(self._evidence_events(cycle_id, 3, limit=2))
            events.append(self._event(cycle_id, "CYCLE_ABORTED", 5))
            return events
        if scenario == "system_hold":
            events.append(self._event(cycle_id, "SYSTEM_HOLD", 3, {
                "code": "DATABASE_UNAVAILABLE",
                "message": "simulated database persistence outage",
            }))
            return events
        if scenario == "hold":
            events.extend(self._evidence_events(cycle_id, 3, limit=2))
            events.append(self._event(cycle_id, "CYCLE_END", 5))
            return events
        events.extend(self._evidence_events(cycle_id, 3, violation=(scenario in {"nonconforming", "rework"})))
        if scenario == "normal":
            events.append(self._event(cycle_id, "CYCLE_END", 9))
        return events

    def _completion_events(self, cycle_id: str, start_sequence: int, attempt: int) -> list[Event]:
        items = self._evidence_events(cycle_id, start_sequence, attempt=attempt)
        items.append(self._event(cycle_id, "CYCLE_END", start_sequence + len(self.sop.steps), attempt=attempt))
        return items

    def _evidence_events(
        self,
        cycle_id: str,
        start_sequence: int,
        limit: int | None = None,
        violation: bool = False,
        attempt: int = 0,
    ) -> list[Event]:
        now = datetime.now(timezone.utc)
        steps = self.sop.steps[:limit]
        items: list[Event] = []
        for offset, step in enumerate(steps):
            req = step.required[0]
            value = False if violation and step.step_id == "S05" else True
            evidence = Evidence(
                evidence_id=f"{cycle_id}-{step.step_id}-A{attempt}", cycle_id=cycle_id,
                step_id=step.step_id, key=req.key, kind=req.kind, value=value,
                occurred_at=now + timedelta(milliseconds=start_sequence + offset),
                valid_from=now - timedelta(seconds=1), valid_until=now + timedelta(seconds=120),
                source_seq=start_sequence + offset, runtime_bundle_id=self.bundle.bundle_id,
                attempt=attempt,
            )
            items.append(self._event(
                cycle_id, "EVIDENCE", start_sequence + offset,
                {"evidence": evidence.model_dump(mode="json")},
                step_id=step.step_id, occurred_at=evidence.occurred_at,
            ))
            if violation and step.step_id == "S05":
                break
        return items

    def _event(
        self,
        cycle_id: str,
        event_type: str,
        sequence: int,
        payload: dict | None = None,
        *,
        step_id: str | None = None,
        occurred_at: datetime | None = None,
        attempt: int = 0,
    ) -> Event:
        now = occurred_at or datetime.now(timezone.utc) + timedelta(milliseconds=sequence)
        return Event(
            event_id=f"{cycle_id}-{event_type}-{sequence}-A{attempt}", event_type=event_type,
            source="simulation", source_instance=f"simulation-{cycle_id}", source_seq=sequence,
            occurred_at=now, ingested_at=now, idempotency_key=f"{event_type}-{sequence}-A{attempt}",
            cycle_id=cycle_id, step_id=step_id, runtime_bundle_id=self.bundle.bundle_id,
            payload=payload or {},
        )

    def apply_disposition(self, cycle_id: str, command: DispositionCommand) -> dict:
        row = self.repository.cycle_row(cycle_id)
        if row is None:
            raise LookupError(cycle_id)
        engine = self._load_engine(row.wal_path)
        if engine.snapshot.cycle_id != cycle_id:
            raise RuntimeError("WAL cycle identity does not match the requested cycle")
        if engine.snapshot.cycle_state != CycleState.AWAITING_DISPOSITION:
            raise ValueError("cycle is not awaiting disposition")
        before = engine.snapshot.model_dump(mode="json")
        next_sequence = max((item.source_seq for item in engine.wal.replay_events()), default=0) + 1
        engine.apply_disposition(command, self._event(cycle_id, "DISPOSITION_SUBMITTED", next_sequence))
        if command.disposition == Disposition.REWORK:
            start = next_sequence + 1
            for item in self._completion_events(cycle_id, start, engine.snapshot.rework_attempt):
                engine.ingest(item)
        self._engine = engine
        self._scenario = row.scenario
        self._persist_engine(engine, row.scenario, Path(row.wal_path))
        after = engine.snapshot.model_dump(mode="json")
        self.repository.add_disposition(command, before, after)
        return self.cycle_detail(cycle_id)

    def _load_engine(self, wal_path: str) -> SopEngine:
        if self._engine is not None and str(self._engine.wal.path) == wal_path:
            return self._engine
        return SopEngine.recover(self.sop, self.bundle, JsonlWal(wal_path), self.settings.runtime_mode)

    def _persist_engine(self, engine: SopEngine, scenario: str, wal_path: Path) -> None:
        snapshot = engine.snapshot
        should_capture = (
            snapshot.conformance_result == ConformanceResult.NONCONFORMING
            or snapshot.cycle_state == CycleState.ON_HOLD
            or snapshot.conformance_result == ConformanceResult.ABORTED
        )
        if should_capture and snapshot.cycle_id:
            asset_dir = (
                self.settings.data_dir / "evidence" / f"{datetime.now(timezone.utc):%Y-%m-%d}"
                / self.settings.station_id / snapshot.cycle_id
            )
            capture = LocalEvidenceAdapter(asset_dir).capture(snapshot.cycle_id, self.bundle.bundle_id)
            capture = capture.model_copy(update={
                "event_id": f"{snapshot.cycle_id}-EVIDENCE_READY",
                "idempotency_key": f"{snapshot.cycle_id}-EVIDENCE_READY",
            })
            if not any(item.event_id == capture.event_id for item in engine.wal.replay_events()):
                engine.ingest(capture)
            rows = []
            for asset_type, path_value in capture.payload.items():
                path = Path(path_value)
                rows.append({
                    "asset_id": f"{snapshot.cycle_id}:{asset_type}", "cycle_id": snapshot.cycle_id,
                    "asset_type": asset_type, "path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "byte_size": path.stat().st_size, "retained": True,
                })
            self.repository.add_assets(rows)
        self.repository.save_runtime(
            self.settings.station_id, scenario, engine.snapshot, wal_path,
            list(engine.wal.replay_events()),
        )

    def station_snapshot(self, station_id: str) -> dict:
        station = self.repository.station_row(station_id)
        if station is None:
            raise LookupError(station_id)
        cycle = self.repository.current_cycle(station_id)
        snapshot = CycleSnapshot.model_validate(cycle.snapshot) if cycle else CycleSnapshot()
        steps = self._step_view(snapshot)
        alarms = [self._alarm_view(row) for row in self.repository.alarm_rows() if row.cycle_id == snapshot.cycle_id]
        assets = [self._asset_view(row) for row in self.repository.cycle_assets(snapshot.cycle_id)] if snapshot.cycle_id else []
        database_health = "UNAVAILABLE" if any(
            alarm["code"] == "DATABASE_UNAVAILABLE" for alarm in alarms
        ) else "ONLINE"
        return {
            "station": {
                "station_id": station.station_id, "name": station.name, "online": station.online,
                "mode": station.mode, "runtime_bundle_id": snapshot.runtime_bundle_id or self.bundle.bundle_id,
            },
            "runtime_bundle": {
                "bundle_id": self.bundle.bundle_id,
                "revision": self.bundle.revision,
                "sop_version": self.bundle.sop_version,
                "configuration": dict(self.bundle.configuration),
            },
            "cycle": self._cycle_view(snapshot, cycle.scenario if cycle else None),
            "steps": steps,
            "evidence": self._evidence_matrix(snapshot),
            "alarms": alarms,
            "evidence_assets": assets,
            "health": {
                "camera": "SIMULATED_ONLINE", "model": "SIMULATED_READY",
                "device": "SIMULATED_ONLINE", "database": database_health,
            },
            "video": {"kind": "SIMULATED", "status": "ONLINE", "stream_url": None},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def stations(self) -> list[dict]:
        return [self.station_snapshot(item.station_id) for item in self.repository.station_rows()]

    def cycle_detail(self, cycle_id: str) -> dict:
        row = self.repository.cycle_row(cycle_id)
        if row is None:
            raise LookupError(cycle_id)
        snapshot = CycleSnapshot.model_validate(row.snapshot)
        return {
            "cycle": self._cycle_view(snapshot, row.scenario),
            "steps": self._step_view(snapshot),
            "evidence": self._evidence_matrix(snapshot),
            "alarms": [self._alarm_view(item) for item in self.repository.alarm_rows() if item.cycle_id == cycle_id],
            "evidence_assets": [self._asset_view(item) for item in self.repository.cycle_assets(cycle_id)],
            "wal_path": row.wal_path,
        }

    def cycles(self, serial_number: str | None = None) -> list[dict]:
        return [
            self._cycle_view(CycleSnapshot.model_validate(row.snapshot), row.scenario)
            for row in self.repository.cycle_rows(serial_number)
        ]

    def _cycle_view(self, snapshot: CycleSnapshot, scenario: str | None) -> dict:
        progress = len(snapshot.completed_step_ids) / len(self.sop.steps) if self.sop.steps else 1
        return {
            "cycle_id": snapshot.cycle_id, "serial_number": snapshot.serial_number,
            "lifecycle": snapshot.cycle_state.value, "conformance": snapshot.conformance_result.value,
            "disposition": snapshot.disposition.value, "current_step_id": snapshot.current_step_id,
            "completed_step_ids": list(snapshot.completed_step_ids),
            "runtime_bundle_id": snapshot.runtime_bundle_id, "rework_attempt": snapshot.rework_attempt,
            "progress_percent": round(progress * 100), "scenario": scenario,
        }

    def _step_view(self, snapshot: CycleSnapshot) -> list[dict]:
        result = []
        for index, step in enumerate(self.sop.steps, start=1):
            if step.step_id in snapshot.completed_step_ids:
                status = "COMPLETED"
            elif step.step_id == snapshot.current_step_id:
                status = "ON_HOLD" if snapshot.cycle_state == CycleState.ON_HOLD else "RUNNING"
            else:
                status = "WAITING"
            result.append({
                "id": step.step_id, "sequence": index, "name": STEP_NAMES[step.step_id],
                "status": status, "timeout_seconds": step.timeout_seconds,
            })
        return result

    def _evidence_matrix(self, snapshot: CycleSnapshot) -> list[dict]:
        matrix = []
        for step in self.sop.steps:
            req = step.required[0]
            found = next((item for item in reversed(snapshot.evidence) if item.key == req.key), None)
            matrix.append({
                "step_id": step.step_id, "key": req.key, "kind": req.kind.value,
                "required": True, "expected": req.expected_value,
                "value": found.value if found else None,
                "quality": found.quality.value if found else "MISSING",
                "source": "simulated-device" if req.kind == EvidenceKind.HARD else "simulated-model",
                "evidence_id": found.evidence_id if found else None,
            })
        return matrix

    @staticmethod
    def _alarm_view(row) -> dict:
        return {
            "alarm_id": row.alarm_id, "cycle_id": row.cycle_id, "domain": row.domain,
            "code": row.code, "message": row.message,
            "occurred_at": row.occurred_at.isoformat(), "acknowledged": row.acknowledged,
            "acknowledged_by": row.acknowledged_by,
        }

    @staticmethod
    def _asset_view(row) -> dict:
        return {
            "asset_id": row.asset_id, "cycle_id": row.cycle_id, "asset_type": row.asset_type,
            "sha256": row.sha256, "byte_size": row.byte_size,
            "created_at": row.created_at.isoformat(), "retained": row.retained,
        }

    async def publish(self, snapshot: dict) -> None:
        for queue in tuple(self._subscribers):
            await queue.put(snapshot)

    def subscribe(self) -> asyncio.Queue[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=8)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict]) -> None:
        self._subscribers.discard(queue)
