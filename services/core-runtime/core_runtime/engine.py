"""Deterministic SOP state machine. Only journaled Events alter its snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .contracts import (
    Alarm,
    AlarmDomain,
    ConformanceResult,
    CycleSnapshot,
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
from .wal import JsonlWal


@dataclass(frozen=True)
class EvidenceRequirement:
    key: str
    kind: EvidenceKind
    expected_value: Any = True
    freshness_seconds: int = 30


@dataclass(frozen=True)
class SopStep:
    step_id: str
    required: tuple[EvidenceRequirement, ...]
    timeout_seconds: int = 60


@dataclass(frozen=True)
class SopDefinition:
    sop_id: str
    version: str
    steps: tuple[SopStep, ...]


class SopEngine:
    """A cycle is derived solely by replaying journaled inputs."""

    def __init__(self, sop: SopDefinition, bundle: RuntimeBundle, wal: JsonlWal, mode: RuntimeMode | str) -> None:
        self.sop = sop
        self.bundle = bundle
        self.wal = wal
        self.mode = RuntimeMode(mode)
        self._snapshot = CycleSnapshot()
        self._seen: set[str] = set()
        self._started_at: datetime | None = None
        self._engine_sequence = 0

    @property
    def snapshot(self) -> CycleSnapshot:
        return self._snapshot

    @classmethod
    def recover(cls, sop: SopDefinition, bundle: RuntimeBundle, wal: JsonlWal, mode: RuntimeMode | str) -> "SopEngine":
        engine = cls(sop=sop, bundle=bundle, wal=wal, mode=mode)
        for event in wal.replay_events():
            engine._apply_event(event)
        if engine.snapshot.cycle_state in {CycleState.ARMED, CycleState.RUNNING}:
            engine._hold("RECOVERY_REQUIRES_REVIEW", "active cycle was recovered from WAL")
        return engine

    def ingest(self, event: Event) -> CycleSnapshot:
        """Durably record an Event before it is considered by the state machine."""
        self.wal.append_event(event)
        self._apply_event(event)
        return self.snapshot

    def checkpoint(self) -> CycleSnapshot:
        self.wal.append_checkpoint(self.snapshot)
        return self.snapshot

    def apply_disposition(self, command: DispositionCommand, event: Event) -> CycleSnapshot:
        if event.event_type != "DISPOSITION_SUBMITTED":
            raise ValueError("disposition commands require DISPOSITION_SUBMITTED events")
        payload = dict(event.payload)
        payload["command"] = command.model_dump(mode="json")
        return self.ingest(event.model_copy(update={"payload": payload, "cycle_id": command.cycle_id}))

    def tick(self, now: datetime) -> CycleSnapshot:
        if self.snapshot.cycle_state != CycleState.RUNNING or self._started_at is None:
            return self.snapshot
        step = self._current_step()
        if step and now > self._started_at + timedelta(seconds=step.timeout_seconds):
            self._engine_sequence += 1
            timeout_event = Event(
                event_id=f"timeout-{self.snapshot.cycle_id}-{self._engine_sequence}",
                event_type="STEP_TIMEOUT",
                source="sop-engine",
                source_instance="sop-engine-1",
                source_seq=self._engine_sequence,
                occurred_at=now,
                ingested_at=now,
                idempotency_key=f"timeout-{self.snapshot.cycle_id}-{self._engine_sequence}",
                cycle_id=self.snapshot.cycle_id,
                step_id=step.step_id,
                runtime_bundle_id=self.bundle.bundle_id,
            )
            self.ingest(timeout_event)
        return self.snapshot

    def _apply_event(self, event: Event) -> None:
        identity = f"{event.source_instance}:{event.idempotency_key}"
        if identity in self._seen:
            return
        self._seen.add(identity)

        if event.event_type == "CYCLE_ARMED":
            self._arm(event)
        elif event.event_type == "CYCLE_STARTED":
            self._start(event)
        elif event.event_type == "EVIDENCE":
            self._accept_evidence(event)
        elif event.event_type == "CYCLE_END":
            self._end(event)
        elif event.event_type in {"CYCLE_ABORTED", "CYCLE_CANCELLED"}:
            self._abort(event)
        elif event.event_type == "STEP_TIMEOUT":
            self._timeout(event)
        elif event.event_type == "CYCLE_RESUMED":
            self._resume(event)
        elif event.event_type == "DISPOSITION_SUBMITTED":
            self._disposition(event)

    def _arm(self, event: Event) -> None:
        if self.snapshot.cycle_state != CycleState.IDLE or not event.cycle_id:
            self._late(event, "CYCLE_ARMED is only valid while IDLE")
            return
        serial_number = event.payload.get("serial_number")
        if not isinstance(serial_number, str) or not serial_number:
            self._hold("INVALID_SERIAL_NUMBER", "CYCLE_ARMED requires a serial number")
            return
        self._snapshot = CycleSnapshot(
            cycle_id=event.cycle_id,
            serial_number=serial_number,
            cycle_state=CycleState.ARMED,
            runtime_bundle_id=self.bundle.bundle_id,
            current_step_id=self.sop.steps[0].step_id if self.sop.steps else None,
        )

    def _start(self, event: Event) -> None:
        if not self._matches_active(event) or self.snapshot.cycle_state != CycleState.ARMED:
            self._late(event, "CYCLE_STARTED does not match an armed cycle")
            return
        self._snapshot = self.snapshot.model_copy(update={"cycle_state": CycleState.RUNNING})
        self._started_at = event.occurred_at

    def _accept_evidence(self, event: Event) -> None:
        if not self._matches_active(event) or self.snapshot.cycle_state not in {CycleState.RUNNING, CycleState.ON_HOLD}:
            self._late(event, "evidence is late or does not match the active cycle")
            return
        evidence_data = event.payload.get("evidence")
        if not isinstance(evidence_data, dict):
            self._hold("INVALID_EVIDENCE", "EVIDENCE requires an evidence payload")
            return
        evidence = Evidence.model_validate(evidence_data)
        retained = self.snapshot.evidence + (evidence,)
        self._snapshot = self.snapshot.model_copy(update={"evidence": retained})
        if evidence.cycle_id != self.snapshot.cycle_id or evidence.runtime_bundle_id != self.bundle.bundle_id:
            self._hold("CYCLE_BINDING_INVALID", "evidence is bound to another cycle or bundle", evidence)
            return
        if not self._is_fresh_and_valid(evidence, event):
            self._hold("EVIDENCE_INVALID_OR_STALE", "evidence freshness or validity failed", evidence)
            return
        if self._conflicts(evidence):
            self._hold("REVIEW_HOLD", "conflicting evidence was retained", evidence)
            return
        requirement = self._requirement(evidence)
        if requirement and evidence.kind in {EvidenceKind.HARD, EvidenceKind.STATE} and evidence.value != requirement.expected_value:
            self._nonconforming("DEFINITE_VIOLATION", f"{evidence.key} violated its required value", evidence)
            return
        self._reconcile()

    def _end(self, event: Event) -> None:
        if not self._matches_active(event) or self.snapshot.cycle_state != CycleState.RUNNING:
            self._late(event, "CYCLE_END requires a running active cycle")
            return
        if len(self.snapshot.completed_step_ids) != len(self.sop.steps):
            self._hold("MISSING_REQUIRED_EVIDENCE", "cycle ended before all required evidence was valid")
            return
        self._snapshot = self.snapshot.model_copy(update={
            "cycle_state": CycleState.CLOSED,
            "conformance_result": ConformanceResult.CONFORMING,
            "current_step_id": None,
        })

    def _abort(self, event: Event) -> None:
        if not self._matches_active(event) or self.snapshot.cycle_state in {CycleState.IDLE, CycleState.CLOSED}:
            self._late(event, "abort is late or does not match the active cycle")
            return
        self._snapshot = self.snapshot.model_copy(update={
            "cycle_state": CycleState.CLOSED,
            "conformance_result": ConformanceResult.ABORTED,
            "current_step_id": None,
        })

    def _timeout(self, event: Event) -> None:
        if not self._matches_active(event) or self.snapshot.cycle_state != CycleState.RUNNING:
            self._late(event, "STEP_TIMEOUT is late or does not match the active cycle")
            return
        self._nonconforming("STEP_TIMEOUT", f"step {event.step_id or 'unknown'} timed out")

    def _resume(self, event: Event) -> None:
        if not self._matches_active(event) or self.snapshot.cycle_state != CycleState.ON_HOLD:
            self._late(event, "CYCLE_RESUMED requires an active held cycle")
            return
        self._snapshot = self.snapshot.model_copy(update={"cycle_state": CycleState.RUNNING})
        self._reconcile()

    def _disposition(self, event: Event) -> None:
        if not self._matches_active(event) or self.snapshot.cycle_state != CycleState.AWAITING_DISPOSITION:
            self._late(event, "disposition requires an awaiting-disposition cycle")
            return
        command = DispositionCommand.model_validate(event.payload.get("command"))
        if command.cycle_id != self.snapshot.cycle_id:
            self._late(event, "disposition command is for another cycle")
            return
        if command.disposition == Disposition.REWORK:
            self._snapshot = self.snapshot.model_copy(update={
                "cycle_state": CycleState.RUNNING,
                "disposition": Disposition.REWORK,
                "rework_attempt": self.snapshot.rework_attempt + 1,
                "current_step_id": self.sop.steps[0].step_id if self.sop.steps else None,
                "completed_step_ids": (),
                "evidence": (),
            })
            return
        self._snapshot = self.snapshot.model_copy(update={
            "cycle_state": CycleState.CLOSED,
            "disposition": command.disposition,
            "current_step_id": None,
        })

    def _reconcile(self) -> None:
        if self.snapshot.cycle_state != CycleState.RUNNING:
            return
        step = self._current_step()
        if step is None or not all(self._has_requirement(requirement) for requirement in step.required):
            return
        complete = self.snapshot.completed_step_ids + (step.step_id,)
        next_step = self.sop.steps[len(complete)] if len(complete) < len(self.sop.steps) else None
        self._snapshot = self.snapshot.model_copy(update={
            "completed_step_ids": complete,
            "current_step_id": next_step.step_id if next_step else None,
        })

    def _has_requirement(self, requirement: EvidenceRequirement) -> bool:
        return any(
            evidence.key == requirement.key
            and evidence.kind == requirement.kind
            and evidence.value == requirement.expected_value
            and evidence.quality == EvidenceQuality.VALID
            for evidence in self.snapshot.evidence
        )

    def _current_step(self) -> SopStep | None:
        index = len(self.snapshot.completed_step_ids)
        return self.sop.steps[index] if index < len(self.sop.steps) else None

    def _requirement(self, evidence: Evidence) -> EvidenceRequirement | None:
        step = self._current_step()
        if step is None:
            return None
        return next((item for item in step.required if item.key == evidence.key and item.kind == evidence.kind), None)

    def _is_fresh_and_valid(self, evidence: Evidence, event: Event) -> bool:
        requirement = self._requirement(evidence)
        freshness = requirement.freshness_seconds if requirement else 30
        return (
            evidence.quality == EvidenceQuality.VALID
            and evidence.valid_from <= evidence.occurred_at <= evidence.valid_until
            and evidence.occurred_at <= event.ingested_at
            and event.ingested_at - evidence.occurred_at <= timedelta(seconds=freshness)
        )

    def _conflicts(self, candidate: Evidence) -> bool:
        return any(
            existing.evidence_id != candidate.evidence_id
            and existing.key == candidate.key
            and existing.kind == candidate.kind
            and existing.value != candidate.value
            for existing in self.snapshot.evidence
        )

    def _matches_active(self, event: Event) -> bool:
        return event.cycle_id is not None and event.cycle_id == self.snapshot.cycle_id

    def _hold(self, code: str, message: str, evidence: Evidence | None = None) -> None:
        if self.snapshot.cycle_state in {CycleState.IDLE, CycleState.CLOSED, CycleState.AWAITING_DISPOSITION}:
            return
        self._snapshot = self.snapshot.model_copy(update={"cycle_state": CycleState.ON_HOLD})
        self._add_alarm(AlarmDomain.PROCESS, code, message, evidence)

    def _nonconforming(self, code: str, message: str, evidence: Evidence | None = None) -> None:
        self._snapshot = self.snapshot.model_copy(update={
            "cycle_state": CycleState.AWAITING_DISPOSITION,
            "conformance_result": ConformanceResult.NONCONFORMING,
        })
        self._add_alarm(AlarmDomain.PROCESS, code, message, evidence)

    def _late(self, event: Event, message: str) -> None:
        self._add_alarm(AlarmDomain.SYSTEM, "LATE_EVENT", message)

    def _add_alarm(self, domain: AlarmDomain, code: str, message: str, evidence: Evidence | None = None) -> None:
        alarm = Alarm(
            alarm_id=f"{code}-{len(self.snapshot.alarms) + 1}", domain=domain, code=code,
            message=message, cycle_id=self.snapshot.cycle_id,
            evidence_id=evidence.evidence_id if evidence else None,
        )
        self._snapshot = self.snapshot.model_copy(update={"alarms": self.snapshot.alarms + (alarm,)})
