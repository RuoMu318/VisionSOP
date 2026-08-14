"""Transactional repositories for current read models and append-only trace records."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core_runtime import CycleSnapshot, DispositionCommand, Event
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    AlarmRow,
    AuditLogRow,
    CycleDispositionRow,
    CycleRow,
    EventRow,
    EvidenceAssetRow,
    EvidenceRow,
    RuntimeBundleRow,
    SopVersionRow,
    StationRow,
)


class Repository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self.factory = factory

    def seed(self, station_id: str, station_name: str, mode: str, bundle: dict[str, Any], sop: dict[str, Any]) -> None:
        with self.factory.begin() as db:
            station = db.get(StationRow, station_id)
            if station is None:
                db.add(StationRow(station_id=station_id, name=station_name, mode=mode))
            elif station.mode != mode:
                station.mode = mode
            if db.get(RuntimeBundleRow, bundle["bundle_id"]) is None:
                db.add(RuntimeBundleRow(
                    bundle_id=bundle["bundle_id"], station_id=station_id,
                    revision=bundle["revision"], sop_version=bundle["sop_version"],
                    configuration=bundle.get("configuration", {}),
                ))
            existing = db.scalar(select(SopVersionRow).where(
                SopVersionRow.sop_id == sop["sop_id"], SopVersionRow.version == sop["version"],
            ))
            if existing is None:
                db.add(SopVersionRow(sop_id=sop["sop_id"], version=sop["version"], definition=sop))

    def save_runtime(
        self,
        station_id: str,
        scenario: str,
        snapshot: CycleSnapshot,
        wal_path: Path,
        events: list[Event],
    ) -> None:
        if snapshot.cycle_id is None or snapshot.serial_number is None or snapshot.runtime_bundle_id is None:
            raise ValueError("a persisted cycle requires cycle, serial, and Runtime Bundle identities")
        now = datetime.now(timezone.utc)
        with self.factory.begin() as db:
            row = db.get(CycleRow, snapshot.cycle_id)
            values = snapshot.model_dump(mode="json")
            if row is None:
                row = CycleRow(
                    cycle_id=snapshot.cycle_id, station_id=station_id,
                    serial_number=snapshot.serial_number, scenario=scenario,
                    lifecycle=snapshot.cycle_state.value,
                    conformance=snapshot.conformance_result.value,
                    disposition=snapshot.disposition.value,
                    runtime_bundle_id=snapshot.runtime_bundle_id,
                    snapshot=values, wal_path=str(wal_path),
                )
                db.add(row)
            else:
                row.lifecycle = snapshot.cycle_state.value
                row.conformance = snapshot.conformance_result.value
                row.disposition = snapshot.disposition.value
                row.snapshot = values
                row.updated_at = now
            station = db.get(StationRow, station_id)
            if station is None:
                raise LookupError(station_id)
            station.current_cycle_id = snapshot.cycle_id
            station.updated_at = now
            for item in events:
                if db.get(EventRow, item.event_id) is None:
                    db.add(EventRow(
                        event_id=item.event_id, station_id=station_id, cycle_id=item.cycle_id,
                        event_type=item.event_type, source_instance=item.source_instance,
                        source_seq=item.source_seq, occurred_at=item.occurred_at,
                        payload=item.model_dump(mode="json"),
                    ))
            for item in snapshot.evidence:
                if db.get(EvidenceRow, item.evidence_id) is None:
                    db.add(EvidenceRow(
                        evidence_id=item.evidence_id, cycle_id=item.cycle_id, step_id=item.step_id,
                        key=item.key, kind=item.kind.value, value={"value": item.value, "unit": item.unit},
                        quality=item.quality.value, occurred_at=item.occurred_at,
                        runtime_bundle_id=item.runtime_bundle_id, attempt=item.attempt,
                    ))
            for item in snapshot.alarms:
                persisted_alarm_id = f"{snapshot.cycle_id}:{item.alarm_id}"
                if db.get(AlarmRow, persisted_alarm_id) is None:
                    db.add(AlarmRow(
                        alarm_id=persisted_alarm_id, station_id=station_id, cycle_id=item.cycle_id,
                        domain=item.domain.value, code=item.code, message=item.message,
                        occurred_at=item.occurred_at,
                    ))

    def add_assets(self, rows: list[dict[str, Any]]) -> None:
        with self.factory.begin() as db:
            for values in rows:
                if db.get(EvidenceAssetRow, values["asset_id"]) is None:
                    db.add(EvidenceAssetRow(**values))

    def add_disposition(self, command: DispositionCommand, before: dict, after: dict) -> None:
        with self.factory.begin() as db:
            db.add(CycleDispositionRow(
                cycle_id=command.cycle_id, disposition=command.disposition.value,
                actor_id=command.actor_id, client_id=command.client_id,
                reason=command.reason, evidence_ids=list(command.evidence_ids),
            ))
            db.add(AuditLogRow(
                action="CYCLE_DISPOSITION", actor_id=command.actor_id, client_id=command.client_id,
                target_type="cycle", target_id=command.cycle_id,
                before_value=before, after_value=after, reason=command.reason,
            ))

    def station_rows(self) -> list[StationRow]:
        with self.factory() as db:
            return list(db.scalars(select(StationRow).order_by(StationRow.station_id)))

    def station_row(self, station_id: str) -> StationRow | None:
        with self.factory() as db:
            return db.get(StationRow, station_id)

    def cycle_row(self, cycle_id: str) -> CycleRow | None:
        with self.factory() as db:
            return db.get(CycleRow, cycle_id)

    def cycle_rows(self, serial_number: str | None = None) -> list[CycleRow]:
        with self.factory() as db:
            query = select(CycleRow)
            if serial_number:
                query = query.where(CycleRow.serial_number == serial_number)
            return list(db.scalars(query.order_by(CycleRow.created_at.desc())))

    def current_cycle(self, station_id: str) -> CycleRow | None:
        with self.factory() as db:
            station = db.get(StationRow, station_id)
            return db.get(CycleRow, station.current_cycle_id) if station and station.current_cycle_id else None

    def alarm_rows(self, domain: str | None = None, acknowledged: bool | None = None) -> list[AlarmRow]:
        with self.factory() as db:
            query = select(AlarmRow)
            if domain:
                query = query.where(AlarmRow.domain == domain)
            if acknowledged is not None:
                query = query.where(AlarmRow.acknowledged == acknowledged)
            return list(db.scalars(query.order_by(AlarmRow.occurred_at.desc())))

    def acknowledge_alarm(self, alarm_id: str, actor_id: str, client_id: str, reason: str) -> AlarmRow | None:
        with self.factory.begin() as db:
            row = db.get(AlarmRow, alarm_id)
            if row is None:
                return None
            before = {"acknowledged": row.acknowledged, "acknowledged_by": row.acknowledged_by}
            row.acknowledged = True
            row.acknowledged_by = actor_id
            row.acknowledged_at = datetime.now(timezone.utc)
            db.add(AuditLogRow(
                action="ALARM_ACKNOWLEDGED", actor_id=actor_id, client_id=client_id,
                target_type="alarm", target_id=alarm_id, before_value=before,
                after_value={"acknowledged": True, "acknowledged_by": actor_id}, reason=reason,
            ))
            return row

    def evidence_asset(self, asset_id: str) -> EvidenceAssetRow | None:
        with self.factory() as db:
            return db.get(EvidenceAssetRow, asset_id)

    def cycle_assets(self, cycle_id: str) -> list[EvidenceAssetRow]:
        with self.factory() as db:
            return list(db.scalars(select(EvidenceAssetRow).where(EvidenceAssetRow.cycle_id == cycle_id)))

    def sop_version(self, sop_id: str, version: str) -> SopVersionRow | None:
        with self.factory() as db:
            return db.scalar(select(SopVersionRow).where(
                SopVersionRow.sop_id == sop_id, SopVersionRow.version == version,
            ))

    def audit_count(self, action: str | None = None) -> int:
        with self.factory() as db:
            query = select(AuditLogRow)
            if action:
                query = query.where(AuditLogRow.action == action)
            return len(list(db.scalars(query)))

    def reset_station(self, station_id: str, actor_id: str = "simulation") -> None:
        with self.factory.begin() as db:
            station = db.get(StationRow, station_id)
            if station is None:
                raise LookupError(station_id)
            before = {"current_cycle_id": station.current_cycle_id}
            station.current_cycle_id = None
            station.updated_at = datetime.now(timezone.utc)
            db.add(AuditLogRow(
                action="SIMULATION_RESET", actor_id=actor_id, client_id="simulation-console",
                target_type="station", target_id=station_id, before_value=before,
                after_value={"current_cycle_id": None}, reason="reset simulated station",
            ))
