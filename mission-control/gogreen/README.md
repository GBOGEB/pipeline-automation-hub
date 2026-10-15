# GOGREEN G0 — Positive evidence, resilience and wide-first testflight

**Status:** read-only implementation on a draft branch; no downstream admission implied.  
**Owner:** pipeline-automation-hub / Mission Control; local producers retain their repository authority.  
**Separation:** EVERRED fixes independently demonstrated RED roots; CODE PURPLE protects P0 recovery and gates; GOGREEN observes real GREEN, widens proof and proposes controlled stress experiments.

## Goal and differentiated value

Use a PASS as a *starting observation*, never as evidence of operating margin or statistical stability. Establish the **observed unit** (`run_id`, `run_attempt`, `job_id`, `source_sha`, tool/config, scope) before planning expansions. Track tests, root causes, artifact bytes, coverage, concurrency and approval as separate, non-substitutable dimensions.

| Programme lane | Main question | GOGREEN treatment |
|---|---|---|
| CODE PURPLE | Is critical recovery/governance safe? | Treat as non-compensating admission boundary |
| EVERRED | Why did a root generate more REDs? | Read first-red/burndown receipts; return unexpected REDs to canonical root owner |
| **GOGREEN** | What passing behavior can be repeated, broadened and challenged safely? | Source-bound GREEN -> target selection -> bounded experiments -> measured resilience and coverage |
| Mycelium top-down | Which proof atoms and dependencies matter? | Publish projection proposals, never substitute for CODEX acceptance |
| Golden Thread bottom-up | Where did the evidence come from? | Keep exact SHA/run/job/artifact and renderable deterministic manifest |
| Recursive mid-plane | Where is the next legal scout/probe/replay? | Staged, disjoint worker packets with path leases reserved only after approval |
| QPS TRIAGE | Can child claims be adopted? | Default `DEFER` until child owner verifies native source bytes and contract |

## Wide before deep: six repo profiles / 42 target cells

Source candidates are declared explicitly in `samples/fleet_g0.json`: ABACUS, CODEX, pipeline-automation-hub, DOCX_RTM_Automation, cryoplant-project and gg_MATH. Eight *possible* telemetry families: CI contract, security, coverage, runtime, artifact, federation, QPS TRIAGE and mathematical model. Some repositories deliberately target fewer than eight families.

The seed is a historical **ABACUS PR #1965** native success ([run #38601239666](https://github.com/GBOGEB/ABACUS/actions/runs/38601239666), run number 8, attempt 1, job #115980730837). The same four-file Ruff 0.17.0 census has 11 before, 0 after, 11 resolved and 0 introduced occurrences; artifact #11912899138 declares a SHA-256 archive digest. This is **metadata-confirmed source-scoped PASS**, not independently downloaded/byte-verified proof, not 8 independent successes, not a broad coverage gain, not a resolved-root count.

### G0 executable spine (Python stdlib, no external account access)

```bash
python -m unittest discover -s mission-control/gogreen/tests -v
python mission-control/gogreen/spine.py \
  --input mission-control/gogreen/samples/fleet_g0.json \
  --out /tmp/gogreen-g0
python mission-control/gogreen/spine.py --out /tmp/gogreen-g0 --verify
python mission-control/gogreen/synthetic_probe.py \
  --total 32 --queue-depth 4 --workers 2 --cycles 2 \
  --output /tmp/gogreen-g0/synthetic_queue.json
```

Output is deterministic and manifest-hashed: `evidence.json`, `scout_packets.json`, `federation_hooks.json`, `summary.md`, `manifest.json`. Source observations have no fabricated timestamps, tests or denominators. `UNKNOWN` is not zero. Run number is never treated as independent-trial count.

`synthetic_probe.py` is a **local toy workload** to verify the queue/backpressure probe's bounded mechanics. Its two or three cycles share a process; they cannot establish real CODEX, ABACUS, QPS, Docker, RHEL or asyncio capacity. The negative control deliberately injects a fault. No production queue, service or port is targeted.

### Scope and metric contract

- **Breadth:** targeted repo-family cells, observed cells, native green metadata observations and independently byte-verified observations have distinct denominators. Unobserved = unknown.
- **Depth:** line/branch coverage deltas require matched scope, tool, config, test selection, exclusions, numerator and denominator; otherwise delta = `null`.
- **Repeatability:** unique `run_id`/`run_attempt`/`job_id` and repeated comparable suite runs; multi-attempt retries or same-process probe cycles do not prove independent trials. No reliability CI from a single PASS.
- **Stress:** limit concurrency, queue depth, tasks, iterations and wall time in an approved isolation arena before invoking actual worker load. Observe queue waits, high-water mark, tail latency, successful requests, error rate and recovery time with exact environments.
- **Fan-out:** discovery may widen; mutation may not. A confirmed root has one EVERRED owner. A GOGREEN scout/probe has one bounded leaf and no write permission by default.
- **Evidence economics:** count wall time, runner minutes, avoided duplicate runs, attribution quality and actual delta per new test; optimize meaningful yield rather than raw workflows launched.

## WBS: horizontal census then vertical deepening

| Wave | Owner/role | Deliverable | DoV boundary |
|---|---|---|---|
| G0 Scout | SCOUT + READER | Six-repo profile, 42-cell candidate matrix, deterministic manifest | Native producer unit/negative tests, exact workflow SHA, artifact digest |
| G1 Verify | TEST_PILOT + GOLDEN_THREAD | Download-and-hash original artifact; test-run evidence to named owner | Verified internal bytes and matching source/test contract, no admission transfer |
| G2 Expand | PROBE_PLANNER + RELIABILITY | Bounded sandbox queue/asyncio/concurrency test, 2-3 controlled cycles | Actual isolated runtime/env telemetry, source-bound metrics, no prod impact |
| G3 Compare | TEST_PILOT + TRIAGE | Matched coverage delta, repeatability samples, regressions and negative controls | Comparable denominators, identified unit and uncertainty, root ownership |
| G4 Federate | MYCELIUM + GOLDEN_THREAD | Typed child proposal/receipts to CODEX and QPS | ACCEPT/REJECT/DEFER controlled by recipient; NO implicit promotion |
| G5 Control | GATE_KEEPER + owner | Safeguarded rollout and recurrence sentinel | Native exact-head checks, eligible reviews and server-side required gates |

## Disjoint packets and anti-duplication

G0 returns `READ_ONLY_DISCOVERY` packets per unobserved repo-family cell plus a distinct ABACUS `CANDIDATE_REPEAT_AND_ARTIFACT_BYTE_PROOF` packet. All carry `dispatch_authorized=false`, `path_lease=null`, `worker_state=STAGED_NOT_LAUNCHED`. Before permitting later mutation, verify the current repository head, source-file overlap, canonical repair lineage and the actual owner. Group work by shared owner, **not** by PR count.

Role_PLATERS are *role definitions*, not authenticated Crew launches. Distinct roles: `SCOUT`, `READER`, `PROBE_PLANNER`, `TEST_PILOT`, `RELIABILITY`, `GOLDEN_THREAD`, `MYCELIUM`, `TRIAGE`, `GATE_KEEPER`.

### Hooks and trust boundaries

`federation_hooks.json` declares CODEX Mycelium's projection, pipeline hub Golden Thread's adapter, ABACUS EVERRED's observation producer, QPS TRIAGE's DEFER intake and gg_MATH's optional provider. It is a proposal contract, not a live connection or qualified cross-repo receipt. Source repo controls source truth; destination repo owns its own acceptance.

**GOGREEN invariants:** `authority_transfer=false`, `merge_authorized=false`, `security_waiver=false`, no automatic rerun/dispatch, no alteration to required gates, no stress on real services, no local synthetic result counted as child resilience. Real new failures go to EVERRED; retained PASS remains historical and cannot bypass current-head admission.

## Next native testflight

`.github/workflows/gogreen-g0.yml` runs only on changed GOGREEN files or explicit manual dispatch. Verify tests, proof output and negative controls, synthetic probe, and upload the exact-head evidence bundle. Native GitHub Actions is required before claiming implementation DoV. The next implementation slices must reconcile actual producer bytes and allow native `repo+sha+run+job` read-only importer receipts; avoid high-frequency workflow fan-out before baseline cost metrics exist.
