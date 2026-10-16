# Native ABACUS to Mission Control bridge — read-only first actual pulse

The ABACUS #2033 telemetry schema and producer source remain canonical in
`GBOGEB/ABACUS/tools/mip_ci_wave_telemetry.py`. The Mission Control
`mip_native_bridge.py` pins a full ABACUS Git commit and gathers **explicit**
run/attempt and page-complete job records from GitHub's fixed HTTPS Actions
REST API. It delegates the numeric producer execution to that exact ABACUS
source and passes its disposable v2 projection to the already-tested
`mip_source_consumer.consume`.

CI now includes a **complete PR-event exact-head cohort manifest** for source
`22c90e0412d0ecc8384917df5e7e19a3195ce86b`. The manifest lists 30
unique native run/attempt IDs. At execution time, the collector re-queries
the pinned GitHub Actions listing with `event=pull_request`, compares the
authoritative `total_count` and complete set of exact run attempts, then
collects every selected job page; any drift fails closed. This proves only
the full thirty-workflow pull-request event population at that exact head,
not all possible GitHub events, subprocesses or independent experimental units.
An observation of 27/30 successful workflows is a descriptive status for
that event cohort, never an IID binomial sample or causal process change.

The observation has a native HTTP run/job identity and selected code SHA, but
no original artifact ZIP byte authentication, no independent process samples,
no root closure and no four-hop chain. Neither a green output nor a root
signature proves an accepted engineering fix. All numerical inference
(Wilson confidence levels, PCA, BT, ANOVA and MANOVA) remains withheld on
this correlated, selected workflow population.

For different heads or selections, create a new version-bound input rather
than relabel an old observation. Do not rewrite historical source hashes,
rerun completed workflows solely to improve the display, change security
protection, approve, merge or publish QPS acceptance on the basis of this
projection.

**DoV:** independent source-owner review of run/job source custody, matched
cohort expansion and accepted root disposition. `MERGE_ADMISSION=HOLD`,
`QPS=DEFER`, `authority_transfer=false`.
