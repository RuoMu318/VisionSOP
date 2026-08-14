# Task 4 Report: End-To-End Verification And Handoff

## Status

DONE

## Acceptance Checklist

- [x] The full core/API suite passes.
- [x] Frontend lint and production build pass.
- [x] Checked-in browser tests cover all primary routes and six simulation scenarios.
- [x] `ON_HOLD` remains `UNKNOWN` in API contracts and UI semantics.
- [x] Lifecycle, conformance, and disposition remain separate.
- [x] PROCESS and SYSTEM alarms remain separate.
- [x] Alarm workflow reaches the originating Cycle and evidence assets.
- [x] Runtime mode and connection health are evidence-driven in the global shell.
- [x] Frozen Runtime Bundle and Adapter configuration come from the API.
- [x] SQLite persistence survives application process restart.
- [x] Desktop and mobile screenshots show a nonblank simulated feed and usable layout.
- [x] API and Web development servers are running locally.
- [x] Docker unavailability is recorded rather than presented as verified.

## Fresh Verification

```text
PS> .\.venv\Scripts\python.exe -m pytest services\core-runtime services\api-server
.........................................................                [100%]
57 passed, 1 warning in 4.81s

PS> npm.cmd run lint
> eslint .
Exit code: 0

PS> npm.cmd run build
> tsc -b && vite build
5589 modules transformed
built in 15.53s
Exit code: 0

PS> npm.cmd run test:e2e
Running 6 tests using 1 worker
6 passed (19.8s)

PS> git diff --check
Exit code: 0
```

The Python warning is Starlette's TestClient/httpx deprecation notice. It does not affect runtime behavior.

## Persistence And Recovery

After the API process was stopped and restarted, Cycle `20260814-071015-1b71b4` was queried again through REST:

```text
Lifecycle:      CLOSED
Conformance:    NONCONFORMING
Disposition:    REWORK
EvidenceAssets: 3
Alarms:         1
```

The automated suite also contains application-restart and WAL recovery coverage.

## Browser Evidence

- `output/playwright/station-final-desktop.png`
- `output/playwright/station-final-mobile.png`
- Desktop and mobile images were inspected after the independent review fixes.
- Mobile simulated Canvas: 368x276, 6,348 sampled nonzero pixels, 87 colors.
- Fresh Playwright session: 0 browser errors, 0 browser warnings.

Generated browser artifacts remain git-ignored. The maintained regression suite is committed at `apps/web-ui/tests/e2e/sop.spec.ts`.

## Running Services

- Web console: `http://127.0.0.1:5173/station`
- API: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`

Both services bind to loopback for local development. Docker/Nginx deployment exposes the web entry point on the configured LAN port.

## Residual Risks

- Docker is not installed on this host. Compose, PostgreSQL, the web image, and Nginx proxy are defined but container execution is unverified locally.
- The Vite build reports a roughly 508 kB trace chunk and 595 kB shared chunk. This is accepted for P0 factory-LAN use and remains a future profiling item.
- Evidence media is deterministic P0 placeholder content, not encoded industrial camera video.
- Camera, model, PLC/tool, and evidence adapters are simulated. Hardware readiness is contractual; real probes, mappings, credentials, and acceptance tests remain post-P0 integration work.
- `ENFORCING` remains intentionally unavailable.

## Rollback

No merge or push has been performed. The implementation remains isolated on `codex/v1-software-foundation`. Rollback is a normal Git revert of the P0 feature commits; persistent test data and generated evidence remain outside Git and can be retained for audit.

## Review Disposition

- Task 1 independent review findings were corrected and accepted before downstream work.
- Task 3 independent review returned four findings; fix round 1 was independently re-reviewed and accepted with no remaining findings.
- The final whole-branch contract audit against `P0_EXECUTION_PLAN.md` found no additional Critical or Important issues.
