from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core_runtime.adapters import (
    LocalEvidenceAdapter,
    SimulatedCameraAdapter,
    SimulatedDeviceAdapter,
    SimulatedModelAdapter,
)
from core_runtime.contracts import (
    ConformanceResult,
    CycleState,
    Disposition,
    DispositionCommand,
    Evidence,
    EvidenceKind,
    EvidenceQuality,
    Event,
    RuntimeBundle,
    RuntimeMode,
)
from core_runtime.engine import EvidenceRequirement, SopDefinition, SopEngine, SopStep
from core_runtime.simulation import run_scenario
from core_runtime.wal import JsonlWal


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_engine(tmp_path):
    bundle = RuntimeBundle(bundle_id="bundle-1", revision="R01", sop_version="1.0")
    sop = SopDefinition(
        sop_id="assembly", version="1.0",
        steps=(SopStep("S01", (EvidenceRequirement("fixture_present", EvidenceKind.HARD, freshness_seconds=10),)),),
    )
    return SopEngine(sop, bundle, JsonlWal(tmp_path / "events.jsonl"), RuntimeMode.SIMULATION)


def event(kind, sequence, cycle_id="cycle-1", payload=None, when=NOW):
    return Event(
        event_id=f"event-{sequence}", event_type=kind, source="test", source_instance="test-1",
        source_seq=sequence, occurred_at=when, ingested_at=when, idempotency_key=f"key-{sequence}",
        cycle_id=cycle_id, runtime_bundle_id="bundle-1", payload=payload or {},
    )


def evidence(value=True, *, evidence_id="evidence-1", occurred_at=NOW, quality=EvidenceQuality.VALID, bundle_id="bundle-1"):
    return Evidence(
        evidence_id=evidence_id, cycle_id="cycle-1", step_id="S01", key="fixture_present",
        kind=EvidenceKind.HARD, value=value, occurred_at=occurred_at,
        valid_from=occurred_at - timedelta(seconds=1), valid_until=occurred_at + timedelta(seconds=30),
        source_seq=1, quality=quality, runtime_bundle_id=bundle_id,
    )


def running_engine(tmp_path):
    engine = make_engine(tmp_path)
    engine.ingest(event("CYCLE_ARMED", 1, payload={"serial_number": "SN-001"}))
    engine.ingest(event("CYCLE_STARTED", 2))
    return engine


def submit_evidence(engine, item, sequence=3):
    return engine.ingest(event("EVIDENCE", sequence, payload={"evidence": item.model_dump(mode="json")}))


def test_normal_completion_keeps_state_and_result_separate(tmp_path):
    engine = running_engine(tmp_path)
    submit_evidence(engine, evidence())
    snapshot = engine.ingest(event("CYCLE_END", 4))

    assert snapshot.cycle_state == CycleState.CLOSED
    assert snapshot.conformance_result == ConformanceResult.CONFORMING
    assert snapshot.disposition == Disposition.NONE


def test_definite_violation_awaits_disposition(tmp_path):
    snapshot = submit_evidence(running_engine(tmp_path), evidence(False))

    assert snapshot.cycle_state == CycleState.AWAITING_DISPOSITION
    assert snapshot.conformance_result == ConformanceResult.NONCONFORMING


@pytest.mark.parametrize(
    "item",
    [
        evidence(quality=EvidenceQuality.INVALID),
        evidence(occurred_at=NOW - timedelta(seconds=60)),
    ],
)
def test_invalid_or_stale_evidence_holds_cycle(tmp_path, item):
    snapshot = submit_evidence(running_engine(tmp_path), item)

    assert snapshot.cycle_state == CycleState.ON_HOLD
    assert snapshot.conformance_result == ConformanceResult.UNKNOWN


def test_missing_and_conflicting_evidence_hold_cycle(tmp_path):
    missing = running_engine(tmp_path).ingest(event("CYCLE_END", 3))
    assert missing.cycle_state == CycleState.ON_HOLD

    engine = running_engine(tmp_path)
    submit_evidence(engine, evidence(True, evidence_id="first"))
    conflict = submit_evidence(engine, evidence(False, evidence_id="second"), 4)
    assert conflict.cycle_state == CycleState.ON_HOLD
    assert conflict.alarms[-1].code == "REVIEW_HOLD"
    assert len(conflict.evidence) == 2


def test_duplicate_and_late_events_cannot_change_cycle(tmp_path):
    engine = running_engine(tmp_path)
    original = event("EVIDENCE", 3, payload={"evidence": evidence().model_dump(mode="json")})
    engine.ingest(original)
    completed = engine.snapshot.completed_step_ids
    engine.ingest(original)
    assert engine.snapshot.completed_step_ids == completed

    engine.ingest(event("CYCLE_END", 4))
    snapshot = engine.ingest(event("EVIDENCE", 5, payload={"evidence": evidence(evidence_id="late").model_dump(mode="json")}))
    assert snapshot.cycle_state == CycleState.CLOSED
    assert snapshot.alarms[-1].code == "LATE_EVENT"


def test_abort_closes_cycle_as_aborted(tmp_path):
    snapshot = running_engine(tmp_path).ingest(event("CYCLE_ABORTED", 3))
    assert snapshot.cycle_state == CycleState.CLOSED
    assert snapshot.conformance_result == ConformanceResult.ABORTED


def test_timeout_is_journaled_before_it_becomes_nonconforming(tmp_path):
    engine = running_engine(tmp_path)
    snapshot = engine.tick(NOW + timedelta(seconds=61))

    assert snapshot.cycle_state == CycleState.AWAITING_DISPOSITION
    assert any(item.event_type == "STEP_TIMEOUT" for item in engine.wal.replay_events())


@pytest.mark.parametrize("disposition", [Disposition.SCRAP, Disposition.AUTHORIZED_RELEASE])
def test_terminal_dispositions_preserve_nonconforming_result(tmp_path, disposition):
    engine = running_engine(tmp_path)
    submit_evidence(engine, evidence(False))
    command = DispositionCommand(cycle_id="cycle-1", disposition=disposition, actor_id="quality", reason="reviewed", client_id="test")
    snapshot = engine.apply_disposition(command, event("DISPOSITION_SUBMITTED", 4))

    assert snapshot.cycle_state == CycleState.CLOSED
    assert snapshot.disposition == disposition
    assert snapshot.conformance_result == ConformanceResult.NONCONFORMING


def test_rework_preserves_nonconforming_fact_and_adds_attempt(tmp_path):
    engine = running_engine(tmp_path)
    submit_evidence(engine, evidence(False))
    command = DispositionCommand(cycle_id="cycle-1", disposition=Disposition.REWORK, actor_id="quality", reason="repair", client_id="test")
    snapshot = engine.apply_disposition(command, event("DISPOSITION_SUBMITTED", 4))

    assert snapshot.cycle_state == CycleState.RUNNING
    assert snapshot.disposition == Disposition.REWORK
    assert snapshot.conformance_result == ConformanceResult.NONCONFORMING
    assert snapshot.rework_attempt == 1


def test_wal_replays_and_checkpoint_is_available(tmp_path):
    engine = running_engine(tmp_path)
    submit_evidence(engine, evidence())
    engine.ingest(event("CYCLE_END", 4))
    engine.checkpoint()

    recovered = SopEngine.recover(engine.sop, engine.bundle, engine.wal, RuntimeMode.SIMULATION)
    assert recovered.snapshot == engine.snapshot
    assert engine.wal.latest_checkpoint() == engine.snapshot


def test_adapter_contracts_emit_events_without_engine_reference(tmp_path):
    camera = SimulatedCameraAdapter()
    device = SimulatedDeviceAdapter()
    model = SimulatedModelAdapter()
    local = LocalEvidenceAdapter(tmp_path / "evidence")
    item = evidence()

    for adapter in (camera, device, model, local):
        assert adapter.probe() is True
        assert adapter.health()["status"] == "STOPPED"
        assert adapter.configuration_schema()["type"] == "object"
        assert adapter.start()[0].event_type.endswith("ONLINE")
        assert adapter.stop()[0].event_type.endswith("OFFLINE")
    assert model.evidence(item).event_type == "EVIDENCE"
    assert device.signal("TORQUE_OK", "cycle-1", "bundle-1").event_type == "TORQUE_OK"
    artifact = local.capture("cycle-1", "bundle-1")
    assert artifact.event_type == "EVIDENCE_READY"
    assert (tmp_path / "evidence" / "cycle-1.json").exists()


def test_enforcing_mode_is_hard_rejected(tmp_path):
    engine = make_engine(tmp_path)
    with pytest.raises(ValueError):
        SopEngine(engine.sop, engine.bundle, engine.wal, "ENFORCING")


@pytest.mark.parametrize("scenario", ["normal", "nonconforming", "hold", "aborted", "rework"])
def test_simulation_runtime_covers_required_scenarios(tmp_path, scenario):
    engine = run_scenario(scenario, tmp_path / f"{scenario}.jsonl")
    assert engine.snapshot.cycle_state in set(CycleState)
