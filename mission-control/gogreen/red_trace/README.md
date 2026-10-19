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

Run locally (GET only):

```bash
GITHUB_TOKEN=... python mission-control/gogreen/red_trace/red_trace.py \
  --repo GBOGEB/pipeline-automation-hub --per-workflow 300 --root . --out /tmp/red-trace
```
