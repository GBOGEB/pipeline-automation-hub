# Method Atlas operational coverage witness — N0 controlled pilot

**Owner and boundary.** This extends the existing
[Method Atlas](main.md), [local broker](broker.py) and
[coverage contract](coverage_contract.py). It does NOT own their
metric definitions, Kahn scheduler, central dashboards, EVERRED history,
N6 notifications, watcher triggers, source SSOT, release or GitHub dispatcher.

## 1. Purpose: how much working behavior is actually experienced?

A source file can have excellent line/branch coverage without ever running in
the pipeline the user cares about. A workflow may complete successfully while
its core mission has no verified output. This witness keeps these separate.

| Axis | Accepted observation | Not justified |
|---|---|---|
| C0 tracked source | Exact-head Python, JS/TS, workflow, TOML, YAML, JSON and test inventory | All files active |
| C1 static reachability | Declared YAML steps and literal workflow-to-file links | All imports or runtime expressions traced |
| C2 instrumented branches | Matched source SHA, coverage tool and exact test population | 100% test coverage implies mission acceptance |
| C3 DAG operation | Actual trigger, needs, workflow_call, job and step chain | Valid YAML means it ran |
| C4 production outcome | Stable input/output SHA, repeated real command and counterfactual response | Test mocks establish fleet causality |
| C5 negatives/out of order | Explicit input rejection and negative regression at real code path | Rejected fixture repairs a live issue |
| C6 EVERRED/full cohort | Native run, attempt, job, step and all outcomes including failure/cancellation | One green rerun closes a persistent root |
| C7 federation | Verified peer head, owner protocol, child result, digest and acceptance | Remote URL is proof of execution |
| C8 security | Bandit, Semgrep, OSV, CodeQL, negative abuse and least-privilege tests | Finding count is coverage |
| C9 watcher liveness | Source-bound heartbeat, job execution, alert acknowledgment and no duplicates | Cron declaration means always present |
| C10 scaling | Matched-workload throughput, queue p95, time, cache, costs and root recurrence | 32 workers automatically beat 16 |

**Zero classification.** ZERO_INSTRUMENTED requires an instrumented executable
with eligible denominator >0 and zero hits. An unlinked file is instead
UNREACHABLE_CANDIDATE_STATIC, UNINSTRUMENTED, NOT_COLLECTED, DESELECTED,
STARTUP_FAILURE_NOT_EXECUTED, ARCHIVE_OUT_OF_SCOPE or DYNAMIC_EDGE_UNKNOWN.
YAML/JSON/TOML are contracts: instrument the *consumer's* branch decisions,
schema validation and failure path. JavaScript/TypeScript use their native
V8/Istanbul coverage, not Python numbers. Existing coverage_contract.py
owns UNKNOWN-versus-ZERO and all percentage arithmetic.

## 2. Existing orchestrators and knowledge custodians

[OPERATIONAL_SURFACES_v1.json](OPERATIONAL_SURFACES_v1.json) records seven
repo boundaries and 21 identified source surfaces: orchestrators, brokers,
security/functional oracles, custodians, observers and presenters.
The registry is for navigation and candidate routing, not an authority
transfer. All external peers are EXTERNAL_NOT_ACCESSED until an owner-bound
source SHA, permissions and privacy contract exist. The public Hub does
not import private QPS workbook bytes, source SHAs, action rows or bidder data.

Method Atlas already has check/build/plan/run-local, typed dependency
precedence, path leases and artifact receipts. GoGREEN already owns
red-trace, outcome and scale-dock series; the launcher owns its page.
This pilot adds a causal I/O **witness**, not a duplicate metric engine.

## 3. Tangible actual execution — real G9 outcome processor

Run from the exact checked-out Hub commit:

~~~bash
HEAD=$(git rev-parse HEAD)
python -m pip install --disable-pip-version-check pyyaml==6.0.3
python -m unittest discover -s mission-control/federation-atlas/orchestration \
  -p test_operational_witness.py -v
python mission-control/federation-atlas/orchestration/operational_witness.py \
  --root . --head "$HEAD" --out /tmp/method-atlas-witness
~~~

The production G9 entrypoint is executed five times: a frozen 57-native-run
historical population, exact replay, valid counterfactual (one success becomes
failure), and two bad inputs (incomplete denominator and out-of-order clock).
Expected original: **46 success / 10 failed / 1 cancelled**; counterfactual
must become **45 / 11 / 1** with unchanged denominator 57. Bad inputs must
fail. Same input, same head must reproduce identical semantic and member
hashes.

Outward: operational_witness.json, index.html (purple offline review),
causal_dag.mmd, manifest.json (member SHA256). Full source cohort and
temporary counterfactual input are **not** copied into the artifact.

## 3A. Two isolated measured coverage populations

The native workflow now installs the same existing pinned coverage.py 7.13.3
and records **two separate branch-aware files**:

- `witness_code_coverage.json` — unit tests PLUS the witness driver itself,
  scoped only to `operational_witness.py`; this is implementation coverage,
  not runtime effectiveness.
- `g9_actual_runtime_coverage.json` — only the five actual invocations of the
  existing `outcome_flight.py` production CLI (baseline, identical replay,
  one valid counterfactual and two rejected bad inputs). This gives **observed
  production-path statement and branch arcs**, not a mock unit-test statistic.

`coverage_measurements.json` lists independently measured/covered statement
and branch counts, percentages, source head and SHA of each coverage JSON.
A missing/zero-eligible or non-branch-aware population fails closed. Native
workflow logs show the exact measured source and process outcomes.

Do not combine the two denominators or promote either to whole-repository,
cross-branch, seven-repository, operational critical-path or causal-root
coverage. G9 instrumented *historical fixture operation* is still not
proof of live cross-repo production behavior.

Proof levels: STATIC_DECLARED_ONLY; LOCAL_DIRECT_PRODUCTION_EXECUTION;
CONTROLLED_FIXTURE_CAUSAL_SENSITIVITY. GitHub-native proof only after
separate authenticated run/job/step readback. No claim of actual fleet
dispatch, causal-root closure or original QPS source correction.

## 4. SIPOC

~~~mermaid
flowchart LR
  S["S: Source owner"] --> I["I: Exact-head input + SHA"]
  I --> P["P: Existing Method Atlas inventory"]
  I --> G["P: Run real G9 production command"]
  G --> O["O: Output and manifest SHA"]
  I --> X["Counterfactual + invalid source"]
  X --> G
  O --> V["C: Idempotence + negative oracle"]
  P --> V
  V --> H["C: Independent owner HOLD"]
~~~

## 5. Scaling and watcher-of-watchers frontier

No new scheduler, webhook, notification or GitHub mutation is installed.
This PR testflight is PR/manual only and leaves N6's exclusive notification
owner unchanged.

- Reuse real Method Atlas run-local next, instrument task-level source SHA,
  generator outputs, declared I/O, disjoint leases, ordered fan-in and
  failed job/step. Do not claim remote dispatch.
- Extend to externally provided read-only peer roots and owner receipts,
  one frozen SHA per repo per pulse. Missing private source stays UNKNOWN.
- Compare **16 versus 32 read-only scouts** over four matched native pulses.
  Record accepted outputs per wall time, queue p50/p95, execution p50/p95,
  paid runner minutes, cache warm/cold, failure/retry, write contention and
  original root recurrence. Keep writer concurrency unchanged. Existing
  sipoc_scale_gate.py owns mutation-scale qualification.
- Reuse dependency caches by immutable lockfile digest, platform and runtime;
  test hash tamper and forced cold-cache. Prefer process simplification and
  removing duplicated package installs before increasing parallelism.
- Make watcher-of-watchers a **read-only consumer** of canonical watch
  receipts: stale/missing observer, missing negative oracle, zero-step job,
  duplicate notification owner or unacknowledged alert become advisory HOLD.
  It must not become a second N6 watch.
- Display source, DAG, run/attempt/job/step, effect, negative controls and
  admission separately in the existing Method Atlas / GOGREEN navigation.

**Admission:** independent review, exact-head real native CI, active RED
canary, owner disposition. Formal engineering credit remains 0; release
and merge admission are HOLD, regardless of local green.
