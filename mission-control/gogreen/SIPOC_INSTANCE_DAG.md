# SIPOC Process Instances — bounded DAG / asyncio pilot

This read-only planner extends the existing Mission Control subtype-workflow
candidate (#561/#563). It does not replace `PROCESS_LANES_v1.json`, the Method
Atlas, GitHub Actions, REX, or independent repo ownership.

## Identity: template is not an instance

A canonical `lane:stage` is a **template**. An instance adds a distinct ID,
incarnation, SIPOC role (S/I/P/O/C), source repository and exact source SHA,
owner issue, mode, declared dependencies, success predicate and optional lease.
The same `DMAIC:ANALYZE` Process template can have several **P incarnations**,
for example CODE_MAROON, Python compatibility, workflow governance and CI
telemetry. They may be disjoint, parallel and marked `ASYNCIO`; none is
launched merely because it is planned.

- **Fan-out:** independent READY instances of a common predecessor may appear
  in one bounded wave, subject to max-parallel and per-repository limits.
- **Fan-in:** a successor is not planned until every declared predecessor is
  included in an earlier wave. A pending/blocked parent propagates HOLD.
- **Lease safety:** mutating *proposals* with the same root or overlapping
  parent/child path in one repo cannot share a wave. No filesystem writes occur.
- **Feedback:** next-pulse observations use separate `NEXT_PULSE` edges,
  never same-wave cycles. Cycles, unknown sources and duplicate incarnations
  fail closed.
- **Asyncio:** an optional bounded, zero-I/O synthetic replay validates wave
  barriers and fault propagation; it is NOT authenticated worker execution,
  a fleet capacity measurement or independent statistical trial.

## Reproduce

From the repository checkout (Python stdlib only):

```bash
python -m unittest discover -s mission-control/gogreen/tests \
  -p 'test_sipoc_instances.py' -v
python mission-control/gogreen/sipoc_instances.py \
  --input mission-control/gogreen/samples/sipoc_instance_wave_20261016.json \
  --atlas mission-control/federation-atlas/PROCESS_LANES_v1.json \
  --out /tmp/cbd-sipoc --synthetic-replay
```

The producer writes an input-byte and canonical-atlas SHA-256 bound JSON
receipt plus digest and a separately labeled synthetic replay record.
The sample references historical exact heads; it is a **declared scenario**,
not a current live census, dispatched Crew flight, accepted root closure or
project admission. A changed source requires a new observation and rerun.

## Required subsequent adaptation

For an actual P execution, assign the appropriate owner and backend to a
separate authorized producer. Native execution shall provide run ID, attempt,
job/step identities, artifact bytes, pass/fail and resource timing. Join outputs
only once their exact source identities match. A scheduled proposal is never a
verified proof, and N+1 forecasts never overwrite the N checkpoint.


## G7 positive-execution provenance / temporal SIPOC (17 Oct 2026)

This is an **additive read-only projection** of the existing SIPOC instance planner. Producer:
`success_graph/runner_telemetry.py`; frozen native evidence:
`success_graph/samples/native_success_20261017.json`. It consumes the canonical
`mission-control/grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json` roster,
not an independently invented Top21 register. The source-head census is 7+7+7
repositories (21/21 current head metadata discovered), **not** a promotion.

**Observed input:** 24 source-bound successful workflow run IDs from five named
families, each with run number/attempt/source SHA and UTC event time; ten
first-page native job records with nine successful runner-executed jobs and one
explicit skipped job. Selected runner occupancy is 235 seconds, not billable
runner time or steady-state throughput. Two separate native RED controls are
retained, not filtered into a false-green population.

**S → I → P → O → C typed edges:**

| SIPOC | Node | Evidence / next behavior |
|---|---|---|
| S | `S` | Canonical source roster and repo SHA metadata, no CI promotion |
| I | `I` | Exact source/run/attempt/job observations with optional runner-time |
| P | `P_SOURCE` | Deduplicate actual run/job IDs; compare sequence, gap and maturation span |
| P | `P_REVERSE` | 51 seeded positive/adverse contracts; native testflight required |
| P | `P_REX` | Declared return to EVERRED/REX owner for real red fingerprint |
| P | `CAP_*` | Eight code capability nodes with entrypoint, input, output and next expansion |
| O | `O` | Hash-bound JSON metrics, graph, offline HTML and artifact manifest |
| C | `C` | Source owner and independent security/governance/QPS admission, default HOLD |

Edges identified from native source metadata are `OBSERVED`. Application or
cross-repository consumers lacking proof of artifact bytes/owner sign-off are
`DECLARED`. No DAG cycle, mutation path lease, remote executor or observer
may convert a DECLARED edge to a receipt through a successful workflow label.

**Positive MANTRA:** Start from six observed consecutive QPS native Debug DAG
run numbers 181–186 and six observed gg_MATH kernel successes, then strengthen
backend-specific negative tests, adverse inputs, workflow step containment,
same-scope coverage and independent-source control. Other workflows contain
unobserved run-number gaps and cannot claim uninterrupted streaks.

**Native producer:** `.github/workflows/gogreen-g7-success-graph.yml` runs
module-scoped branch/statement coverage, 51 tests, exact-head output hashing
and a separate GitHub run/attempt-bound receipt. It neither replaces
`sipoc_instances.py`, writes canonical BD/REX, relaxes status gates, nor
publishes Pages. See [G7 capability and pruning ledger](success_graph/README.md).
