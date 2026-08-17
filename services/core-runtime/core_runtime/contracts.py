"""Versioned wire contracts shared by the engine and adapters."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SCHEMA_VERSION = "1.0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CycleState(StrEnum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    RUNNING = "RUNNING"
    ON_HOLD = "ON_HOLD"
    AWAITING_DISPOSITION = "AWAITING_DISPOSITION"
    CLOSED = "CLOSED"


class ConformanceResult(StrEnum):
    UNKNOWN = "UNKNOWN"
    CONFORMING = "CONFORMING"
    NONCONFORMING = "NONCONFORMING"
    ABORTED = "ABORTED"


class Disposition(StrEnum):
    NONE = "NONE"
    REWORK = "REWORK"
    SCRAP = "SCRAP"
    AUTHORIZED_RELEASE = "AUTHORIZED_RELEASE"


class RuntimeMode(StrEnum):
    SIMULATION = "SIMULATION"
    SHADOW = "SHADOW"
    ADVISORY = "ADVISORY"


class EvidenceKind(StrEnum):
    HARD = "HARD"
    STATE = "STATE"
    SOFT = "SOFT"


class EvidenceQuality(StrEnum):
    VALID = "VALID"
    STALE = "STALE"
    INVALID = "INVALID"
    CONFLICTED = "CONFLICTED"


class AlarmDomain(StrEnum):
    PROCESS = "PROCESS"
    SYSTEM = "SYSTEM"


class Event(BaseModel):
    """An immutable, journal-first domain input."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    event_id: str
    event_type: str
    source: str
    source_instance: str
    source_seq: int = Field(ge=1)
    occurred_at: datetime
    ingested_at: datetime = Field(default_factory=utc_now)
    idempotency_key: str
    cycle_id: str | None = None
    step_id: str | None = None
    runtime_bundle_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    """Evidence is retained even when it is unusable for a decision."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    evidence_id: str
    cycle_id: str
    step_id: str
    key: str
    kind: EvidenceKind
    value: Any
    unit: str | None = None
    occurred_at: datetime
    valid_from: datetime
    valid_until: datetime
    source_seq: int = Field(ge=1)
    source: str = "unknown"
    model_version: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    quality: EvidenceQuality = EvidenceQuality.VALID
    runtime_bundle_id: str
    attempt: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validity_window_is_ordered(self) -> "Evidence":
        if self.valid_until < self.valid_from:
            raise ValueError("valid_until must not precede valid_from")
        return self


class RuntimeBundle(BaseModel):
    """The frozen configuration identity used for one running cycle."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    bundle_id: str
    revision: str
    sop_version: str
    configuration: tuple[tuple[str, str], ...] = ()


class Alarm(BaseModel):
    model_config = ConfigDict(frozen=True)

    alarm_id: str
    domain: AlarmDomain
    code: str
    message: str
    occurred_at: datetime = Field(default_factory=utc_now)
    cycle_id: str | None = None
    evidence_id: str | None = None


class CycleSnapshot(BaseModel):
    """Read model with independent lifecycle, conformance, and disposition."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    cycle_id: str | None = None
    serial_number: str | None = None
    cycle_state: CycleState = CycleState.IDLE
    conformance_result: ConformanceResult = ConformanceResult.UNKNOWN
    disposition: Disposition = Disposition.NONE
    runtime_bundle_id: str | None = None
    current_step_id: str | None = None
    completed_step_ids: tuple[str, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    alarms: tuple[Alarm, ...] = ()
    rework_attempt: int = 0


class DispositionCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    cycle_id: str
    disposition: Disposition
    actor_id: str
    reason: str = Field(min_length=1)
    client_id: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def only_ng_dispositions_are_submitted(self) -> "DispositionCommand":
        if self.disposition == Disposition.NONE:
            raise ValueError("NONE is not a disposition command")
        return self
