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
    utc_now,
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

    def __init__(
        self,
        sop: SopDefinition,
        bundle: RuntimeBundle,
        wal: JsonlWal,
        mode: RuntimeMode | str,
        lateness_window_seconds: int = 5,
    ) -> None:
        self.sop = sop
        self.bundle = bundle
        self.wal = wal
        self.mode = RuntimeMode(mode)
        self._snapshot = CycleSnapshot()
        self._seen: set[str] = set()
        self._started_at: datetime | None = None
        self._engine_sequence = 0
        self._source_watermarks: dict[str, tuple[int, datetime]] = {}
        self.lateness_window = timedelta(seconds=lateness_window_seconds)

    @property
    def snapshot(self) -> CycleSnapshot:
        return self._snapshot

    @classmethod
    def recover(cls, sop: SopDefinition, bundle: RuntimeBundle, wal: JsonlWal, mode: RuntimeMode | str) -> "SopEngine":
        engine = cls(sop=sop, bundle=bundle, wal=wal, mode=mode)
        for event in wal.replay_events():
            engine._apply_event(event)
        if engine.snapshot.cycle_state in {CycleState.ARMED, CycleState.RUNNING}:
            now = utc_now()
            engine.ingest(Event(
                event_id=f"recovery-hold-{engine.snapshot.cycle_id}",
                event_type="RECOVERY_HOLD",
                source="sop-recovery",
                source_instance="sop-recovery-1",
                source_seq=1,
                occurred_at=now,
                ingested_at=now,
                idempotency_key=f"recovery-hold-{engine.snapshot.cycle_id}",
                cycle_id=engine.snapshot.cycle_id,
                runtime_bundle_id=engine.snapshot.runtime_bundle_id,
            ))
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
        if not self._accepts_ordering(event):
            return

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
        elif event.event_type == "RECOVERY_HOLD":
            self._recovery_hold(event)
        elif event.event_type == "SYSTEM_HOLD":
            self._system_hold(event)
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
            current_step_id=self.sop.steps[0].step_id if self.sop.steps else None,
        )

    def _start(self, event: Event) -> None:
        if not self._matches_cycle(event) or self.snapshot.cycle_state != CycleState.ARMED:
            self._late(event, "CYCLE_STARTED does not match an armed cycle")
            return
        if event.runtime_bundle_id != self.bundle.bundle_id:
            self._bundle_mismatch(event)
            return
        self._snapshot = self.snapshot.model_copy(update={
            "cycle_state": CycleState.RUNNING,
            "runtime_bundle_id": self.bundle.bundle_id,
        })
        self._started_at = event.occurred_at

    def _accept_evidence(self, event: Event) -> None:
        if not self._admit_active(event):
            return
        if self.snapshot.cycle_state not in {CycleState.RUNNING, CycleState.ON_HOLD}:
            self._late(event, "evidence is late for the active cycle")
            return
        evidence_data = event.payload.get("evidence")
        if not isinstance(evidence_data, dict):
            self._hold("INVALID_EVIDENCE", "EVIDENCE requires an evidence payload")
            return
        evidence = Evidence.model_validate(evidence_data)
        retained = self.snapshot.evidence + (evidence,)
        self._snapshot = self.snapshot.model_copy(update={"evidence": retained})
        if (
            evidence.cycle_id != self.snapshot.cycle_id
            or evidence.runtime_bundle_id != self.snapshot.runtime_bundle_id
            or evidence.attempt != self.snapshot.rework_attempt
        ):
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
        self._reconcile(event.ingested_at)

    def _end(self, event: Event) -> None:
        if not self._admit_active(event):
            return
        if self.snapshot.cycle_state != CycleState.RUNNING:
            self._late(event, "CYCLE_END requires a running active cycle")
            return
        if (
            len(self.snapshot.completed_step_ids) != len(self.sop.steps)
            or not self._all_completed_requirements_valid(event.ingested_at)
        ):
            self._hold("MISSING_REQUIRED_EVIDENCE", "cycle ended before all required evidence was valid")
            return
        self._snapshot = self.snapshot.model_copy(update={
            "cycle_state": CycleState.CLOSED,
            "conformance_result": (
                ConformanceResult.CONFORMING
                if self.snapshot.conformance_result == ConformanceResult.UNKNOWN
                else self.snapshot.conformance_result
            ),
            "current_step_id": None,
        })

    def _abort(self, event: Event) -> None:
        if not self._admit_active(event):
            return
        if self.snapshot.cycle_state in {
            CycleState.IDLE,
            CycleState.CLOSED,
            CycleState.AWAITING_DISPOSITION,
        }:
            if self.snapshot.cycle_state != CycleState.CLOSED:
                self._late(event, "abort is late or cannot replace an established conformance result", "INVALID_TRANSITION")
            return
        self._snapshot = self.snapshot.model_copy(update={
            "cycle_state": CycleState.CLOSED,
            "conformance_result": ConformanceResult.ABORTED,
            "current_step_id": None,
        })

    def _timeout(self, event: Event) -> None:
        if not self._admit_active(event):
            return
        if self.snapshot.cycle_state != CycleState.RUNNING:
            self._late(event, "STEP_TIMEOUT is late or does not match the active cycle")
            return
        self._nonconforming("STEP_TIMEOUT", f"step {event.step_id or 'unknown'} timed out")

    def _resume(self, event: Event) -> None:
        if not self._admit_active(event):
            return
        if self.snapshot.cycle_state != CycleState.ON_HOLD:
            self._late(event, "CYCLE_RESUMED requires an active held cycle")
            return
        if self._has_unusable_required_evidence(event.ingested_at):
            self._add_alarm(AlarmDomain.PROCESS, "REVALIDATION_FAILED", "held evidence remains ineligible")
            return
        self._snapshot = self.snapshot.model_copy(update={"cycle_state": CycleState.RUNNING})
        self._reconcile(event.ingested_at)

    def _disposition(self, event: Event) -> None:
        if not self._admit_active(event):
            return
        if self.snapshot.cycle_state != CycleState.AWAITING_DISPOSITION:
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
            })
            return
        self._snapshot = self.snapshot.model_copy(update={
            "cycle_state": CycleState.CLOSED,
            "disposition": command.disposition,
            "current_step_id": None,
        })

    def _reconcile(self, decision_time: datetime) -> None:
        if self.snapshot.cycle_state != CycleState.RUNNING:
            return
        step = self._current_step()
        if step is None or not all(self._has_requirement(requirement, decision_time) for requirement in step.required):
            return
        complete = self.snapshot.completed_step_ids + (step.step_id,)
        next_step = self.sop.steps[len(complete)] if len(complete) < len(self.sop.steps) else None
        self._snapshot = self.snapshot.model_copy(update={
            "completed_step_ids": complete,
            "current_step_id": next_step.step_id if next_step else None,
        })

    def _has_requirement(self, requirement: EvidenceRequirement, decision_time: datetime) -> bool:
        return any(
            self._is_decision_eligible(evidence, requirement, decision_time)
            for evidence in self.snapshot.evidence
        )

    def _all_completed_requirements_valid(self, decision_time: datetime) -> bool:
        return all(
            self._has_requirement(requirement, decision_time)
            for step in self.sop.steps
            for requirement in step.required
        )

    def _has_unusable_required_evidence(self, decision_time: datetime) -> bool:
        step = self._current_step()
        if step is None:
            return False
        for requirement in step.required:
            candidates = [
                item for item in self.snapshot.evidence
                if item.attempt == self.snapshot.rework_attempt
                and item.key == requirement.key
                and item.kind == requirement.kind
            ]
            if candidates and not any(self._is_decision_eligible(item, requirement, decision_time) for item in candidates):
                return True
        return False

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

    def _is_decision_eligible(
        self,
        evidence: Evidence,
        requirement: EvidenceRequirement,
        decision_time: datetime,
    ) -> bool:
        return (
            evidence.cycle_id == self.snapshot.cycle_id
            and evidence.runtime_bundle_id == self.snapshot.runtime_bundle_id
            and evidence.attempt == self.snapshot.rework_attempt
            and evidence.key == requirement.key
            and evidence.kind == requirement.kind
            and evidence.value == requirement.expected_value
            and evidence.quality == EvidenceQuality.VALID
            and evidence.valid_from <= evidence.occurred_at <= evidence.valid_until
            and evidence.occurred_at <= decision_time <= evidence.valid_until
            and decision_time - evidence.occurred_at <= timedelta(seconds=requirement.freshness_seconds)
        )

    def _conflicts(self, candidate: Evidence) -> bool:
        return any(
            existing.evidence_id != candidate.evidence_id
            and existing.attempt == candidate.attempt
            and existing.key == candidate.key
            and existing.kind == candidate.kind
            and existing.value != candidate.value
            for existing in self.snapshot.evidence
        )

    def _matches_cycle(self, event: Event) -> bool:
        return event.cycle_id is not None and event.cycle_id == self.snapshot.cycle_id

    def _admit_active(self, event: Event) -> bool:
        if not self._matches_cycle(event):
            self._late(event, "event does not match the active cycle")
            return False
        if self.snapshot.runtime_bundle_id is None or event.runtime_bundle_id != self.snapshot.runtime_bundle_id:
            self._bundle_mismatch(event)
            return False
        return True

    def _accepts_ordering(self, event: Event) -> bool:
        watermark = self._source_watermarks.get(event.source_instance)
        if watermark is not None:
            last_sequence, last_occurred_at = watermark
            if event.source_seq <= last_sequence:
                self._late(event, "source sequence is not monotonic", "OUT_OF_ORDER_SEQUENCE")
                return False
            if event.occurred_at < last_occurred_at - self.lateness_window:
                self._late(event, "event occurred outside the lateness window", "LATE_EVENT")
                return False
            self._source_watermarks[event.source_instance] = (event.source_seq, max(last_occurred_at, event.occurred_at))
            return True
        self._source_watermarks[event.source_instance] = (event.source_seq, event.occurred_at)
        return True

    def _recovery_hold(self, event: Event) -> None:
        if not self._matches_cycle(event) or self.snapshot.cycle_state not in {CycleState.ARMED, CycleState.RUNNING}:
            return
        if self.snapshot.runtime_bundle_id is not None and event.runtime_bundle_id != self.snapshot.runtime_bundle_id:
            self._bundle_mismatch(event)
            return
        self._hold("RECOVERY_REQUIRES_REVIEW", "active cycle was recovered from WAL")

    def _system_hold(self, event: Event) -> None:
        if not self._admit_active(event):
            return
        if self.snapshot.cycle_state not in {CycleState.RUNNING, CycleState.ON_HOLD}:
            self._late(event, "SYSTEM_HOLD requires an active cycle", "INVALID_TRANSITION")
            return
        code = str(event.payload.get("code") or "SYSTEM_UNAVAILABLE")
        message = str(event.payload.get("message") or "required system capability is unavailable")
        self._snapshot = self.snapshot.model_copy(update={"cycle_state": CycleState.ON_HOLD})
        self._add_alarm(AlarmDomain.SYSTEM, code, message)

    def _bundle_mismatch(self, event: Event) -> None:
        self._add_alarm(AlarmDomain.PROCESS, "RUNTIME_BUNDLE_MISMATCH", "event does not match the frozen Runtime Bundle")
        if self.snapshot.cycle_state in {CycleState.ARMED, CycleState.RUNNING, CycleState.ON_HOLD}:
            self._snapshot = self.snapshot.model_copy(update={"cycle_state": CycleState.ON_HOLD})

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

    def _late(self, event: Event, message: str, code: str = "LATE_EVENT") -> None:
        self._add_alarm(AlarmDomain.SYSTEM, code, message)

    def _add_alarm(self, domain: AlarmDomain, code: str, message: str, evidence: Evidence | None = None) -> None:
        alarm = Alarm(
            alarm_id=f"{code}-{len(self.snapshot.alarms) + 1}", domain=domain, code=code,
            message=message, cycle_id=self.snapshot.cycle_id,
            evidence_id=evidence.evidence_id if evidence else None,
        )
        self._snapshot = self.snapshot.model_copy(update={"alarms": self.snapshot.alarms + (alarm,)})
