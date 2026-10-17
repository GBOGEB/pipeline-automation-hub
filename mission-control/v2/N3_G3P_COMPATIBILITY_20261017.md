# CODE PURPLE — N3 telemetry compatibility with canonical G3P

**Control owner:** Mission Control v2 on `master`.
**Disposition:** Read-only consumer adapter / transitional telemetry; NOT a second scheduler, method registry or admission gate.

## Precedence observed at the final recensus

The concurrently merged `mission-control/v2/G3P_EXECUTION_OPERATOR.md` and `mission-control/v2/g3p_execution.py` establish **G3P** (Governed Three-Pulse Wave) as the canonical new execution envelope under `MC_METHOD_PROFILE_REGISTRY_v1.json`.

The earlier `3P-CONT` and `N3-AUTO` names remain descriptive/compatibility aliases for three consecutive bounded continuation receipts and the hands-off-in-this-session policy. They must not create a second globally authoritative Mission Control method. `3W` continues to mean three *waves*, not three pulses.

| Current historical telemetry | Canonical G3P interpretation | Acceptance |
|---|---|---|
| `n3_continuation.py`, `CBD_GOLDEN_GRAPH_N3_20261017.json` | Historical receipt chain; the pulse ordinals begin at N+1 | Valid as historical ledger only |
| `n3_integrity.py` | Additional advisory input quality/provenance analysis | Non-authoritative |
| `n3_metrics.py` | Denominator-aware read-only consumer view | Cannot promote `EXECUTED_PASS` |
| `n3_dashboard.py` | Offline HTML/SVG evidence presentation | Not a CI or admission gate |
| `CBD_GOLDEN_GRAPH_N6_20261017.json` | Three additive historical progress records N+4..N+6 | No G3P conversion without a separate complete source-bound G3P receipt |
| `G3P_EXECUTION_OPERATOR.md` | Canonical operator semantics | Owning authority |
| `g3p_execution.py` | Canonical G3P validator/projection | Owning authority |

## No-loss, no-double-count boundary

Do not convert an N3 receipt to native G3P `EXECUTED_PASS` without independently proving forecast-before-action UTC timestamps, owners/leases, action start/end times, exact source commit, native run/attempt/jobs and the declared measurement denominators. The old ledger lacks these inputs and deliberately reports UNKNOWN.

No duplicate SSOT. No backfilled forecast, inferred elapsed time, fabricated worker capacity, or promotion of local 61/61 tests into a new GitHub CI result. The prior historical 24/24 is not an independent trial from 36/46/61 re-runs.

**Next legal integration:** consume G3P canonical terminal results through a *read-only* projection after source-owner acceptance, while preserving historic N3 ledger hashes. Native exact-head workflow remains needed; CODEX Zod consumer schemas remain separately governed. Protected merges retain the independent gates.

Tracking: [Mission Control #604](https://github.com/GBOGEB/pipeline-automation-hub/issues/604) · [Stacked metrics PR #611](https://github.com/GBOGEB/pipeline-automation-hub/pull/611).
