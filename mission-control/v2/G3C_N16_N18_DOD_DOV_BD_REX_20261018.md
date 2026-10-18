# Mission Control G3C — N+16 through N+18 convergence

**Status:** SOURCE-IMPLEMENTED / EXACT-HEAD NATIVE CI PENDING / ADMISSION HOLD  
**Upstream source owner:** hub PR #631, base head `f3bd255ad926e9ae970ff9226853545da271a3f1`  
**Canonical G3P envelope:** hub #604; #620 → #621 → #631. This child does not introduce a new Mission, SSOT, runner or source authority.

## Pulse plan and actual implementation

| Pulse | Slice | Implemented code | Independent result |
| --- | --- | --- | --- |
| N+16 | Qualification | `g3c_convergence.py` matches three local G3A checkpoints by immutable population of 122 obligations; source digests and owner/nonpromotion guards | Local testflight passed; native CI pending |
| N+17 | Negative controls | `test_g3c_convergence.py` covers false admission, denominator drift, forged proof, inconsistent counts, plateau and missing commit, CLI manifest hashes | 16 local tests passed; 85/85 statement and 12/12 branch obligations in local measured module; native proof pending |
| N+18 | Controlled return | New path-filtered Python 3.11/3.12 exact-head CI, G3A graph adapter reuse and pinned historical #701 producer source | Consumer CODEX #1089 remains draft / separate owner; cannot count accepted N |

## Measured historical local coverage (not G3C native proof)

G3A's unchanged-source test series: N+13 `107/122`, N+14 `109/122`, N+15 `119/122`. Difference: `+12/122 = +9.83607 percentage points`. Increments `+2` then `+10` covered obligations, an **accelerating local coverage *count***, not evidence of terminal CI convergence, regression stability, six-sigma capability, stationary time-series or productivity trend.

The historical third pulse has a **null `source_commit` in the committed proof JSON**. Do not infer it from the PR narrative. The graph has eight declared family nodes, three declared edges, zero claims of authenticated federation; verified native edge denominator UNKNOWN.

## Build and reproduce

```sh
python -m pip install coverage==7.13.3
PYTHONPATH=mission-control/v2 python -m coverage run --branch --source=g3c_convergence -m unittest discover -s mission-control/v2 -p test_g3c_convergence.py -v
python -m coverage json -o /tmp/g3c-coverage.json -q
python mission-control/v2/n3_master_dags_bridge.py --manifest mission-control/federation-atlas/G3A_N13_N15_MASTER_DAGS_COMPAT_20261017.json --expected-hub-base 296c2dfa6c81849038b3d378d2e179dfdb4ca8a4 --out /tmp/g3a-declared-graph.json
python mission-control/v2/g3c_convergence.py --proof mission-control/federation-atlas/G3A_N13_N15_LOCAL_PROOF_20261017.json --graph /tmp/g3a-declared-graph.json --producer-observation mission-control/federation-atlas/G3C_N16_N18_PRODUCER_PIN_20261018.json --out-dir /tmp/g3c-out
```

Outputs: `g3c-convergence.json`, `g3c-convergence.html`, SHA-256 manifest. The HTML uses fixed integer covered counts, no inferred interpolation/decay model and no browser write actions. Playwright visual review remains separate and UNKNOWN until actually executed.

## Reentry and gating

The P-process producer historical exact head `16a548759d879d30b4a7435e587e2c97bf0e3d9b` ran [39133186022](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39133186022), artifact `12139440079`. It is a **historical** snapshot, not the latest PR #701 head. CODEX consumer [#1089](https://github.com/GBOGEB/CODEX/pull/1089) and issue [#1088](https://github.com/GBOGEB/CODEX/issues/1088) require independent qualification.

Before admission: receive both Python native runs and artifacts at exact head; independent review; terminal predecessor stack qualification; owner restores ABACUS [#1860](https://github.com/GBOGEB/ABACUS/issues/1860) required checks/reviewer protections. No merger, cross-repo mutation, root-closure credit or engineering QPS acceptance from this child.

**Global programme:** HOLD. Three source-level implementation slices are not three admitted consecutive G3P pulses.
