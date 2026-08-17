"""P0 traceability tables. Media bytes stay outside the database."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class StationRow(Base):
    __tablename__ = "station"
    station_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    mode: Mapped[str] = mapped_column(String(32))
    online: Mapped[bool] = mapped_column(Boolean, default=True)
    current_cycle_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class RuntimeBundleRow(Base):
    __tablename__ = "runtime_bundle"
    bundle_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("station.station_id"))
    revision: Mapped[str] = mapped_column(String(32))
    sop_version: Mapped[str] = mapped_column(String(32))
    configuration: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class SopVersionRow(Base):
    __tablename__ = "sop_version"
    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sop_id: Mapped[str] = mapped_column(String(96))
    version: Mapped[str] = mapped_column(String(32))
    definition: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint("sop_id", "version"),)


class VisionRecipeRow(Base):
    """Immutable published recipes and their editable successor drafts."""

    __tablename__ = "vision_recipe"
    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[str] = mapped_column(String(96), index=True)
    version: Mapped[int] = mapped_column(Integer)
    station_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    definition: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint("template_id", "version"),)


class CycleRow(Base):
    __tablename__ = "cycle"
    cycle_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("station.station_id"), index=True)
    serial_number: Mapped[str] = mapped_column(String(128), index=True)
    scenario: Mapped[str] = mapped_column(String(32))
    lifecycle: Mapped[str] = mapped_column(String(32))
    conformance: Mapped[str] = mapped_column(String(32))
    disposition: Mapped[str] = mapped_column(String(32))
    runtime_bundle_id: Mapped[str] = mapped_column(String(96))
    snapshot: Mapped[dict] = mapped_column(JSON)
    wal_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class EventRow(Base):
    __tablename__ = "event"
    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    station_id: Mapped[str] = mapped_column(String(64), index=True)
    cycle_id: Mapped[str | None] = mapped_column(String(96), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    source_instance: Mapped[str] = mapped_column(String(96))
    source_seq: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON)


class EvidenceRow(Base):
    __tablename__ = "evidence"
    evidence_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    cycle_id: Mapped[str] = mapped_column(String(96), index=True)
    step_id: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(96))
    kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[dict] = mapped_column(JSON)
    quality: Mapped[str] = mapped_column(String(24))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    runtime_bundle_id: Mapped[str] = mapped_column(String(96))
    attempt: Mapped[int] = mapped_column(Integer, default=0)


class AlarmRow(Base):
    __tablename__ = "alarm"
    alarm_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    station_id: Mapped[str] = mapped_column(String(64), index=True)
    cycle_id: Mapped[str | None] = mapped_column(String(96), index=True, nullable=True)
    domain: Mapped[str] = mapped_column(String(16), index=True)
    code: Mapped[str] = mapped_column(String(96), index=True)
    message: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(96), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CycleDispositionRow(Base):
    __tablename__ = "cycle_disposition"
    disposition_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_id: Mapped[str] = mapped_column(String(96), index=True)
    disposition: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str] = mapped_column(String(96))
    client_id: Mapped[str] = mapped_column(String(96))
    reason: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class EvidenceAssetRow(Base):
    __tablename__ = "evidence_asset"
    asset_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    cycle_id: Mapped[str] = mapped_column(String(96), index=True)
    asset_type: Mapped[str] = mapped_column(String(24))
    path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    retained: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLogRow(Base):
    __tablename__ = "audit_log"
    audit_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(96), index=True)
    actor_id: Mapped[str] = mapped_column(String(96))
    client_id: Mapped[str] = mapped_column(String(96))
    target_type: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(128))
    before_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
