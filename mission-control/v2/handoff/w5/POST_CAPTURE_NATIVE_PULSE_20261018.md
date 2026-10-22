## W5 post-capture N→N+1 — *different source-head populations*

W5 baseline source SHA **97a8b13faff577272a90edaf0dd4593035e10605** reached terminal native [B0 39142444027](https://github.com/GBOGEB/ABACUS/actions/runs/39142444027) **13/13 jobs success** (4,168 PASS, 2 SKIP, 3 warnings) and [matrix 39142443923](https://github.com/GBOGEB/ABACUS/actions/runs/39142443923) **7 SUCCESS + 1 SKIPPED jobs**. From actual B0 report-only artifact 12142426649, the exact native **coverage-dab.json** records **7,765/22,188 statements = 35.00%**, **1,651/5,444 branches = 30.33%**, combined 34.08%, 374 excluded lines and test-function dynamic contexts. This is measured native source data, not a stale screen or synthetic KPI.

**New source SHA 1122dca15557e4d2b0ec16300fcbf409db678e86** has a separately paginated **165-workflow** census: 105 success / 8 failed / 44 cancelled / 6 queued / 2 pending (157/165 terminal, **95.15%**; cancelled is NOT PASS). Current [B0 39143732112](https://github.com/GBOGEB/ABACUS/actions/runs/39143732112) **FAIL** with 11 green and 2 red jobs. Current [matrix 39143732055](https://github.com/GBOGEB/ABACUS/actions/runs/39143732055) **FAIL** with 2 green / 5 red / 1 skipped jobs.

Common native **first-red** in four canonical B0/Python jobs: **ModuleNotFoundError: No module named 'test_g3cs_assurance_matrix'** while collecting **tests/test_g3cs_source_mutations.py**, owner source [ABACUS #2234](https://github.com/GBOGEB/ABACUS/pull/2234). Downstream report-only/proof jobs also fail. One candidate shared root can manifest in many jobs; do not count job failures as separate causal roots. The older 35.00%/30.33% metrics are **NOT** latest-main coverage after the new SHA: current-main coverage remains null because native collection failed.

### Source lineage / graph extension

~~~mermaid
flowchart LR
 A[ABACUS old main 97a8…] --> B0[Native B0 13/13 PASS]
 B0 --> COV[35.00% statements / 30.33% branches]
 A -. newer Git revision, not comparable .-> B[ABACUS new main 1122…]
 B --> ROOT[G3CS test-module import missing]
 ROOT --> B0RED[Current-main B0 red]
 ROOT --> MATRIXRED[Current-main Python matrix red]
 B0RED --> OWNER[ABACUS source-owner repair / exact SHA retest]
 MATRIXRED --> OWNER
 OWNER -. not accepted until reviewed .-> GOV[Admission HOLD]
~~~

**Required follow-up:** repair collection in its disjoint ABACUS source owner, retain fail-closed test count, rerun B0 and matrix at the same *fresh* main SHA, and independently disposition the root. Code failure cannot be papered over by a PR merge, previous green run, inflated coverage or an unapproved reviewer. Continue with W5 source snapshot/graph plus this additive pulse; do not rewrite W4 or earlier W5 capture.

**Security waiver=false, authority transfer=false, merger admission=HOLD.**
