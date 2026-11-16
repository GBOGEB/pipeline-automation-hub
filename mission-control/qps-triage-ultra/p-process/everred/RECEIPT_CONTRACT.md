# EVERRED source-bound semantic root receipts — bounded pilot

This is an **additive companion**, not a replacement for `roots.yaml`, `harvest.py`, `taxonomy_root_occurrence.py`, the REX/HIST-BD ledgers, or Kahn scheduling owner. Existing canonical root IDs are preserved. Matching a signature to a root is a **candidate attribution**, not causal proof.

## Invocation

```bash
python mission-control/qps-triage-ultra/p-process/everred/receipt_contract.py --events /tmp/qualified-events.json --catalog mission-control/qps-triage-ultra/p-process/everred/roots.yaml --heads /tmp/exact-heads.json --out /tmp/everred-receipt
python -m unittest discover -s mission-control/qps-triage-ultra/p-process/everred -p test_receipt_contract.py -v
```

Events are JSON records, each requiring `repo`, 40-hex `sha`, `target_ref` (for example `pull/2746`), `workflow`, `job`, `step`, `failure_predicate`, `config_scope`, `run_id`, `run_attempt`, `job_id`, `step_number`, timezone-aware `observed_at`, `conclusion`, and `executed_steps`. The exact-head file maps `GBOGEB/repo@target_ref` to live provider-read head SHA. The existing EVERRED harvester does **not** populate all of these fields. A separate native readback adapter must obtain missing fields, not fill them synthetically. Missing head -> `HEAD_UNKNOWN`. Mismatched head -> `STALE_HEAD`.

## Root and occurrence semantics

* Fingerprint is SHA-256 over normalized `repo/workflow/job/step/failure_predicate/config_scope`. This is a **candidate family key**; distinct predicates or configuration scopes never alias automatically.
* One delivery identity is `(repo, run_id, attempt, job_id, step_number)`. Duplicate identical deliveries count once; mutated identity fails closed.
* `action_required`, `queued`, `skipped`, `cancelled`, `neutral` and zero executed steps are never positive execution proof.
* `REGRESSION_VERIFIED` label requires negative and positive distinct URL receipts on exact head, nonzero execution and eligible independent review. **This offline tool cannot authenticate supplied URLs or reviewers**: only fresh provider reads may promote the label as trusted portfolio evidence.
* Every occurrence has `ADMISSION_HOLD`, and every root stays `root_closed=false`. A green test, merged PR or dashboard is not formal root closure.

## Outputs and boundaries

`root_receipt.json` contains deterministic SHA, distinct root candidates, occurrences, stale/current labels and DAG layers. `root_receipt.html` separates root proof from admission. These files are generated locally and should not be published when they contain private source data. The committed files contain no private readbacks or secrets.

Kahn-ready initial lanes are `normalize`, `negative`, and `badge`, which join at `integrate` -> `native` -> `independent` -> `admission`. The module provides graph validation and disjoint-write checking, **not** worker dispatch or owner authority.

## DoD / DoV

- [x] Local deterministic deduplication, same-root recurrence, distinct causes, A-B-A replay, stale/unknown SHA, unexecuted case, missing proof, review isolation, false-green, Kahn cycle and writer collision tests.
- [ ] Native CI PASS at the final PR head and required contexts checked.
- [ ] Native provider-readback adapter and negative/positive source receipts verified independently.
- [ ] Existing EVERRED/REX governance owners accept candidate mapping and badge semantics.
- [ ] Independent exact-head reviewer approval, accepted policy/owner decisions and real negative RED-block/positive GREEN-admit canaries.

**Disposition: MERGE_ADMISSION_HOLD / NO_MERGE** until external conditions qualify.