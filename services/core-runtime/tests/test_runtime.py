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
    AlarmDomain,
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


def test_object_state_confirmed_is_normalized_to_state_evidence(tmp_path):
    bundle = RuntimeBundle(bundle_id="bundle-vision", revision="R01", sop_version="1.0")
    sop = SopDefinition(
        sop_id="assembly", version="1.0",
        steps=(SopStep("S02", (EvidenceRequirement("product_in_fixture", EvidenceKind.STATE),)),),
    )
    engine = SopEngine(sop, bundle, JsonlWal(tmp_path / "vision-events.jsonl"), RuntimeMode.SHADOW)
    engine.ingest(Event(
        event_id="arm", event_type="CYCLE_ARMED", source="operator", source_instance="operator-1",
        source_seq=1, occurred_at=NOW, ingested_at=NOW, idempotency_key="arm", cycle_id="cycle-vision",
        payload={"serial_number": "SN-VISION"},
    ))
    engine.ingest(Event(
        event_id="start", event_type="CYCLE_STARTED", source="operator", source_instance="operator-1",
        source_seq=2, occurred_at=NOW, ingested_at=NOW, idempotency_key="start", cycle_id="cycle-vision",
        runtime_bundle_id="bundle-vision",
    ))

    snapshot = engine.ingest(Event(
        event_id="vision-3", event_type="OBJECT_STATE_CONFIRMED", source="vision-runtime",
        source_instance="ST01_CAM01:product_in_fixture", source_seq=3,
        occurred_at=NOW, ingested_at=NOW, idempotency_key="frame-123", cycle_id="cycle-vision",
        step_id="S02", runtime_bundle_id="bundle-vision",
        payload={
            "state": "product_in_fixture", "value": True, "confidence": 0.98,
            "model_version": "fixture-occupancy-cv-v1", "valid_for_seconds": 20,
        },
    ))

    assert snapshot.completed_step_ids == ("S02",)
    evidence = snapshot.evidence[0]
    assert evidence.kind == EvidenceKind.STATE
    assert evidence.source == "vision-runtime"
    assert evidence.model_version == "fixture-occupancy-cv-v1"
    assert evidence.confidence == 0.98


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


@pytest.mark.parametrize(
    "item",
    [
        evidence(quality=EvidenceQuality.INVALID),
        evidence(occurred_at=NOW - timedelta(seconds=60)),
        evidence(bundle_id="other-bundle"),
    ],
)
def test_rejected_evidence_remains_inelegible_after_resume(tmp_path, item):
    engine = running_engine(tmp_path)
    submit_evidence(engine, item)

    resumed = engine.ingest(event("CYCLE_RESUMED", 4))
    ended = engine.ingest(event("CYCLE_END", 5))

    assert resumed.cycle_state == CycleState.ON_HOLD
    assert ended.cycle_state == CycleState.ON_HOLD
    assert ended.conformance_result == ConformanceResult.UNKNOWN


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


def test_completed_rework_preserves_nonconforming_fact_and_evidence_chain(tmp_path):
    engine = running_engine(tmp_path)
    submit_evidence(engine, evidence(False, evidence_id="original"))
    command = DispositionCommand(cycle_id="cycle-1", disposition=Disposition.REWORK, actor_id="quality", reason="repair", client_id="test")
    engine.apply_disposition(command, event("DISPOSITION_SUBMITTED", 4))
    submit_evidence(engine, evidence(True, evidence_id="rework").model_copy(update={"attempt": 1}), 5)
    snapshot = engine.ingest(event("CYCLE_END", 6))

    assert snapshot.cycle_state == CycleState.CLOSED
    assert snapshot.conformance_result == ConformanceResult.NONCONFORMING
    assert snapshot.disposition == Disposition.REWORK
    assert {item.evidence_id for item in snapshot.evidence} == {"original", "rework"}


def test_abort_after_nonconforming_cannot_erase_ng_fact(tmp_path):
    engine = running_engine(tmp_path)
    submit_evidence(engine, evidence(False))
    snapshot = engine.ingest(event("CYCLE_ABORTED", 4))

    assert snapshot.cycle_state == CycleState.AWAITING_DISPOSITION
    assert snapshot.conformance_result == ConformanceResult.NONCONFORMING


def test_start_requires_the_bundle_that_is_frozen_on_running_transition(tmp_path):
    engine = make_engine(tmp_path)
    engine.ingest(event("CYCLE_ARMED", 1, payload={"serial_number": "SN-001"}))
    snapshot = engine.ingest(event("CYCLE_STARTED", 2).model_copy(update={"runtime_bundle_id": "other-bundle"}))

    assert snapshot.cycle_state == CycleState.ON_HOLD
    assert snapshot.runtime_bundle_id is None
    assert snapshot.alarms[-1].code == "RUNTIME_BUNDLE_MISMATCH"


@pytest.mark.parametrize("event_type", ["CYCLE_END", "CYCLE_ABORTED", "CYCLE_RESUMED"])
def test_lifecycle_event_with_wrong_frozen_bundle_enters_hold(tmp_path, event_type):
    engine = running_engine(tmp_path)
    if event_type == "CYCLE_RESUMED":
        engine.ingest(event("CYCLE_END", 3))
    snapshot = engine.ingest(event(event_type, 4).model_copy(update={"runtime_bundle_id": "other-bundle"}))

    assert snapshot.cycle_state == CycleState.ON_HOLD
    assert snapshot.alarms[-1].code == "RUNTIME_BUNDLE_MISMATCH"


def test_disposition_event_with_wrong_frozen_bundle_enters_hold(tmp_path):
    engine = running_engine(tmp_path)
    submit_evidence(engine, evidence(False))
    command = DispositionCommand(cycle_id="cycle-1", disposition=Disposition.SCRAP, actor_id="quality", reason="reviewed", client_id="test")
    wrong_bundle_event = event("DISPOSITION_SUBMITTED", 4).model_copy(update={"runtime_bundle_id": "other-bundle"})
    snapshot = engine.apply_disposition(command, wrong_bundle_event)

    assert snapshot.cycle_state == CycleState.AWAITING_DISPOSITION
    assert snapshot.alarms[-1].code == "RUNTIME_BUNDLE_MISMATCH"


def test_unique_lower_source_sequence_is_classified_without_transition(tmp_path):
    engine = running_engine(tmp_path)
    submit_evidence(engine, evidence())
    out_of_order = event("CYCLE_END", 2).model_copy(update={"idempotency_key": "out-of-order-key"})
    snapshot = engine.ingest(out_of_order)

    assert snapshot.cycle_state == CycleState.RUNNING
    assert snapshot.alarms[-1].code == "OUT_OF_ORDER_SEQUENCE"


def test_backdated_event_outside_lateness_window_is_classified_without_transition(tmp_path):
    engine = running_engine(tmp_path)
    future_item = evidence(occurred_at=NOW + timedelta(seconds=10))
    engine.ingest(event("EVIDENCE", 3, payload={"evidence": future_item.model_dump(mode="json")}, when=NOW + timedelta(seconds=10)))
    backdated_end = event("CYCLE_END", 4, when=NOW)
    snapshot = engine.ingest(backdated_end)

    assert snapshot.cycle_state == CycleState.RUNNING
    assert snapshot.alarms[-1].code == "LATE_EVENT"


def test_backdated_event_after_closure_is_classified_without_reopening_cycle(tmp_path):
    engine = running_engine(tmp_path)
    engine.ingest(event("EVIDENCE", 3, payload={"evidence": evidence().model_dump(mode="json")}, when=NOW + timedelta(seconds=10)))
    engine.ingest(event("CYCLE_END", 4, when=NOW + timedelta(seconds=10)))
    snapshot = engine.ingest(event("CYCLE_STARTED", 5, when=NOW))

    assert snapshot.cycle_state == CycleState.CLOSED
    assert snapshot.alarms[-1].code == "LATE_EVENT"


def test_wal_replays_and_checkpoint_is_available(tmp_path):
    engine = running_engine(tmp_path)
    submit_evidence(engine, evidence())
    engine.ingest(event("CYCLE_END", 4))
    engine.checkpoint()

    recovered = SopEngine.recover(engine.sop, engine.bundle, engine.wal, RuntimeMode.SIMULATION)
    assert recovered.snapshot == engine.snapshot
    assert engine.wal.latest_checkpoint() == engine.snapshot


def test_recovery_hold_is_durable_and_replayable(tmp_path):
    engine = running_engine(tmp_path)
    recovered_once = SopEngine.recover(engine.sop, engine.bundle, engine.wal, RuntimeMode.SIMULATION)
    recovered_twice = SopEngine.recover(engine.sop, engine.bundle, engine.wal, RuntimeMode.SIMULATION)

    assert recovered_once.snapshot.cycle_state == CycleState.ON_HOLD
    assert recovered_twice.snapshot.cycle_state == CycleState.ON_HOLD
    assert recovered_twice.snapshot.alarms[-1].code == "RECOVERY_REQUIRES_REVIEW"
    assert [item.event_type for item in engine.wal.replay_events()].count("RECOVERY_HOLD") == 1


def test_required_system_failure_holds_without_creating_product_ng(tmp_path):
    engine = running_engine(tmp_path)
    snapshot = engine.ingest(event("SYSTEM_HOLD", 3, payload={
        "code": "DATABASE_UNAVAILABLE", "message": "database persistence is unavailable",
    }))

    assert snapshot.cycle_state == CycleState.ON_HOLD
    assert snapshot.conformance_result == ConformanceResult.UNKNOWN
    assert snapshot.alarms[-1].domain == AlarmDomain.SYSTEM
    assert snapshot.alarms[-1].code == "DATABASE_UNAVAILABLE"


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


@pytest.mark.parametrize(
    ("scenario", "state", "result", "disposition", "attempt"),
    [
        ("normal", CycleState.CLOSED, ConformanceResult.CONFORMING, Disposition.NONE, 0),
        ("nonconforming", CycleState.AWAITING_DISPOSITION, ConformanceResult.NONCONFORMING, Disposition.NONE, 0),
        ("hold", CycleState.ON_HOLD, ConformanceResult.UNKNOWN, Disposition.NONE, 0),
        ("aborted", CycleState.CLOSED, ConformanceResult.ABORTED, Disposition.NONE, 0),
        ("rework", CycleState.CLOSED, ConformanceResult.NONCONFORMING, Disposition.REWORK, 1),
    ],
)
def test_simulation_runtime_has_exact_required_outcomes(tmp_path, scenario, state, result, disposition, attempt):
    engine = run_scenario(scenario, tmp_path / f"{scenario}.jsonl")
    assert engine.snapshot.cycle_state == state
    assert engine.snapshot.conformance_result == result
    assert engine.snapshot.disposition == disposition
    assert engine.snapshot.rework_attempt == attempt
