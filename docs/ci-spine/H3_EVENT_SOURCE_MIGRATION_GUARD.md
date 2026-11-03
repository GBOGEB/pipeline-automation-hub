# H3 — Bounded event-source migration guard (candidate, not production migration)

**Authority and placement:** this code imports `required_gate/gate.py` and uses its
`recheck_names()`, `declared_recheck_names()`, and canonical `ADMISSION.json`.
The sole event-pressure metric remains `mission-control/jade_temple/devops/actions_metrics.py`.
The present `workflow_run` trigger and all enforced checks stay unchanged.

**Baseline:** independent, exact-source canonical T1 was produced in Hub PR #1107,
native run 41474915456 at source SHA `908a34cf54cdd19c15730bf3931515e6a4642833`,
with 345 `GOGREEN Required Gate Re-check` records in the last 1,000 completed
repository records (34.5%, 91 cancelled, 225 skipped, 29 succeeded).
Artifact `mip-h1-canonical-recheck-t1` has its own GitHub SHA-256,
daily digest cache receipts and canonical receipt sha256
`510d40a673ca572206fe2dc54c4f9292656d42ca00385d8e35afce3b1ff33467`.
This is run-record pressure, not billable minutes or missing test results.

## Quantified H3 boundary (what-if only)

The current fixed-count cohort contains 655 non-recheck records and 345 recheck
records. Holding unrelated event creation constant, a replacement policy that
eliminates only `x` recheck records produces the **new** denominator
`(1000 - x)`, not 1,000. Therefore `(345-x)/(1000-x) <= 0.20` needs
**at least 182 genuinely uncreated run records** (then 163/818 ~= 19.93%).
This is an arithmetic sensitivity, *not* a forecast or qualified T2. Real
window membership, queue and trigger-population shifts must be measured anew.
A job-level `if` or `cancel-in-progress` change does NOT prevent workflow
records from being created.

## H3 migration preflight

The guard requires two distinct checked-out Git worktrees: candidate source
(`--root`) and the independently pinned base (`--base-root`) whose exact
`git rev-parse HEAD` matches `--base-sha`. No candidate-controlled
`ADMISSION.json` can reclassify the base. Read-only example:

```bash
python mission-control/gogreen/required_gate/h3_event_retirement_guard.py \
  --root . --base-root ../owner-base-checkout \
  --base-sha "<40-character exact GitHub base SHA>" \
  --out /tmp/h3_guard.json
```

Optional `--proposed /tmp/proposed_names.json` accepts a JSON string list.
A candidate trigger removal, policy demotion, absent/unparseable enforced
source, or marker-vs-actual-workflow_run mismatch must remain HOLD.

Native two-checkout pilot `MIP H3 Base-Bound Retirement Preflight` completed
successfully in Actions run `41615589717` at PR #1112 head
`f14ddd65476bbcdc394d8b61c870e39ba33d8802`. The dedicated
proof-only workflow was removed after that testflight instead of adding a
persistent extra workflow to an already-stale ADMISSION census (21 unlisted
versus a maximum of 20 under the existing test). The source guard and its
unittest suite remain for governed checks. This proof does **not** certify
an event-source retirement or merge.

Future source-owned implementation requires:
1. A source-side candidate notifier/dispatcher that fires **only** when
   independently proven necessary on the exact PR head, with authenticated
   stable run/attempt identity and a bounded dispatch idempotency policy;
2. Native replay of genuine RED recovery, delayed first-pass workflows, wrong
   SHA/PR/attempt/ZIP and no eligible event loss;
3. A separately authorized replacement for one enforced workflow at a time,
   with the previous listener retained until an independently qualified
   handoff and rollback path are accepted;
4. Identical-method T1/T2 and repeat pulse showing fewer **created** run
   records, not merely fewer executed jobs; check queue/run/cancel rates
   independently; preserve required protection and independent owner review.

No migration, permission expansion, branch-rule change, merge or gate demotion
is authorized by this proof. `H3_TRIGGER_RETIREMENT_HOLD`.
