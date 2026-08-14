from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core_runtime import ConformanceResult, CycleState, Disposition, Event, RuntimeMode
from sop_api import create_app
from sop_api.config import Settings
from sop_api.orchestrator import EventTimeReorderBuffer


EXPECTED = {
    "normal": ("CLOSED", "CONFORMING", "NONE", False),
    "nonconforming": ("AWAITING_DISPOSITION", "NONCONFORMING", "NONE", True),
    "hold": ("ON_HOLD", "UNKNOWN", "NONE", True),
    "system_hold": ("ON_HOLD", "UNKNOWN", "NONE", True),
    "aborted": ("CLOSED", "ABORTED", "NONE", True),
    "rework": ("CLOSED", "NONCONFORMING", "REWORK", True),
}


def test_health_and_initial_station_are_software_only(client):
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok", "version": "0.1.0-p0", "mode": "SIMULATION",
        "database": "sqlite", "hardware": "simulated",
    }

    station = client.get("/api/v1/stations/ST01/snapshot").json()
    assert station["cycle"]["lifecycle"] == "IDLE"
    assert station["cycle"]["conformance"] == "UNKNOWN"
    assert station["station"]["mode"] == "SIMULATION"
    assert len(station["steps"]) == 6


@pytest.mark.parametrize("scenario", EXPECTED)
def test_every_simulated_scenario_drives_the_real_runtime(client, scenario):
    response = client.post(f"/api/v1/simulation/scenarios/{scenario}")
    assert response.status_code == 200
    body = response.json()
    lifecycle, conformance, disposition, has_assets = EXPECTED[scenario]
    assert body["cycle"]["lifecycle"] == lifecycle
    assert body["cycle"]["conformance"] == conformance
    assert body["cycle"]["disposition"] == disposition
    assert bool(body["evidence_assets"]) is has_assets
    if lifecycle == "ON_HOLD":
        assert conformance == "UNKNOWN"


def test_cycle_trace_and_sop_version_queries(client):
    snapshot = client.post("/api/v1/simulation/scenarios/normal").json()
    cycle_id = snapshot["cycle"]["cycle_id"]
    serial = snapshot["cycle"]["serial_number"]

    detail = client.get(f"/api/v1/cycles/{cycle_id}")
    assert detail.status_code == 200
    assert detail.json()["cycle"]["progress_percent"] == 100
    assert len(detail.json()["evidence"]) == 6
    assert client.get(f"/api/v1/cycles?serial_number={serial}").json()[0]["cycle_id"] == cycle_id

    sop = client.get("/api/v1/sops/SOP_001/versions/1.0")
    assert sop.status_code == 200
    assert [item["id"] for item in sop.json()["steps"]] == [f"S0{i}" for i in range(1, 7)]


@pytest.mark.parametrize("disposition", ["SCRAP", "AUTHORIZED_RELEASE", "REWORK"])
def test_dispositions_preserve_nonconforming_and_are_audited(client, app, disposition):
    snapshot = client.post("/api/v1/simulation/scenarios/nonconforming").json()
    cycle_id = snapshot["cycle"]["cycle_id"]
    response = client.post(f"/api/v1/cycles/{cycle_id}/dispositions", json={
        "disposition": disposition, "actor_id": "quality-1", "client_id": "test-client",
        "reason": "reviewed simulated violation", "evidence_ids": [],
    })
    assert response.status_code == 200
    cycle = response.json()["cycle"]
    assert cycle["lifecycle"] == "CLOSED"
    assert cycle["conformance"] == "NONCONFORMING"
    assert cycle["disposition"] == disposition
    assert app.state.repository.audit_count("CYCLE_DISPOSITION") == 1


def test_invalid_or_late_disposition_is_rejected(client):
    cycle_id = client.post("/api/v1/simulation/scenarios/normal").json()["cycle"]["cycle_id"]
    payload = {"disposition": "SCRAP", "actor_id": "quality-1", "client_id": "test", "reason": "late"}
    assert client.post(f"/api/v1/cycles/{cycle_id}/dispositions", json=payload).status_code == 409
    payload["disposition"] = "NONE"
    assert client.post(f"/api/v1/cycles/{cycle_id}/dispositions", json=payload).status_code == 422


def test_alarm_domains_acknowledgement_and_evidence_metadata(client, app):
    body = client.post("/api/v1/simulation/scenarios/nonconforming").json()
    process = client.get("/api/v1/alarms?domain=PROCESS&acknowledged=false").json()
    assert process and all(item["domain"] == "PROCESS" for item in process)
    alarm_id = process[0]["alarm_id"]
    acknowledged = client.post(f"/api/v1/alarms/{alarm_id}/acknowledge", json={
        "actor_id": "quality-1", "client_id": "test-client", "reason": "reviewed evidence",
    })
    assert acknowledged.status_code == 200
    assert acknowledged.json()["acknowledged"] is True
    assert app.state.repository.audit_count("ALARM_ACKNOWLEDGED") == 1

    asset = body["evidence_assets"][0]
    metadata = client.get(f"/api/v1/evidence/{asset['asset_id']}")
    assert metadata.status_code == 200
    assert len(metadata.json()["sha256"]) == 64
    assert "path" not in metadata.json()


def test_system_hold_is_not_counted_as_process_nonconformance(client):
    body = client.post("/api/v1/simulation/scenarios/system_hold").json()
    assert body["cycle"]["lifecycle"] == "ON_HOLD"
    assert body["cycle"]["conformance"] == "UNKNOWN"
    assert body["alarms"][-1]["domain"] == "SYSTEM"
    assert body["alarms"][-1]["code"] == "DATABASE_UNAVAILABLE"


def test_websocket_starts_with_the_rest_snapshot(client):
    expected = client.get("/api/v1/stations/ST01/snapshot").json()
    with client.websocket_connect("/ws/v1/stations/ST01") as socket:
        actual = socket.receive_json()
    assert actual["cycle"] == expected["cycle"]
    assert actual["station"] == expected["station"]


def test_persistence_survives_application_restart(settings):
    first = create_app(settings)
    with TestClient(first) as client:
        created = client.post("/api/v1/simulation/scenarios/hold").json()
    second = create_app(settings)
    with TestClient(second) as client:
        restored = client.get("/api/v1/stations/ST01/snapshot").json()
    assert restored["cycle"]["cycle_id"] == created["cycle"]["cycle_id"]
    assert restored["cycle"]["lifecycle"] == "ON_HOLD"
    assert restored["cycle"]["conformance"] == "UNKNOWN"


def test_simulation_reset_is_audited(client, app):
    client.post("/api/v1/simulation/scenarios/normal")
    reset = client.post("/api/v1/simulation/reset", json={"actor_id": "operator-1"})
    assert reset.status_code == 200
    assert reset.json()["cycle"]["lifecycle"] == "IDLE"
    assert app.state.repository.audit_count("SIMULATION_RESET") == 1


def test_invalid_resources_are_explicit(client):
    assert client.get("/api/v1/stations/UNKNOWN/snapshot").status_code == 404
    assert client.get("/api/v1/cycles/UNKNOWN").status_code == 404
    assert client.post("/api/v1/simulation/scenarios/unknown").status_code == 404
    assert client.get("/api/v1/alarms?domain=UNKNOWN").status_code == 422


def test_enforcing_cannot_be_constructed_or_loaded(monkeypatch, tmp_path):
    with pytest.raises(ValueError):
        RuntimeMode("ENFORCING")
    monkeypatch.setenv("RUNTIME_MODE", "ENFORCING")
    monkeypatch.setenv("SOP_DATA_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        Settings.from_env()


def test_event_time_buffer_orders_eligible_events_and_appends_late_for_classification():
    from datetime import datetime, timedelta, timezone

    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def item(sequence, offset):
        when = origin + timedelta(seconds=offset)
        return Event(
            event_id=str(sequence), event_type="TEST", source="test", source_instance="test-1",
            source_seq=sequence, occurred_at=when, ingested_at=when, idempotency_key=str(sequence),
        )

    result = EventTimeReorderBuffer(5).order([item(3, 10), item(1, 0), item(2, 8)])
    assert [event.source_seq for event in result.ordered] == [2, 3, 1]
    assert result.late_count == 1
