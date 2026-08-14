# P0 Software Foundation Execution Plan

Source contract: `V1_IMPLEMENTATION_PLAN.md` V1.4 Camera-only amendment.

Current Runtime Bundle `ST01-P0-R02` binds only simulated Camera/Model/Evidence adapters. `SimulatedDeviceAdapter` remains a contract-test fixture for future expansion and is not an active field device.

## Global Constraints

- No real hardware assumptions or station-specific addresses may be hardcoded.
- The business core consumes only versioned Events through the durable journal.
- Lifecycle, conformance result, and disposition remain separate fields.
- Missing, stale, invalid, or conflicting required evidence moves the Cycle to `ON_HOLD`.
- `ENFORCING` is unavailable in P0. Only `SIMULATION`, `SHADOW`, and `ADVISORY` are valid.
- Camera and model integrations use Adapter Contracts with simulated P0 implementations; future Device Adapter contracts remain inactive.
- The UI exposes lifecycle, conformance, disposition, evidence, and PROCESS/SYSTEM alarm domains separately.

## Task 1: Contracts, SOP Engine, WAL, And Simulated Adapters

Create the Python workspace and implement versioned Event/Evidence contracts, immutable Runtime Bundles, the Cycle state machine, evidence policies, append-only fsync WAL, Adapter protocols, deterministic simulated camera/model/evidence adapters, and an inactive Device Adapter contract fixture for future expansion. Add focused unit tests for normal, nonconforming, hold, abort, disposition, duplicate/late event, conflict, and recovery behavior.

Acceptance: tests pass locally; adapters cannot mutate Cycle state directly; ENFORCING is rejected.

## Task 2: API, Persistence, Evidence, And Simulation Orchestration

Implement FastAPI endpoints and WebSocket snapshots, SQLAlchemy persistence compatible with PostgreSQL and local SQLite tests, alarm domains, append-only audit records, evidence metadata, scenario orchestration, and Docker Compose definitions. Add API and integration tests for all simulated scenarios and dispositions.

Acceptance: backend tests pass; scenario APIs drive the real SOP Engine; PostgreSQL configuration is present; local execution works without Docker.

## Task 3: Web UI

Implement the React/TypeScript/Vite industrial console with ST01 as the first screen. Include station monitoring, simulated live feed, SOP progress, evidence matrix, lifecycle/conformance/disposition display, alarms split by domain, SN traceability, controlled configuration, and explicit simulation controls. Connect to the FastAPI REST/WebSocket contracts and support loading/error/disconnected states.

Acceptance: production build succeeds; core user flows work at desktop and mobile/tablet widths; UI never presents ON_HOLD as NONCONFORMING.

## Task 4: End-To-End Verification And Handoff

Run the full backend and frontend suites, exercise all simulated scenarios through the API and UI, verify persistence and recovery, run browser screenshots, and start local development servers. Record Docker as unverified if the host still lacks Docker.

Acceptance: local P0 flow is usable, tests/build pass, evidence and residual risks are documented, and the user receives working local URLs.
