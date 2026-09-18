# MissionControl DROP-IN v4 — QPS W249 LEG5 sequential 3P* then MIP

Start from repository authority.

## Refresh
- `GBOGEB/cryoplant-project main`
- QPS #923, #1258, #1266, #1357
- QPS PR #1486
- `GBOGEB/pipeline-automation-hub master`
- this receiver PR and its exact-head workflow proof

## Read
1. `mission-control/qps-triage-ultra/leg5/QPS_LEG5_W249_CURRENT_v1.yaml`
2. `mission-control/qps-triage-ultra/leg5/QPS_LEG5_W249_SEQUENTIAL_3PSTAR_MIP_RECEIVER_v4.yaml`
3. `mission-control/qps-triage-ultra/leg5/QPS_LEG5_W249_SEQUENTIAL_DEPENDENCY_GRAPH_v4.json`
4. this file
5. QPS `triage/w249/QPS_W249_LEG5_3PSTAR_SEQUENTIAL_EXECUTION_v0.4.yaml`
6. QPS `triage/w249/QPS_W249_LEG5_RUNNER_RETRY_EXHAUSTION_RECEIPT_v0.3.yaml`
7. QPS `triage/w249/QPS_W249_LEG5_MIP_SEQUENTIAL_EXECUTION_v0.4.yaml`

## Preserve
- QPS #1486 merged at `604f282ab0ca249f660507bf9567da26b7579d09`.
- LEG5 remains 7/9.
- authorized manual retries = 2; both were consumed and both remained zero-step.
- fresh automatic #1486 probe run `35358917304` was also zero-step.
- #923 remains the external private-QPS runner-admission gate.
- #1266/#1357 remain open and cannot be closed by parent proof.
- no more blind private-QPS retries until owner-side Actions admission materially changes.
- authority_transfer=false and all formal credit deltas remain zero.

## Next legal child transition
Material owner-side admission change -> unchanged Release Runner Probe -> require `runner_id != 0 && steps > 0 && validator_runner_selector_compatible` -> #1266 validator -> 8/9 -> #1357 validator -> 9/9 -> scope exhaustion -> #1258 closure evaluation.
