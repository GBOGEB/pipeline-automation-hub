# Unified TOP7 / TOP14 / TOP21 evidence, taxonomy and measurement contract

**Authority:** Mission Control cohort definitions in `GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json`. QPS owns engineering acceptance; CODEX owns provenance/semantic admission; ABACUS owns analytical code and security evidence. This document is an interoperable *read-only measurement contract*, not a new authority source.

## Single measurement and treatment system

| Field / term | Definition | Units and denominator | Missing / treatment |
|---|---|---|---|
| `source_sha` | Exact commit whose changed code was instrumented | 40-char immutable git SHA | Missing = REJECT |
| `base_sha` | Git merge-base against the named comparison branch | 40-char git SHA | Missing = REJECT |
| `eligible_lines` | Unique changed executable line numbers represented in coverage XML | Count of distinct (repository-relative path, line) tuples | Unmatched file => INCOMPLETE, not zero |
| `covered_lines` | Eligible tuples with at least one coverage hit | Count, <= eligible | Never infer from test count |
| `percent` | 100 x covered / eligible, rounded to 2 decimals | %, source-bound diff only | Null for unknown/incomplete; zero only if measured 0/positive denominator |
| `missing_source_files` | Changed Python paths absent from instrumented XML | Unique sorted file list | Any entry => percent null and HOLD |
| `artifact_sha256` | SHA256 of native CI artifact ZIP | 64 hex chars | Missing => no receipt credit |
| `security_clearance` | Independent full-scope security acceptance | true, false or null | Null = UNKNOWN, not FAIL or PASS |
| `effective_main_protection` | Server-side effective protection on default branch | true or false/null | false/null => merge HOLD |
| `quality_run` | Terminal checks on source SHA | State + run/job IDs | PENDING/QUEUED/IN_PROGRESS never PASS |
| `evidence_class` | Evidence basis | OBSERVED_NATIVE, DERIVED_VERIFIED, DECLARED, UNKNOWN | No promotion from DECLARED alone |
| `cohort` | Membership from the global cohort SSOT | TOP7 / TOP14 extension / TOP21 extension | Membership is not promotion |
| `first_red` | Earliest genuine failing required gate | Root+same-head check receipt | No synthetic red |
| `proof_debt` | Missing required acceptance predicates | Count by rule ID, not issue count | No conversion of null to zero |
| `BD_queue` | Deduplicated technical debt backlog | Count of unique findings keyed by fingerprints | Do not add scanner categories with different denominators |
| `MIP` | Iterative improvement pulse | DEFINE->MEASURE->ANALYZE->IMPROVE->CONTROL->RECENSUS | CONTROL needs terminal evidence |
| `DOV` | Definition of verification | Exact head, full checks, hashes, independently corroborated scope | Unverified = HOLD |
| `DOD` | Definition of done | DOV plus required owner/security/engineering admissions | Cannot be inferred from green test suite |

## Global taxonomy

- **Scope**: `REPOSITORY_MAIN`, `RECOVERY_BRANCH`, `CHANGED_LINES`, `SELECTED_TESTS`, `FULL_REPOSITORY_SECURITY`, `COHORT`. Never mix denominators.
- **State**: `MEASURED`, `INCOMPLETE_INSTRUMENTATION`, `NO_ELIGIBLE_CHANGED_LINES`, `QUEUED`, `IN_PROGRESS`, `PASS`, `FAIL`, `UNKNOWN`, `HOLD`. Null observation is not numeric zero.
- **Security**: `BANDIT_TOUCHED`, `BANDIT_FULL`, `SEMGREP_FULL`, `SAFETY_FULL`, `DEPENDENCY_AUDIT`, `INDEPENDENT_REVIEW`, `BRANCH_PROTECTION`. Scans are independent; an advisory scanner passing does not prove clearance.
- **Debt treatment**: `NEW`, `EXISTING`, `RESOLVED`, `REOPENED`, `DUPLICATE`, `UNVERIFIED` with stable source/tool/rule/path/fingerprint keys.
- **Authority**: `PRODUCER`, `SEMANTIC_VALIDATOR`, `COHORT_CONTROLLER`, `ENGINEERING_OWNER`, `INDEPENDENT_REVIEWER`. A producer cannot self-admit to another authority.
- **Evidence disposition**: `ACCEPT`, `REJECT`, `DEFER` must be emitted only by the relevant authorized independent reviewer. Validation success is NOT acceptance.

## Rollout and roll-up

`QPS TRIAGE / ABACUS / CODEX / other cohort producers -> exact-SHA native receipts -> common validation -> Mission Control cohort ledger -> read-only REX / dashboard consumer -> independent admission or HOLD`.

Apply **the same schema, formula, file-path normalisation, unique-line counting, fail-closed missing-source check and evidence classes** to TOP7 first, then shadow-run on TOP14 and TOP21. The cohort SSOT remains unchanged; TOP14 remains shadow-measured and TOP21 held until global promotion rules pass. Do not write coverage evidence to a canonical QPS engineering SSOT or change rank decisions.

## Current dated observations

See `CROSS_REPO_COVERAGE_ROLLUP_20261013.json`; these are dated immutable *branch receipts*, not an always-current fleet state. QPS 169/176 = 96.02%, CODEX 165/174 = 94.83%, ABACUS 150/160 = 93.75% at the newer native exact-head receipt; its bounded Bandit ratchet still fails (B101=59 against a 46-finding allowance). Subsequent commits do not inherit earlier native green status.

**No main merges, ruleset overrides, scanner suppression or authority transfer.**
