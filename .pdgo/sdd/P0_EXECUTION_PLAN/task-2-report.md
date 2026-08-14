# Task 2 Report: API, Persistence, Evidence, And Simulation Orchestration

## Status

DONE

## Delivered

- FastAPI REST and WebSocket contracts for station, cycle, alarm, evidence, SOP, disposition, and simulation workflows.
- SQLAlchemy persistence for SQLite development and PostgreSQL deployment configuration.
- Six-step ST01 P0 SOP driven by the real `SopEngine` with normal, nonconforming, process hold, system hold, aborted, and rework scenarios.
- Event-time batch reordering and late-event classification boundary.
- Append-only event/disposition/audit records and mutable current read models.
- Local evidence placeholders with SHA-256 metadata stored outside the database.
- Docker Compose, API Dockerfile, station adapter configuration, environment template, and environment lock record.

## Verification

```text
PS> .\.venv\Scripts\python.exe -m pytest services\core-runtime services\api-server
......................................................                   [100%]
54 passed, 1 warning in 4.39s
```

The warning is Starlette's deprecation notice for its current TestClient re-export and does not affect runtime behavior.

`python -m compileall -q services/core-runtime/core_runtime services/api-server/sop_api` completed successfully.

## Constraints Preserved

- `ENFORCING` is rejected by the shared RuntimeMode contract and environment loading.
- Simulation controls emit Events into the journal and real engine; the API never writes Cycle state directly.
- Lifecycle, conformance, and disposition remain separate in persistence and responses.
- `ON_HOLD` retains `UNKNOWN` conformance for missing evidence and system failure scenarios.
- PROCESS and SYSTEM alarms remain separate in database queries and UI contracts.

## Residual Risk

- Docker is unavailable on the development host, so Compose and PostgreSQL container execution are delivered but unverified locally.
- P0 evidence files are deterministic placeholders rather than encoded camera media.
