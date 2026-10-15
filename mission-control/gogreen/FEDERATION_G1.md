# GOGREEN G1 — Mission Control federation-wide, wide-first discovery roll-up

**Owner:** `pipeline-automation-hub/mission-control/gogreen` · **Authority:** read only.

The new `federation_rollup.py` is additive to G0; it does not alter `spine.py`,
`collect_readonly.py`, ABACUS feedback gates or any child repository.

## Difference between the two crosswalks

- **G0:** six repository profiles × selectively targeted eight technical families
  = 42 target cells; historical metadata seed only.
- **G1:** six repositories × the same eleven common federation surfaces
  = 66 comparable *discovery* cells. The difference in denominator means
  `G1-19.70% minus G0-2.38%` is **not** a valid coverage-improvement delta.
- **G1 source discovery:** 13/66 candidate cells identified by existing source
  paths at specific default-branch SHA. Files existing is not proof of tests.
- **G1 native status depth:** 0/66 at the six stated main SHAs. Historical
  successful PR workflows are retained separately and never transferred.
- **G1 artifact-byte proof:** 0/66. Discovery is not linked execution.
- **REX:** all six remain UNKNOWN until a verified canonical source contract is
  identified; a text mention is not enough to classify a producer.

## Evidence dimensions and planning gates

| Axis | Interpretation | G1 state |
|---|---|---|
| Breadth | Exact-SHA source-discovered / 66 eligible repo×surface cells | 13/66 |
| Depth L1 | Exact-SHA run/attempt/job success with typed surface | 0/66 |
| Depth L2 | Independent source-bound uploaded artifact digest + bytes | 0/66 |
| Coverage gain | Matched test numerator/denominator, exclusions and scope | UNKNOWN |
| Roots resolved | Signed EVERRED/LDAB causality and regression proof | UNKNOWN |
| Queue | Six non-atomic API queue counts | 1,341 queued, 12 in-progress (historical snapshot) |
| PCA | Independent comparable observation matrix and eigengap | HOLD |
| BT | Connected real worker-outcome comparison graph | HOLD |
| 3PSTAR | Native method/target validation, not workflow discovery | HOLD |
| QPS | Recipient-side ACCEPT/REJECT/DEFER | DEFER |

The input `samples/federation_g1_observed.json` is a **frozen telemetry
snapshot**, not a current polling endpoint. Refresh source SHAs and collect
new timestamps before making operational decisions. Its six queue samples are
not atomic, so summation describes sampled fleet pressure, not a simultaneous
cross-repository queue guarantee. The pulse ID and UTC time are explicit.

## Reproduce

```sh
python -m unittest discover -s mission-control/gogreen/tests -v
python mission-control/gogreen/federation_rollup.py \
  --current mission-control/gogreen/samples/federation_g1_observed.json \
  --output /tmp/gogreen-g1
```

The producer writes `rollup.json` plus a SHA-256 `manifest.json`.
Its output keeps all metrics and admission dimensions separate, with
`authority_transfer=false`, `worker_dispatches=0`, `admission=HOLD`,
`merge_authorized=false`.

### Disjoint follow-on worker slices

1. **READER / Mission Control:** extract exact-head, per-surface source and
   signed run/attempt/job evidence without mutating repos.
2. **GOLDEN_THREAD / LDAB / LLDB:** join real artifact bytes, diagnostic root
   fingerprints and error receipts; UNKNOWN until genuinely joined.
3. **TEST_PILOT / GOGREEN:** add scope-matched positive regression coverage,
   stress only bounded local/sandbox lanes, and use measured runner budgets.
4. **gg_MATH / PCA / 3PSTAR / BT:** derive inference only after repeated
   eligible observations; do not treat successive status snapshots as IID.
5. **QPS TRIAGE / owner:** independent child decision and governed admission.

Do not open ABACUS PRs, dispatch a worker, cancel a required check, loosen A10,
or claim code coverage improvement based on this discovery census alone.
