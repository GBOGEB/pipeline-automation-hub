# Proposed draft PR — JADE_TEMPLE bootstrap (Mission Control authority)

> **Doc** JT-08 · **Status** HISTORICAL · **Release** UNNAMED (owner sets SemVer) · **Admission** `MERGE_ADMISSION=HOLD` · **Updated** 2026-10-31

**Repository:** `GBOGEB/pipeline-automation-hub`  
**Suggested base:** `master` (re-read head before branching)  
**Suggested branch:** `docs/jade-temple-top21-bootstrap-20261018`  
**Suggested draft title:** `docs(jade-temple): seed Top21 read-only readiness and recursive handover project`.

## Files / disjoint scope

New, additive `mission-control/jade_temple/` project docs, snapshot links, tests and standalone HTML projection. Keep existing `mission-control/federation-atlas/central/top21/` cohort roster and GitHub tree snapshots untouched. No rewrite of ABACUS N+2 viewer, CODEX consumer, QPS engineering SSOT, canonical CP handover schema or CI gates.

## Acceptance plan

1. Re-read current GitHub branch SHA and open PRs; check file path collisions.
2. Validate `data/TOP21_PORTFOLIO.json` 21 IDs and source N11 totals, provenance separation for 5-vs-21 nominations, exact heads (readback historical after write), unknown metrics and no authority escalation.
3. Run `python -m unittest discover -s tests -p 'test_jade_contract.py' -v` and deterministic site builder/hash verification twice.
4. Run Chromium responsive HTML QA at 1440x1000, 1280x800, 390x844 and controls; emit screenshots and local receipt.
5. On PR exact head, run native source tests and lint/CodeQL/security. Verify required approvals/protected branch and RED canary as independent gates.
6. Reviewer and owner decide the soft landing/manifest policy before any mandatory rule or migration. Release remains HOLD.

## Out-of-scope

No repo root file relocation, branch ruleset edits, GitHub Pages deployment, actual next release, worker dispatch, security waiver or owner transfer. This PR is a bootstrap presentation and planning surface only.

---

**Nav:** [← 07 Handover recursion](07_HANDOVER_RECURSION.md) · [Index](00_START_HERE.md) · [09 Project upload guide →](09_PROJECT_UPLOAD_GUIDE.md)
