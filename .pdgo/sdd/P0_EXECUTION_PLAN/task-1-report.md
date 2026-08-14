# Task 1 Report: Contracts, SOP Engine, WAL, And Simulated Adapters

## Status

DONE

## Changed Paths

- `services/core-runtime/pyproject.toml`
- `services/core-runtime/core_runtime/__init__.py`
- `services/core-runtime/core_runtime/contracts.py`
- `services/core-runtime/core_runtime/wal.py`
- `services/core-runtime/core_runtime/engine.py`
- `services/core-runtime/core_runtime/adapters.py`
- `services/core-runtime/core_runtime/simulation.py`
- `services/core-runtime/tests/test_runtime.py`

## Commit

- `28b226be718330b8dd483ae210fca82112cd155d` `feat: add P0 SOP core runtime`

## Test Command And Output

```text
PS services/core-runtime> ..\\..\\.venv\\Scripts\\python.exe -m pytest
...................                                                      [100%]
19 passed in 0.35s
```

`..\\..\\.venv\\Scripts\\python.exe -m compileall -q core_runtime` also completed successfully.

## Assumptions

- P0 uses one active cycle per engine instance and receives all business inputs as versioned Events.
- Required HARD and STATE evidence with a mismatched expected value is a definite violation; SOFT evidence remains supporting-only.
- A rework attempt preserves the original `NONCONFORMING` fact and starts a new attempt under the same immutable Runtime Bundle.

## Deviations

None. No API, UI, hardware integration, or approved product documents were modified.

## Risks

- Checkpoints are durably written and can be read, but P0 recovery intentionally replays the complete WAL for maximum replay simplicity; checkpoint-based replay truncation can be added after the persistence/API task establishes its durable checkpoint ownership.
- The simulated evidence media files are deterministic placeholders, not encoded video or image content, because P0 has no media pipeline dependency.

## Blockers

None.

## Self-Review

- Confirmed lifecycle, conformance, and disposition are separate contracts and `NONCONFORMING` is retained through REWORK, SCRAP, and AUTHORIZED_RELEASE.
- Confirmed all externally ingested business Events and internally generated timeout Events are appended with flush plus fsync before state application.
- Confirmed duplicate and late Events cannot advance a cycle, evidence failures safely enter `ON_HOLD`, and adapters have no engine reference or state-mutation API.
- Confirmed `ENFORCING` fails enum validation; only `SIMULATION`, `SHADOW`, and `ADVISORY` are accepted.
