# GOGREEN required gate (N+9): telemetry → trust → authority → gate

One always-reporting PR check (`GOGREEN required gate`) that stands in for the path-filtered PR gates, which cannot be made required directly: a PR that misses a gate's `paths` would wait forever for a check that never reports.

N+8 hard-coded two gates. N+9 closes the `telemetry → trust → authority → gate` control spine over the whole fleet, reusing the existing modules rather than adding new ones:

| Step | Module | What it does |
|---|---|---|
| Telemetry | `../red_trace/red_trace.py` | Master lane (N+8) plus a **merged-PR lane**: the same `classify()` replayed over the result each workflow showed on every merged head *at merge time*. Adds `green_streak`, `nondeterminism` (same-head disagreement, rerun rescue) and an explicit coverage census. |
| Trust | `admission.py` | Per workflow: current state on each lane, green streak since the last red, freshness, nondeterminism, 📌 pins, declared intent (`# gogreen-admission: observe`). |
| Authority | `ADMISSION.json` | Every workflow file gets `ENFORCED`, `OBSERVED` or `EXCLUDED` with reason codes. Omission is not a state. |
| Gate | `gate.py` | Reads the ledger **from the base branch** and enforces `ENFORCED` gates on the exact PR head. |
| Backtest | `backtest.py` | Replays `gate.py`'s own applicability logic against recent merged PRs: what would the gate have answered at merge time, per policy. |

## Admission rules (`admission.py`)

`EXCLUDED` is structural, read from the workflow's own trigger: `SELF`, `NO_PULL_REQUEST_TRIGGER`, `PULL_REQUEST_TARGET_ONLY`, `NOT_FOR_MASTER` (branches filter), `TYPES_SKIP_HEADS`, `UNPARSEABLE`, `DECLARED_EXCLUDE`.

`ENFORCED` needs evidence on at least one lane, and on every lane that has evidence: current GREEN, no nondeterminism, freshest lane exercised within `FRESH_DAYS` (14) with a green streak of at least `MIN_STREAK` (2), and no pinned historical run or artifact.

Anything else is `OBSERVED` with the reason codes that held it back (`RED_NOW_MASTER`, `RED_NOW_PR`, `NONDETERMINISTIC_*`, `GREEN_STREAK_SHORT`, `NOT_EXERCISED_RECENTLY`, `PINNED_EVIDENCE`, `NO_TERMINAL_EVIDENCE`, `DECLARED_INFORMATIONAL`).

**Repair oscillation is not flakiness.** A gate that went red and was repaired several times is `FLAKY` by flip count, but if every head gave one consistent answer it is still enforceable. Only a head that gave both answers, or a rerun that rescued a red, marks it nondeterministic.

**Ratchet.** An entry the previous ledger enforces (before a ledger exists: the N+8 pair) is never auto-demoted. When its evidence turns bad it stays `ENFORCED` with `INCUMBENT_RATCHET` and a `demotion_candidate` list. Weakening a gate is an `OWNER` decision.

**Runtime debt.** Every `uses:` reference is resolved to its `runs.using`. The map lives in the ledger, so CI regeneration stays offline. `node20_uses` lists the workflows still on Node 20 actions, which GitHub currently forces onto Node 24 with a deprecation warning.

## Gate semantics (`gate.py`)

- **Policy source.** `--policy base` (the default when `--base-sha` is given) reads `ADMISSION.json` at the exact base SHA through the contents API. A PR that edits the ledger takes effect only after the owner merges it.
- **Triggers.** `paths`, `paths-ignore`, `branches`, `branches-ignore` and `types` are read from the PR-head workflow file. `!` patterns follow GitHub's ordered semantics.
- **Polling.** One `/actions/runs?head_sha=` listing per poll, however many gates are watched. N+8 made one call per gate per poll.
- **Visibility.** `OBSERVED` gates are snapshot when the enforced ones finish: a red one becomes a `::warning`, never a failure. Unlisted workflows are reported as such. The gate never waits for itself.
- **Fail closed.** An enforced gate with no terminal run on the exact head by the deadline fails.

## Depth census (N+10, `depth.py`)

Static census of the control spine's own reach, with an explicit ZERO bucket per dimension. Unknown is never counted as zero, and zero is never hidden.

| Dimension | Measures | ZERO bucket |
|---|---|---|
| Breadth | workflows with terminal red/green evidence, and on how many lanes | `ZERO_EVIDENCE` |
| Depth | tests each workflow executes: unittest (via `scripts/zero_test_gate_audit.py`), pytest and `node --test` by static count | `ZERO_TESTS`, `UNKNOWN_TESTS` |
| Penetration | tracked files whose change fires a PR gate, using `gate.applies()`. *Targeted* counts path-filtered gates only, because a catch-all gate reaches 100% while saying nothing about a file | `ZERO_TARGETED` files, `ZERO_PENETRATION` (dead filter) |
| Tested | source modules a test file imports or is named after. QA/validator harnesses and config/data files are counted separately | `ZERO_TESTED` modules |

`--ledger none` derives dispositions from workflow files alone, using the admission scope rules, so the same census runs on any federation repo without evidence. The red-trace workflow publishes it in the job summary from the live ledger proposal.

## Run locally (GET only)

```bash
python mission-control/gogreen/red_trace/red_trace.py --repo GBOGEB/pipeline-automation-hub \
  --root . --pr-lane 100 --out /tmp/rt
python mission-control/gogreen/required_gate/admission.py --root . \
  --master-trace /tmp/rt/red_trace.json --pr-trace /tmp/rt/red_trace_pr.json \
  --resolve-runtimes --out /tmp/ADMISSION.json --summary /tmp/admission.md
python mission-control/gogreen/required_gate/backtest.py --repo GBOGEB/pipeline-automation-hub --root . \
  --pr-trace /tmp/rt/red_trace_pr.json --ledger /tmp/ADMISSION.json --limit 60 --out /tmp/bt
python mission-control/gogreen/required_gate/depth.py --root . --ledger /tmp/ADMISSION.json --out /tmp/depth
python mission-control/gogreen/required_gate/depth.py --root ../ABACUS --ledger none --out /tmp/depth-abacus
```

`merge_authorized=false`. A ledger proposal, a backtest FAIL and a gate PASS are each one observation, not an admission. Requiring `GOGREEN required gate` on `master`, accepting a promotion and demoting a gate are owner decisions.
