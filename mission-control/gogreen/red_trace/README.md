# GOGREEN red-trace

Read-only ledger of red/green transitions on `master`, computed from GitHub Actions history.
Workflow: `.github/workflows/gogreen-red-trace.yml`. It publishes the job summary (visible from any PR's Checks tab) and an artifact holding `red_trace.json` and `red_trace.md`.

| Class | Meaning |
|---|---|
| `EVERRED` | Never green in the fetched window. With ⁺ (history truncated) this means never green *in window*, not never green ever. |
| `GREEN_TO_RED` | Red now and green earlier. `break` = last green head → first red head, the suspect commits between them, and the first failing job/step. |
| `RED_TO_GREEN` | Green now, red earlier in the window. `red_episodes` records the recovery head and the red duration in hours. |
| `FLAKY` | Three or more green/red flips in the window. |
| `STABLE_GREEN` | No red in the window. |

Evidence rules:
- **One outcome per head:** each (workflow, head SHA) counts once, using its latest run and attempt.
- **Terminal results only:** cancelled, skipped and in-progress runs are never counted as green or red.
- **Shared break roots:** when one head SHA turns several workflows red, it is listed once as a candidate root.
- **`stale`:** the last observation is more than 3 days old. A replay is needed before it says anything about HEAD.
- **📌 Pinned evidence:** the workflow asserts on a hard-coded historical run or artifact ID. Artifacts expire, so the gate can turn red with zero code change, and its suspect list is then meaningless.
- **No credit:** suspects are not a causal attribution, and the ledger gives no root-closure credit.
- **`green_streak`:** consecutive green heads since the last red: how stable a gate has been since its last repair.
- **`nondeterminism`:** `same_head_disagreements` (one head SHA gave both green and red) and `rerun_rescues` (a rerun turned red into green). This separates a nondeterministic gate from repair oscillation, which `FLAKY` alone cannot.
- **`census`:** the full workflow listing is the denominator. A workflow that never ran on the branch is listed as `unobserved`, never counted green.

## Merged-PR lane (N+9, `--pr-lane N`)

About half of the hub's PR gates never run on `master`, so the master lane cannot see them. The merged-PR lane replays the same `classify()` over a second sequence: for each of the last N merged PRs, the result each workflow showed on the merged head **at merge time** (the `merged_outcome_census` chronology). It costs one paginated `/actions/runs?head_sha=` listing per PR.

| Field | Meaning |
|---|---|
| `merge_matrix` | Per merged PR: `{workflow: conclusion at merge}`, plus `merge_after_s`, the seconds from the first check starting to the merge. |
| `pending_at_merge` | The run had not completed when the PR merged. |
| `rerun_after_merge` | The attempt that existed at merge was overwritten by a later rerun, so its result is unknown. |
| `merged_with_red` / `merged_with_pending` | PRs merged while a check was red or still running. |

Neither of the two pending states counts as green or red. Output: `red_trace_pr.json` (`gogreen.red_trace.pr_lane.v1`) and `red_trace_pr.md`. The master-lane file keeps schema `gogreen.red_trace.v1` (additive fields only), so the ABACUS EVERRED adapter is unaffected.

Consumers: `../required_gate/admission.py` (trust → authority) and `../required_gate/backtest.py`.

Run locally (GET only):

```bash
GITHUB_TOKEN=... python mission-control/gogreen/red_trace/red_trace.py \
  --repo GBOGEB/pipeline-automation-hub --per-workflow 300 --root . --pr-lane 100 --out /tmp/red-trace
```
