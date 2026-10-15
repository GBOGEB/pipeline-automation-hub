# W4 CODE PURPLE — Root-owned first-red repair and overlay retention

Date: 2026-10-15. Owner: MissionControl / [#153](https://github.com/GBOGEB/pipeline-automation-hub/issues/153). This is a **source repair candidate only**. No owner acceptance, merge waiver, new Pages publisher or QPS engineering acceptance.

## Distinct evidence roots

- **EVERRED-ATLAS-001**: PR #541 merged despite native Method Atlas RED. Runs [38739254875](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739254875) and [38739428503](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739428503): 87 executed, one failed; a whole-HTML string ban on `QPS P3` falsely matched the legitimate explanatory text `not an artificial QPS P3`. Repair restricts the assertion to the actual `<b>P3</b>` pulse row and verifies [0,1,2] exactly. Exit requires terminal exact-head+exact-main Atlas PASS and artifact checksum verification.
- **EVERRED-SESSION-002**: PR #540 Session Hook run [38739313365](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739313365) passed 19 tests but failed generated HTML title predicate. Generated heading is `CODE PURPLE — Recursive session intent ledger`; workflow previously asserted `Session intent`. Match exact known heading, preserve privacy/SHA/fail-closed requirements. Exit requires terminal native producer receipt, full append-only chain validation.
- **EVERRED-ATLAS-003**: A prior W3 branch preserved N+2 Pulse overlay, but the #541 merge carried an older Atlas workflow and navigation that omitted that stage. Restored one historical overlay step + one link. Exit requires `federation-latest.html` and JSON in same exact-head Atlas ZIP, plus no stale promotion.

## Noncompensating HOLDs

* The verified prior 42 Flight Deck tests and 99.63/98.31 focused coverage are **local** evidence, not native W3 admission.
* W1/W2 source and W3 earlier step are merged. This W4 source repair is staged in a **non-PR branch**, preserving GitHub Actions credits until an owner-authorized single testflight.
* MissionControl master still lacks effective branch protection. Existing operator Golden Thread `session_hook` uses only manually sanitized intent and cannot reconstruct raw ChatGPT metadata.
* Original G4 census: 6/42 status-observed, 36 unobserved; five comparable main anchors 2 matching/3 stale. UNKNOWN is not ZERO.
* QPS engineering decision = DEFER; source-to-consumer native chain = UNKNOWN.

## Next allowed transaction

Preflight current master SHA and branch ancestry -> inspect these disjoint diffs -> owner-authorized single draft PR -> verify 87+ original Atlas tests, 42+ Flight Deck tests, 19 Session Hook tests, generated receipt bytes and negative controls -> resolve eligible review/ruleset -> integrate -> exact-main recensus -> publish only through existing Pages provider -> verify hosted bytes. Any first-red stays attributed to its own producer/root.

`authority_transfer=false; security_waiver=false; merge_authorized=false; formal_credit_delta=0; engineering_credit_delta=0`
