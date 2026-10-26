# Three-view Issue Expedition / DoD-DoV plan

This is an additive read-only consumer of Mission Control #308 (issue expedition), #324 (measured PCA/BT), #372 (root and proof lifecycle), #604 (evidence graph), QPS #481 and the canonical gg_MATH provider. It is NOT a new issue SSOT.

## Three views and fourth owner-review ordering

1. Golden thread = oldest created issue first. Oldest does not mean executable.
2. Mycelium = newest created issue first. This is an issue intake view, not the CODEX workflow run historian.
3. Graph = most dependent candidate issues, then undirected textual association degree. Text mentions are NONCAUSAL.
4. Owner-review = labelled P0..P4 first, then candidate dependents, linked open PRs, checkbox-only near-finished signal and age. Unknown priority sorts last. Never confuse this advisory ordering with PCA or Bradley-Terry inference.

DoD and DoV are separated by explicit source headings. Checked counts are SELF-REPORTED and not accepted. An absent checklist is null, not 0/0 and not 0%. Each record includes complete steps, source body digest, per-repo/global ordering, open PR overlap and out-of-scope references. Formal engineering, merge and owner acceptance stay UNKNOWN/HOLD.

## Replay/validation

Run from root with:

    python -m unittest discover -s mission-control/qps-triage-ultra/issue-expedition -p test_triway_burndown.py -v

    python mission-control/qps-triage-ultra/issue-expedition/triway_burndown.py --github --out triway-private.json --csv triway-private.csv

Requires GitHub token for private repos. Alternative: --input census-private.json. Add --previous matched-prior-projection.json for noncausal issue identity deltas. Never commit raw full bodies: private owner material may be present. GitHub REST defaults to GET only; API calls are bounded to 20 pages each; missing timestamps, SHA and denominators fail closed.

## Next pulses

N+1: native source-head tests, concurrency/auth 403/429, pagination boundary, review and exact-head CI.
N+2: source-bound explicit blocker/supersession edges, cycle handling, PR review/run evidence and immutable progress receipts.
N+3: integrate registered JADE Top21 and global USER cohorts rather than claiming five repos represent the full estate; gg_MATH PCA/BT must remain withheld until comparable measured features/pairs and identifiable fits exist.
N+4: independent owner DoD/DoV sign-off, semantic root deduplication, and matched same-population time-series burndown.

Governance invariant: MERGE_ADMISSION=HOLD; authority_transfer=false; formal_credit_delta=0. No ruleset/issue mutation, owner acceptance or Pages publication authorized here.
