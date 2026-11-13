# N3 — governed warm handler execution inside the existing Method Atlas broker

**Status:** implementation candidate, not source-owner admission.

This pilot is the controlled continuation of N2/N2.1 scaling proof in
[PR #1251](https://github.com/GBOGEB/pipeline-automation-hub/pull/1251).
It uses existing source families:

- Method Atlas broker: \`broker.py::run_local\` (single scheduler/lease owner).
- Method Atlas source-contract processor: \`main.py::validate_profile\`.
- GOGREEN native outcome producer: \`outcome_flight.py::build\`.
- Method Atlas runtime replay UI: \`runtime_evidence.py::render\`.
- Legacy broker policy: \`BROKER_POLICY_v1.json\` maximum **4** workers.
- Existing N1 merged \`read_scout_scale.py\` native fleet gate (not satisfied here).

**No replacement scheduler, queue SSOT, watcher, cost metric, local max-worker
change, tokenized remote action, source mutation or GitHub dispatch.**

## 1. What N3 actually experiences

The real existing broker runs the exact same four-task Kahn DAG in both
backends:

~~~mermaid
flowchart TD
    P["Source SHA + policy pin"] --> A["Method Atlas validate_profile()"]
    P --> G["GOGREEN G9 build()"]
    A --> J["ALL: read, hash, semantic join"]
    G --> J
    G -. invalid census, invalid clock or post-producer tamper .-> X["Rejected; join BLOCKED"]
    J --> V["Existing read-only execution replay"]
    V --> O["Source owner HOLD"]
~~~

**Cold** handlers invoke the existing CLI entrypoints in new Python processes.
**Warm** handlers invoke those *same* processor functions imported once into
this local Python process. In either case the real broker:
1. checks registered handlers, input/output contracts and typed path leases;
2. applies Kahn topological ordering, dependency requirements and worker
   admission under the original \`max_workers=4\`;
3. records actual start, verify, ready-wait, finish, failed and blocked events;
4. invokes an independent output validator BEFORE an ALL-dependent successor
   becomes eligible.

For positives, the profile processor verifies source graph/ports and emits
\`source-check.json\`; G9 produces its actual 4 files plus manifest using
the frozen 57-run complete historical source. The join verifies exact
profile and G9 current member SHA256 and G9 semantics before writing
\`join.json\`. The joined bytes must be **identical** across worker levels,
across cold/warm backends and across repeated same-variant pulses.

For negatives, either census mismatch or impossible temporal order must
fail the actual G9 producer. Method Atlas profile still succeeds but
\`join\` is **blocked** and writes no artifact. In two additional cases
(one warm2 and one cold2) a valid G9 product is corrupted *between*
producer completion and broker verification; the broker must fail the
\`output_contract\` phase and block the join. No false-green receipt.

## 2. Actual workload and measured parameters

Four source-aligned pulses with six local broker modes:
\`cold1, cold2, cold4, warm1, warm2, warm4\`.
Pulse 1 and 3 use the original G9 baseline; pulse 2 and 4 use one valid
success-to-failure counterfactual. Their paired negatives alternate
incomplete native census and out-of-order clock evidence.

Required total = 4 pulses × 6 modes × (1 positive DAG + 1 negative DAG)
+ 2 post-producer corruptions = **50 actual broker executions**.

Each DAG has four real broker task states; if all pass as designed:
- **24** positive DAGs, with verified profile + G9 + join products;
- **24** invalid G9 DAGs, with G9 failed and join blocked;
- **2** post-producer tamper DAGs, with output_contract failure and join blocked;
- 200 task states recorded (successful, failed and blocked distinctly);
- 24 verified joins; 26 expected negative blocked joins.

Report median *positive DAG wall-clock seconds* separately by local
worker count and backend, plus broker ready-wait p95, max concurrent
tasks, output SHA, source SHA and warm import/bootstrap time. The
cold-to-warm ratio per matched worker count is descriptive only.

Warm modules are preloaded before the timed DAG trials and their one-time
bootstrap cost is reported separately, NOT silently considered zero.
The pulse count is from one runner and is **not** four independent GitHub
jobs; the existing merged N1 gate remains HOLD until authenticated
source-matched native job/attempt evidence is supplied.

## 3. Run without remote dispatch

From a clean exact-head checkout:

~~~bash
HEAD=$(git rev-parse HEAD)
python -m pip install --disable-pip-version-check pyyaml==6.0.3
python -m unittest discover -s mission-control/federation-atlas/orchestration \
  -p test_warm_broker_pilot.py -v
python mission-control/federation-atlas/orchestration/warm_broker_pilot.py \
  --root . --head "$HEAD" --pulses 4 --out /tmp/n3-broker-review
~~~

Review:
- \`n3_receipt.json\`: per-mode, per-pulse, per-task source/head, broker
  DAG states, negative phases, join hashes, timings and bounded metrics;
- \`index.html\`: compact purple decision dashboard;
- \`runtime-replay.html\`: **existing Method Atlas replay controller**,
  showing the real broker timeline and states; no tasks launched by UI;
- \`n3_dag.mmd\`: semantic edges for source, producers, join and oracle;
- \`manifest.json\`: SHA256 of every outward member.

The original historical G9 input rows and private engineering sources
are NOT exported. This is source-bound local evidence, not an authenticated
GitHub native run/job receipt or QPS review authority.

## 4. DOV / DoD and recursive scaling frontier

| Gate | Completion criterion |
|---|---|
| N3-01 Broker ownership | Existing \`broker.run_local\` called for every trial; max_workers<=4; same policy unchanged |
| N3-02 Two real processors | Method Atlas profile + G9 real CLI/callable each exercised, no mocks in the main trial |
| N3-03 DAG output parity | 24 positive joins, exact source SHA and member bytes, same hash per source variant across all modes |
| N3-04 Negative causal guards | 24 invalid G9 cases plus 2 post-producer corruptions, wrong-success blocked; join NEVER runs on rejected prerequisites |
| N3-05 Replay | Existing runtime_evidence.render used with recorded broker events; no live actions in HTML |
| N3-06 Cost vs concurrency | Median wall, ready-wait p95, actual max-running, one-time warm bootstrap for 1/2/4; compare within same runner |
| N3-07 Native QA | Nonzero adversarial unit suite and exact-head GHA native proof, independent review, effective protection |
| N3-08 Owner admission | No source owner transfer, merge authorization or four-independent-native-pulse fleet scale promotion without explicit decisions |

After N3, the next genuine frontier is a **second language/repository**
(TypeScript DOCX queue, or approved CODEX pipeline) with an authorized
owner-supplied exact-source execution bridge. Compare input/output contracts,
idempotence, security, retention, and causal negative controls across the
two repos before scaling tokenized actions. No private file inference.

**Disposition:** \`N3_REAL_LOCAL_BROKER_PILOT / MERGE_HOLD /
NATIVE_FLEET_SCALING_UNQUALIFIED / FORMAL_CREDIT_0\`.
