# GoGREEN TOP21 — merged success and inherited red outcome census

**Status:** read-only evidence consumer, not an independent root/merge authority. Canonical TOP21 roster remains \`mission-control/grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json\` (source Git blob \`0e42dd49eacc46a57fde432ad8d93ea17de4b4f9\`). The three source-pinned 17 October snapshots capture the **latest two merged PRs selected from the 30 most recently updated closed PRs per repository**. This is a bounded sample, **not every historical merged PR**. One repository has only one selected PR. No claim is made about empty populations outside the selected sample.

## Measured fixed-snapshot scope

- **21/21 repositories** represented; **41 merged PRs**, **509 native check-run IDs**, **33 failed-check manifestations**. All numbers are for the bounded recorded sample, not all repos' lifetime histories.
- Historical findings include *premerge* and *postmerge* check completions. The merge-chronology comparison uses native \`completed_at\` relative to the PR's \`merged_at\`; check creation after merging cannot retroactively be considered a premerge required gate.
- **6** selected PRs have checks failing before merge, **9** have checks failing after merge (two PRs occur in both populations). 23 of 41 have positive **observed** check surfaces; five PRs have missing/inaccessible/nonpositive check evidence. Nothing here proves all effective required checks/review/security were satisfied.
- The full raw check-run evidence is retained in \`snapshots/top7_20261017.json\`, \`top14_extension_20261017.json\`, \`top21_extension_20261017.json\`. Each native check entry preserves exact ID/name/status/conclusion/started/completed UTC/details URL. Check population completeness is explicit.
- The historical profile PR #1 source head was re-read and corrected after a fail-closed native SHA validation; **five PRs have zero native check runs**, including that PR. These are **UNKNOWN**, never green. GitHub commit status contexts and effective required-check policies were not part of this bounded scan.

## Dual output and owner lanes

**GoGREEN:** maintain successful capabilities and source-pinned test/check facts as positive evidence. \`OBSERVED_GREEN_AT_MERGE\` is bounded: observed check runs were successful/skipped/neutral, not verified independent approval. \`OBSERVED_GREEN_LAST_KNOWN\` means some checks completed only after merging. Neither means formally admitted engineering or federation release.

**CODE PURPLE/EVERRED:** emit a separate deduplicated \`event_key=(repository,PR,source HEAD,check-run ID)\` per failure, including check name, job/run link and pre-/postmerge timing. Preserve all 33 manifestations. Grouping check names is **symptom** association, not causal root closure. Do not create 33 issues or waive anything automatically. The existing Mission Control BD/REX registers own disposition and deduplication of causal roots.

Examples with inspected first-red evidence:
- ABACUS #2129 \`policy-and-inventory\`: stale \`docs/ci/WORKFLOW_RATIONALIZATION.md\` and unclassified workflows; graph-contract also fails on 3.11 and 3.12.
- CODEX #1066 \`semantic-validation\`: native W169 replay test \`_SentinelObject\` has no \`hexdigest\`; \`governance-gate\` flags missing PR-007 header and absent W003 follow-up.
- CoolProp #20 \`build\`: Docker pull denied (this alone is not a code defect); Telegraf #3 \`semantic/main\`: nonsemantic PR title.
These findings are source-specific, not asserted to explain other failures with the same workflow name.

## SIPOC / DAG

\`S:TOP21 repos, immutable PR HEADs + native GitHub checks → I:PR number, base, merge time, check run/attempt/job identity → P1:bounded read-only pagination and source validation → P2:pre/post merge chronology with explicit unknowns → P3:green, inherited red, unverified classification → O1:GoGREEN positive capability ledger; O2:CODE PURPLE/EVERRED failure handoff → C:independent source owners, governance, REX / admission HOLD\`.

Cycle (declared, not yet proven): source-owner repairs → separate exact-head positive/negative/fault-injection tests → new native checks → owner-approved disposition and recensus. The DAG never grants merge authority.

## Execution and scaling

Run the native pinned testflight via \`.github/workflows/gogreen-top21-merged-outcomes.yml\`. It checks native JS regression tests, then regenerates CSV/JSON/SIPOC and SHA256 manifest in the CI artifact. This qualifies the **transformer on these frozen receipts**, not current fleet health or a live cross-repo permission/dispatch test.

Scale with the supplied offline CLI/PowerShell bundle and a bounded read-only native collector: cohort 7 → 14 → 21; ≤2 merged PRs/repo initially; each complete paginated checks population has a source-run identity and a stop-on-partial flag; next increment increases depth only when verified denominator and permission coverage improve. The collector is authorized to **read**; remote mutation, issue creation, rerun, merge, release admission and security waiver remain disallowed.

## Metric definitions / due diligence

- \`observed_green_prs\` counts only qualifying **sampled** PRs. It is not a merged-repository coverage percentage or engineering acceptance rate.
- \`failed_check_observations\` counts check IDs, not independently verified roots, and not failed lines of code or coverage.
- \`first_red_verified_fraction\` is UNKNOWN until job logs have been read and linked to the exact same run/check. The reviewed examples above are supplemental evidence.
- \`coverage_statements\` and \`coverage_branches\` are **null** for this census; check-green is not code coverage. Future test/coverage growth must be measured per source blob and common eligible denominator.
- Continuous clocks: created/start/completed/merge. Pulse clock: N+i only after source-bound native terminal evidence. “N20” requires >=20 observations within one declared comparable population; 41 PRs across 21 repos do not qualify as a single independent N20 rate.
- Cross-repo comparisons must preserve TOP21 cohort, branch target, age and commit identity. Feature-branch merges must not count as mainline deliveries.

**Admission disposition:** \`HOLD\`. \`merge_authorized=false\`, \`root_closure_credit=0\`, \`authority_transfer=false\`.
