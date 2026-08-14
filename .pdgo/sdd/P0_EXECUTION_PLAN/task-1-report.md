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

## Concern Resolution

The editable-install metadata concern is resolved by the root `.gitignore` rule `*.egg-info/`.

```text
PS C:\Users\Administrator\Documents\ChatGPT\sop> git check-ignore -v services/core-runtime/sop_core_runtime.egg-info/
.gitignore:5:*.egg-info/    services/core-runtime/sop_core_runtime.egg-info/

PS C:\Users\Administrator\Documents\ChatGPT\sop\services\core-runtime> ..\..\.venv\Scripts\python.exe -m pytest
...................                                                      [100%]
19 passed in 0.32s
```

## Fix Round 1

### Status

DONE

### Changed Paths

- `services/core-runtime/core_runtime/contracts.py`
- `services/core-runtime/core_runtime/engine.py`
- `services/core-runtime/core_runtime/simulation.py`
- `services/core-runtime/tests/test_runtime.py`

### Commit

- `b0e8875c868ed66717d82c4e136068b340830ef4` `fix: preserve P0 runtime safety invariants`

### Commands And Exact Output

The newly added safety regressions were run before the implementation change:

```text
PS services/core-runtime> ..\..\.venv\Scripts\python.exe -m pytest tests/test_runtime.py
14 failed, 18 passed in 0.75s
```

After the implementation and final post-closure lateness regression:

```text
PS services/core-runtime> ..\..\.venv\Scripts\python.exe -m pytest tests/test_runtime.py
.................................                                        [100%]
33 passed in 0.53s
```

`..\..\.venv\Scripts\python.exe -m compileall -q core_runtime` completed successfully.

### Resolution

- Rejected Evidence remains retained for audit but is revalidated against the active cycle, frozen Bundle, validity window, freshness window, and rework attempt before it can satisfy a requirement.
- A Cycle-level `NONCONFORMING` fact is retained through completed rework and cannot be replaced by an abort from `AWAITING_DISPOSITION`.
- The Bundle is frozen only at `CYCLE_STARTED`; lifecycle, timeout, and disposition Events require the frozen Bundle and mismatches are classified for manual review.
- Per-source-instance sequence and event-time watermarks classify out-of-order and outside-window inputs without applying their transition.
- Recovery creates a durable `RECOVERY_HOLD` Event, so a second replay reconstructs the same hold and alarm.
- Simulations assert exact normal, nonconforming, hold, aborted, and completed-rework outcomes.
