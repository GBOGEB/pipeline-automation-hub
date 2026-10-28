# CI spine authority index — phase 1 (read-only)

This consolidates the pilot from [PR #989](https://github.com/GBOGEB/pipeline-automation-hub/pull/989) while reusing its now-merged README. No new orchestration layer, scheduler, canonical metric, deployment, branch deletion or automatic merge is introduced.

**Run** (from an exact source checkout):

```bash
python -m unittest tests/test_ci_spine_index.py -v
python scripts/ci_spine_index.py --check --source-sha "$(git rev-parse HEAD)" --out /tmp/ci-spine-index.json
```

The new, narrowly scoped `ci-spine-governed-qa.yml` runs all available CI-spine adversarial tests, asserts exact-head checkout and writes a source-bound receipt. The existing JADE-OID-pinned `zero-test-gate-guard.yml` remains byte-identical to `master` (blob `a19c1295232f1aa3730a68f293a72178dc5ef870`) to avoid stale generated DAG evidence. The new workflow uses pinned actions, read-only permissions and no promotion. Its status badge, if displayed, remains **workflow status only**, not release qualification. The JSON includes the exact checkout SHA, all discovered workflow paths, canonical OIDs, source-text SHA256, existing workflow class, triggers, schedules, job `needs` DAG/layers, seven authoritative anchor bindings and *conceptual* phase edges. The static contract is deliberately restricted to anchors; unbound workflows are counted, and structural anomalies in them are advisory rather than falsely certified. Bound structural faults, missing metric owners, malformed paths and source-SHA mismatches are first-red failures. The CI run and uploaded artifact, not a manually green badge, establish execution evidence.

## Canonical boundaries

| Meaning | Existing owner (no fork) |
|---|---|
| Workflow parse, job DAG, source signals | `mission-control/jade_temple/devops/workflows.py` |
| Workflow classification and run/job timing | `mission-control/jade_temple/devops/actions_metrics.py` |
| Root failure/recovery | `mission-control/gogreen/scale_dock.py` |
| Historical pulses | `mission-control/jade_temple/tools/rolling5.py` |
| Cross-system DAG/SIPOC | `mission-control/jade_temple/tools/cicd_dag.py` |
| Gate zero-test collection | `scripts/zero_test_gate_audit.py` |
| Source-bound FPC, pinning, branch custody | Existing `.github/workflows/first-pass-closure-gate.yml`, `actions-pin-ratchet.yml`, `branch-hygiene.yml` |

The index does **not** calculate CI success rates, runtime distributions, queue duration, current exact-head eligibility, impact of caching, approval status or branch deletion eligibility. Those remain separate evidence. Conceptual edges are **not** proof of GitHub Actions `needs` relations, cross-workflow dependency or scheduler order.

## Next pulse (explicit holds)

- [x] Define and validate source-bound authority anchors; keep unknown and unmapped as unknown.
- [x] Reuse owner implementations rather than copying metrics or DAGs.
- [x] Exercise negative controls; create a PR-triggered receipt through the dedicated, read-only CI-spine workflow.
- [ ] Read back exact-head CI, inspect failures, and independently review noncompensating predicates.
- [ ] Compare runtime-capacity historical branch with already landed v2 contract, scripts and workflow; extract only unique semantics on a separate PR if justified.
- [ ] Connect a read-only dashboard surface to this stable index and existing Actions metrics, keeping all denominators, clock types, evidence classes and as-of dates explicit.
- [ ] Re-census branch hygiene and issue queue on one SHA-bound pulse. Execute no branch deletions from 11 October historical lists.

**Hold:** no release, certification, promotion or merge authority is produced by this index. Read [AGENTS.md](../../AGENTS.md) for L1/L4/L6/L7, and [CI badges and reuse pilot](../../docs/CI_STATUS_BADGES_AND_REUSE_SPINE.md) which is merged on master. This branch does not require PR #989 to land first.
