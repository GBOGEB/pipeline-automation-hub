# Global Code Purple

_GitHub readback 2026-10-18 13:27 UTC · not lifted: 2 of 5 lift criteria met. Generated from the same model as the page and the deck; anchors match the PDF links._

## Contents

- A · Situation
- B · How to read
- C · Protocol
- D · Lifecycle
- E · Admission
- F · Coverage
- G · Evidence & structure
- H · Lift & method
- [Process stages](#process-stages) · [Nodes](#nodes) · [Triggers](#triggers) · [Edges](#edges)

## Process stages

<a id="stage-1"></a>
### Stage 1 · Mobilise (Define)

Nodes: [N01](#node-n01) Mission controller · [N02](#node-n02) Asymmetric allocation

- **Entry:** A trigger: new head, schedule or material change
- **Actions:** Census authorities and capabilities; Pin the exact SHA; Budget lanes by the cost of a red
- **Exit:** Pinned SHA pair; Lane budget

<a id="stage-2"></a>
### Stage 2 · Collect and run (Measure)

Nodes: [N03](#node-n03) Async I/O · [N04](#node-n04) Parallel worker lanes

- **Entry:** SHA pinned, lanes budgeted
- **Actions:** Collect prior evidence asynchronously from REX, KEB and GitHub; Run parse, Ruff, SARIF and smoke lanes in parallel
- **Exit:** Evidence bundle; Per-lane results

<a id="stage-3"></a>
### Stage 3 · Pre-match (Measure)

Nodes: [N05](#node-n05) Preflight + pre-match cache

- **Entry:** Lane results and evidence bundle
- **Actions:** Reuse results proven for the identical commit and inputs; Run only the remainder
- **Exit:** Preflight receipt (local, not CI proof)

<a id="stage-4"></a>
### Stage 4 · Triage (Analyse)

Nodes: [N06](#node-n06) First completed material red?

- **Entry:** Preflight receipt
- **Actions:** Rank findings with DOW; Assign one of four failure classes; Select the first completed material red
- **Exit:** One red to repair, or none

<a id="stage-5"></a>
### Stage 5 · Repair loop (Improve)

Nodes: [N07](#node-n07) Isolated repair · [N08](#node-n08) Impacted retest

- **Entry:** One classified red
- **Actions:** Fix the smallest common cause on an isolated branch; Retest the impacted set; Write a new exact-commit receipt
- **Exit:** Repaired head submitted for verification

<a id="stage-6"></a>
### Stage 6 · Admission (Control)

Nodes: [N09](#node-n09) Exact-head final admission · [N10](#node-n10) All non-waivable gates green?

- **Entry:** Exact head with no known material red
- **Actions:** Run CI, Codex review and PR Feedback Gate on the exact SHA; Evaluate non-waivable gates only
- **Exit:** Admit, or hold

<a id="stage-7"></a>
### Stage 7 · Hold and learn (Control)

Nodes: [N11](#node-n11) HOLD · [N12](#node-n12) REX · KEB evidence

- **Entry:** A non-waivable gate red or pending
- **Actions:** Record the reason in REX; Update recurrence and lessons; Plan the next pulse
- **Exit:** Hold record; Next pulse on material change

<a id="stage-8"></a>
### Stage 8 · Merge and prove (Control)

Nodes: [N13](#node-n13) Single-flight merge controller · [N14](#node-n14) Exact-main CI · metrics · [N15](#node-n15) Output N · control

- **Entry:** Admission green
- **Actions:** Merge one PR at a time; Run exact-main CI, record metrics, read back the publication; Write the census row
- **Exit:** Output N becomes input N+1

## Nodes

| ID | Node | Role | Phase | Stage | Triggers | Artefact | Status |
|---|---|---|---|---|---|---|---|
| <a id="node-n01"></a>N01 | **Mission controller**: Takes global input N, discovers authorities and capabilities, and resolves producer, consumer, receipts and scope for this pulse. | Authority | Define | [1](#stage-1) | [T01](#trig-t01) [T07](#trig-t07) [T12](#trig-t12) | `CODEX GLOB.yaml, .mesh/MESH_DOCK.yaml` | Seeded / committed |
| <a id="node-n02"></a>N02 | **Asymmetric allocation**: Pins the exact head under test and spends compute where a red is most expensive. Cheap I/O runs async; costly checks get dedicated lanes. | Authority | Define | [1](#stage-1) | [T01](#trig-t01) | `Seed YAML execution contract` | Seeded / committed |
| <a id="node-n03"></a>N03 | **Async I/O**: Collects existing evidence without blocking the workers, including prior receipts that may already prove a result. | Process | Measure | [2](#stage-2) | [T02](#trig-t02) | `REX and KEB lookups, GitHub check readback` | Not implemented |
| <a id="node-n04"></a>N04 | **Parallel worker lanes**: Runs parse, Ruff, SARIF security scans and smoke in parallel with no shared state. | Process | Measure | [2](#stage-2) | [T02](#trig-t02) | `ABACUS scripts/testpilot_preflight.py, pre-commit, Ruff, Bandit, Semgrep` | Partial |
| <a id="node-n05"></a>N05 | **Preflight + pre-match cache**: Merges worker output with collected evidence. A result already proven for the identical commit and inputs is reused instead of rerun. | Process | Measure | [3](#stage-3) | [T03](#trig-t03) | `Receipts keyed by exact commit and input hash` | Not implemented |
| <a id="node-n06"></a>N06 | **First completed material red?**: Ranks findings and selects the first completed red that matters, classified as source defect, inherited debt, review capacity or runner failure. | Gate | Analyse | [4](#stage-4) | [T03](#trig-t03) [T03b](#trig-t03b) [T04](#trig-t04) | `ABACUS DOW` | Not implemented |
| <a id="node-n07"></a>N07 | **Isolated repair**: Fixes the smallest common cause only. Security-sensitive governance changes cannot approve themselves. | Repair | Improve | [5](#stage-5) | [T05](#trig-t05) | `Smallest-scope branch` | Not implemented |
| <a id="node-n08"></a>N08 | **Impacted retest**: Reruns only what the repair touches and writes a new exact-commit receipt. | Repair | Improve | [5](#stage-5) | [T06](#trig-t06) | `Impacted test set` | Not implemented |
| <a id="node-n09"></a>N09 | **Exact-head final admission**: Independent verification on the exact head SHA, including required reviews. | Process | Control | [6](#stage-6) | [T08](#trig-t08) [T09](#trig-t09) | `GitHub Actions, PR Feedback Gate, Codex review and security review` | In progress |
| <a id="node-n10"></a>N10 | **All non-waivable gates green?**: Admits only when every non-waivable check and review is green on the same SHA. Waivable checks are recorded, not counted. | Gate | Control | [6](#stage-6) | [T10](#trig-t10) [T11](#trig-t11) [T13](#trig-t13) | `Required checks and reviews at exact head` | On hold |
| <a id="node-n11"></a>N11 | **HOLD**: Logs the blocking reason to REX and plans the next pulse. A material change re-enters at the mission controller. | Hold | Control | [7](#stage-7) | [T09](#trig-t09) [T11](#trig-t11) [T12](#trig-t12) | `REX entry` | On hold |
| <a id="node-n12"></a>N12 | **REX · KEB evidence**: Holds evidence identity, recurrence counts and reusable lessons. Async I/O reads from it at the start of each pulse. | Evidence store | Control | [7](#stage-7) | [T11](#trig-t11) [T16](#trig-t16) | `CODEX KEB and REX` | Partial |
| <a id="node-n13"></a>N13 | **Single-flight merge controller**: Merges one admitted PR at a time so no head goes stale behind another merge. | Admitted path | Control | [8](#stage-8) | [T13](#trig-t13) [T14](#trig-t14) | `Merge queue discipline` | Not reached |
| <a id="node-n14"></a>N14 | **Exact-main CI · metrics**: Proves main is green after the merge, records metrics and reads the published result back. | Admitted path | Control | [8](#stage-8) | [T15](#trig-t15) [T16](#trig-t16) | `GitHub Actions on main, Pages` | Not reached |
| <a id="node-n15"></a>N15 | **Output N · control**: Becomes the input of iteration N+1 through governed reconciliation (⊕). | Authority | Control | [8](#stage-8) | [T15](#trig-t15) | `Iteration census` | Not reached |

## Triggers

| ID | From → to | Event | Guard | Action | Nodes | Wired today |
|---|---|---|---|---|---|---|
| <a id="trig-t01"></a>T01 | Test pending → Set-up | Pull request opened or synchronised, or a push | Head SHA pinned | Start CI; mark the gate pending | [N01](#node-n01) [N02](#node-n02) | Partly wired: GitHub starts CI on these events. ABACUS's gate re-evaluates on workflow_run and review events, not on synchronize (#1858 thread, line 599). |
| <a id="trig-t02"></a>T02 | Set-up → Run lanes | Preconfig receipt written | Python runtime, dependencies and devcontainer resolved | Start the parallel lanes | [N03](#node-n03) [N04](#node-n04) | Proposed: Needs the .self harness. |
| <a id="trig-t03"></a>T03 | Run lanes → Retry | A lane goes red with class runner or infrastructure (5xx, runner lost, cancelled) | No earlier retry on this SHA | Re-run the failed jobs once; log a REX entry | [N05](#node-n05) [N06](#node-n06) | Manual: Re-run all jobs button on GitHub. |
| <a id="trig-t03b"></a>T03b | Retry → Run lanes | Retry finished | — | Results re-enter triage | [N06](#node-n06) | Manual: Same re-run. |
| <a id="trig-t04"></a>T04 | Run lanes → Debug | Red classified as a source defect that doesn't reproduce locally | It is the first completed material red | Re-run that lane with debug on (debugpy, LLDB) and keep the trace | [N06](#node-n06) | Partly wired: CODEX main already runs LLDB, lldb-dap and debugpy lanes (green); nothing triggers them from a red yet. |
| <a id="trig-t05"></a>T05 | Debug → Fix | Root cause recorded | Fix scope is the smallest common cause | Branch from the exact head | [N07](#node-n07) | Manual: — |
| <a id="trig-t06"></a>T06 | Fix → Integrate | Impacted retest green, with an exact-commit receipt | No governance change approves itself | Push to the PR head | [N08](#node-n08) | Manual: — |
| <a id="trig-t07"></a>T07 | Integrate → Test pending | New head on the PR | — | Old receipts retired; the cycle restarts at T01 | [N01](#node-n01) | Wired: Push event. |
| <a id="trig-t08"></a>T08 | Run lanes → Admission | All lanes terminal | No material red | Exact-head CI plus Codex code and security review | [N09](#node-n09) | Partly wired: CI is automatic. The Codex review request is manual, and the allowance is exhausted. |
| <a id="trig-t09"></a>T09 | Admission → PR follow-up | Review thread, Codex comment or gate failure | — | Answer, fix, or record an owner residual-risk decision | [N09](#node-n09) [N11](#node-n11) | Partly wired: Detection is wired: pr-feedback-gate.yml runs on pull_request_review and review-comment events. The response is manual. |
| <a id="trig-t10"></a>T10 | PR follow-up → Admission | Thread resolved or review submitted | Zero unresolved threads | The gate re-evaluates | [N10](#node-n10) | Wired: Review events trigger the gate. |
| <a id="trig-t11"></a>T11 | Admission → HOLD | A non-waivable gate is red or pending (e.g. Codex outage) | — | Write the HOLD record and a REX entry | [N10](#node-n10) [N11](#node-n11) [N12](#node-n12) | Partly wired: The gate holds. The REX record is manual. |
| <a id="trig-t12"></a>T12 | HOLD → Test pending | Scheduled readback, or a material change | Something changed since the last pulse | Start a new pulse | [N11](#node-n11) [N01](#node-n01) | Proposed: Needs a scheduled task (burndown item 7). |
| <a id="trig-t13"></a>T13 | HOLD → Merged | Owner decision with a written residual risk | Owner only. One-time ruleset bypass, restored straight after the merge | Squash-merge, restore the ruleset, write REX | [N10](#node-n10) [N13](#node-n13) | Manual: Owner edits ruleset 24494381. This is the proposed path for #1858. |
| <a id="trig-t14"></a>T14 | Admission → Merged | All non-waivable gates green on the same SHA | Single-flight: no other merge in progress | Squash-merge | [N13](#node-n13) | Partly wired: ABACUS: ruleset enforces it. CODEX: no ruleset; #984 merged with 4 reds. |
| <a id="trig-t15"></a>T15 | Merged → Federate | Exact-main CI green and read back | Consumer listed in MESH_DOCK | Open an adoption PR in the peer repo; write the census row | [N14](#node-n14) [N15](#node-n15) | Proposed: Not built. For #984, CODEX main has 2 post-merge reds to clear first. |
| <a id="trig-t16"></a>T16 | Merged → Merged | Exact-main CI measures coverage at or above floor + 1 point | Exact-main CI green; measurement on the same SHA | Raise the coverage floor to the measured value; write the census row (total, breadth, depth, per area) | [N14](#node-n14) [N12](#node-n12) | Proposed: Not built. Today the gate is a fixed 75% and fails on every PR. |

## Edges

| ID | From → to | Type | Meaning |
|---|---|---|---|
| E01 | [N01](#node-n01) → [N02](#node-n02) | Sequence | Every pulse starts at the controller. |
| E02 | [N02](#node-n02) → [N04](#node-n04) | Sequence | Costly checks get dedicated lanes. |
| E03 | [N02](#node-n02) → [N03](#node-n03) | Sequence | Cheap I/O runs without blocking the workers. |
| E04 | [N04](#node-n04) → [N05](#node-n05) | Sequence | Per-lane JSON and SARIF results. |
| E05 | [N03](#node-n03) → [N05](#node-n05) | Evidence | Prior receipts offered for exact-match reuse. |
| E06 | [N05](#node-n05) → [N06](#node-n06) | Sequence | Merged preflight result. |
| E07 | [N06](#node-n06) → [N07](#node-n07) | Material red | A completed material red exists. |
| E08 | [N07](#node-n07) → [N08](#node-n08) | Material red | Repair committed on an isolated branch. |
| E09 | [N08](#node-n08) → [N09](#node-n09) | Sequence | Retest receipt goes to exact-head verification. |
| E10 | [N06](#node-n06) → [N09](#node-n09) | Pass | No material red among completed checks. |
| E11 | [N09](#node-n09) → [N10](#node-n10) | Sequence | Check and review states on the exact head. |
| E12 | [N10](#node-n10) → [N11](#node-n11) | Hold | A non-waivable gate is red or pending. |
| E13 | [N10](#node-n10) → [N13](#node-n13) | Pass | Every non-waivable gate is green on the same SHA. |
| E14 | [N13](#node-n13) → [N14](#node-n14) | Pass | One PR merged at a time. |
| E15 | [N14](#node-n14) → [N15](#node-n15) | Pass | Main green; metrics and publication read back. |
| E16 | [N11](#node-n11) → [N12](#node-n12) | Evidence | Blocking reason recorded. |
| E17 | [N12](#node-n12) → [N03](#node-n03) | Evidence | Lessons and receipts reused in the next pulse. |
| E18 | [N11](#node-n11) → [N01](#node-n01) | Hold | A material change triggers the next pulse. |
| E19 | [N15](#node-n15) → [N01](#node-n01) | .self recursion | Validated output becomes input N+1 through ⊕. |
