"""No-API deterministic P0 simulation scenarios."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .contracts import Disposition, DispositionCommand, Evidence, EvidenceKind, Event, RuntimeBundle, RuntimeMode
from .engine import EvidenceRequirement, SopDefinition, SopEngine, SopStep
from .wal import JsonlWal


def build_runtime(wal_path: Path | str) -> SopEngine:
    bundle = RuntimeBundle(bundle_id="ST01-P0-R01", revision="R01", sop_version="1.0")
    sop = SopDefinition(
        sop_id="simulated-sop", version="1.0",
        steps=(SopStep("S01", (EvidenceRequirement("fixture_present", EvidenceKind.HARD),)),),
    )
    return SopEngine(sop, bundle, JsonlWal(wal_path), RuntimeMode.SIMULATION)


def run_scenario(name: str, wal_path: Path | str) -> SopEngine:
    engine = build_runtime(wal_path)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cycle_id = f"sim-{name}"

    def event(kind: str, payload: dict | None = None) -> Event:
        sequence = len(engine.snapshot.evidence) + len(engine.snapshot.alarms) + 1
        return Event(
            event_id=f"{cycle_id}-{kind}-{sequence}", event_type=kind, source="simulation",
            source_instance="simulation-1", source_seq=sequence, occurred_at=now,
            ingested_at=now, idempotency_key=f"{kind}-{sequence}", cycle_id=cycle_id,
            runtime_bundle_id=engine.bundle.bundle_id, payload=payload or {},
        )

    engine.ingest(event("CYCLE_ARMED", {"serial_number": "SIM-001"}))
    engine.ingest(event("CYCLE_STARTED"))
    if name == "aborted":
        engine.ingest(event("CYCLE_ABORTED"))
        return engine
    if name == "hold":
        engine.ingest(event("CYCLE_END"))
        return engine
    value = False if name in {"nonconforming", "rework"} else True
    evidence = Evidence(
        evidence_id=f"{cycle_id}-evidence", cycle_id=cycle_id, step_id="S01", key="fixture_present",
        kind=EvidenceKind.HARD, value=value, occurred_at=now, valid_from=now - timedelta(seconds=1),
        valid_until=now + timedelta(seconds=30), source_seq=1, runtime_bundle_id=engine.bundle.bundle_id,
    )
    engine.ingest(event("EVIDENCE", {"evidence": evidence.model_dump(mode="json")}))
    if name == "rework":
        command = DispositionCommand(cycle_id=cycle_id, disposition=Disposition.REWORK, actor_id="quality-1", reason="rework", client_id="simulation")
        engine.apply_disposition(command, event("DISPOSITION_SUBMITTED"))
        return engine
    if name == "normal":
        engine.ingest(event("CYCLE_END"))
        return engine
    if name != "nonconforming":
        raise ValueError(f"unknown scenario: {name}")
    return engine
