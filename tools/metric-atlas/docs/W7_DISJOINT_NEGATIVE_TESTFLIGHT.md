# CODE PURPLE CBD W7 — disjoint dispatch/receiver TestFlight

Date: 2026-10-21. Source owner: GBOGEB/pipeline-automation-hub.
Parent: #604. Basis: merged W5 #758 and W6-A/B #767/#769.
Source modules modified: dispatch.py and receiver.py only. This is not a new scheduler, dispatcher, publisher, QPS SSOT or authorised source mutation.
Privileged cross-repo dispatch remains guarded; W7 tests use mocks and do not execute remote events.

## Confirmed faults
1. Original dispatch.plan accepted a forged request_id in a superficially valid manifest. The patch reuses W6 disjoint_scale._check_manifest to reconstruct the exact three-lane census and rejects noncanonical metadata **before even planning**.
2. Original receiver.platform_job searched only the first 100 latest-run jobs, falsely reporting absence of a job on a later page. The patch bounds jobs and check-run reads to four 100-row pages, preserves exact returned totals, rejects missing/drifting/duplicate pages, and holds on 401+ entries.
The local A -> B -> A reverse test reproduces original failure, candidate repair, original failure with no network calls.

## Native CI fanout and resource controls
The existing qps-metric-census-federation.yml (single canonical workflow) retains its original full regression gate. One additive W7 matrix job is gated by verify-census-contract, limited to two concurrent slots, and runs source-disjoint dispatch/receiver tests on Python 3.11 and 3.12 (2x2=4 cells). Each exact PR-head job emits local-source scope coverage JSON and source blob hash. No new workflow or required-check identity.
Do not interpret a matrix job SUCCESS as independent security review or an authenticated dispatched worker.

## Measurement and interpretation
Local fixed candidate-source family: dispatch 64/64 statements and 24/24 branches; receiver 123/123 statements and 50/50 branches; 0 exclusions, as measured in the separate expanded offline suite shipped with W7 QA bundle. Native matrix tests are a **different test cohort**: measure each cell independently, never copy the local percentages to native. Local provisional test source uses a partial validation shim for W6; native runner uses the full upstream W6 module.
Missing worker-hours, main policy protections, first-red causal closures, and global zero-test inventory remain UNKNOWN.
W191 MASTER INPUT real Windows/OneDrive return and A10 confidentiality remain noncompensating owner obligations.

## Admission checklist
- [x] Source-first A/B/A reproducer, two disjoint modules, bounds 0..400, adversarial/reverse regressions (LOCAL)
- [x] Syntax/unit/coverage checked with source hash and unchanged matched candidate population (LOCAL)
- [ ] Native PR-head full suite; 4 matrix cells; native exact-byte artifact verification
- [ ] Independent review, effective required-check and RED-canary proof
- [ ] Source owner disposition and serial main merge; fresh-main readback; temporal recurrence
- [ ] QPS private Windows source return (separate owner gate)
MERGE_ADMISSION=HOLD. Engineering credit=0. Dispatch workers launched by this PR=0.
