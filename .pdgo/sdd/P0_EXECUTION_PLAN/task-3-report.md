# Task 3 Report: Industrial Web UI

## Status

DONE - independent re-review accepted

## Delivered

- React 19, TypeScript, Vite, Ant Design industrial console with ST01 as the default route.
- Station monitor with a nonblank simulated Canvas feed, SOP progress, current action, evidence matrix, evidence assets, health status, and explicit simulation controls.
- Lifecycle, conformance, and disposition are rendered as separate fields. `ON_HOLD` is rendered as `UNKNOWN` / not verifiable and never as `NONCONFORMING`.
- PROCESS and SYSTEM alarms remain separate in station and alarm-center views; acknowledgements capture a reason.
- Quality disposition workflow preserves the original conformance result while recording REWORK, SCRAP, or AUTHORIZED_RELEASE separately.
- SN traceability with cycle table, evidence/alarm detail, and a lazy-loaded ECharts result distribution.
- Read-only React Flow configuration view for SOP graph, Runtime Bundle, and simulated Adapter Contracts.
- REST initialization, WebSocket updates, retry, loading, empty, stale-after-5-seconds, and disconnected-after-15-seconds states.
- Responsive desktop, tablet, and mobile navigation/layouts.
- Multi-stage web image and Nginx proxy configuration added to Docker Compose.
- Checked-in Playwright configuration and focused browser regression suite that can start or reuse the API and UI servers.

## Verification

```text
PS> npm.cmd run lint
> eslint .
Exit code: 0

PS> npm.cmd run build
> tsc -b && vite build
5589 modules transformed
built in 15.53s
Exit code: 0
```

Playwright CLI browser verification against `http://127.0.0.1:5173` covered:

- `/station`, `/alarms`, `/trace`, and `/config` primary routes.
- normal, nonconforming, missing-evidence hold, system hold, aborted, and rework scenario transitions.
- quality disposition, alarm acknowledgement, trace detail, and controlled configuration interactions.
- WebSocket `LIVE`, `STALE`, `DISCONNECTED`, and recovery behavior.
- A fresh system-hold run displaying lifecycle `ON_HOLD`, conformance `UNKNOWN`, SYSTEM alarm domain, and database health `UNAVAILABLE`.
- Browser console result: 0 errors and 0 warnings.

Independent review fix round 1 added a reproducible browser gate:

```text
PS> npm.cmd run test:e2e
Running 6 tests using 1 worker
6 passed (18.7s)
```

The suite asserts primary routes, all six simulation outcomes, separate lifecycle/conformance/disposition semantics, dynamic SHADOW/disconnected shell state, explicit configuration API failure, alarm-to-evidence navigation, and the mobile no-overlap boundary.

TDD evidence for the fix round:

- RED: API contract test failed with `KeyError: 'runtime_bundle'`.
- RED: shell test could not find `边缘服务断开`.
- RED: configuration failure test could not find `配置加载失败`.
- RED: alarm workflow could not find `查看证据`.
- GREEN: 4 focused API mode/bundle tests, lint, production build, and all 6 browser tests passed.
- RE-REVIEW: accepted with no remaining findings (`task-3-rereview-report.md`).

Responsive visual evidence:

- `output/playwright/station-desktop.png`
- `output/playwright/station-tablet.png`
- `output/playwright/station-mobile.png`
- Desktop simulated feed sampled 22,116 nonzero pixels and 64 colors.
- Mobile simulated feed sampled 6,348 nonzero pixels and 85 colors at 368x276.
- Trace chart sampled 2,438 nontransparent pixels and 20 colors at 794x300.

## Constraints Preserved

- No station hardware address, PLC register, camera URL, model path, or vendor SDK is hardcoded.
- UI simulation actions call the API scenario endpoints; they do not mutate Cycle state locally.
- `ENFORCING` is not exposed.
- P0 controlled configuration explicitly states the simulation-only boundary and hardware Adapter Contract handoff.
- Green, amber, red, and gray state colors always include text and/or icons.

## Residual Risk

- Vite reports two chunks over 500 kB after minification: the lazy trace chunk is about 508 kB and the shared chunk is about 595 kB. This is non-blocking for the P0 factory-LAN target but should be profiled before low-bandwidth remote deployment.
- Docker is unavailable on this host, so the web container and Nginx proxy configuration are delivered but unverified locally.
- Browser screenshots and Playwright session artifacts are intentionally git-ignored verification outputs.
