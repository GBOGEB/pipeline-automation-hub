# ABACUS merge stall (Codex review allowance exhausted)

Incident `CP-2026-10-12-ABACUS-MERGE-STALL` · readback 2026-10-25T19:25:41+00:00 · owner GBOGEB

## Lift: NOT LIFTED

| ID | Criterion | Met | Evidence |
|---|---|---|---|
| L1 | Unblocker PR merged | yes | merged_at=2026-10-12T16:17:07Z |
| L2 | Gate restored (ruleset active, no bypass, expected rules present) | no | active, bypass=6, rules=5; missing: required_status_checks rule absent |
| L5 | Admission integrity (no merge since the unblocker without a green gate) | no | 97 merged; gate green on 1; 64 merged with red checks |
| L3 | Merge flow restored (at least 5 merges to the default branch since the unblocker) | yes | 97 merges since 2026-10-12T16:17:07Z |
| L4 | Open PR backlog at most a quarter of the baseline | no | 18 open (baseline 20) |

## Admission integrity

Since 2026-10-12T16:17:07Z: **97 merged**, gate `PR Feedback Gate` green on **1**, 64 merged with at least one red check. Gate states: failure 38, in_progress 38, none 20, success 1.

## Tracked PRs

| PR | Role | State | Inherited reds | Source-defect candidates |
|---|---|---|---|---|
| GBOGEB/ABACUS#1858 | unblocker | merged | — | — |
| GBOGEB/ABACUS#1859 | debt-ratchet | merged | — | — |
| GBOGEB/ABACUS#1857 | queued | merged | — | — |
| GBOGEB/ABACUS#1856 | queued | merged | — | — |
| GBOGEB/CODEX#984 | seed | merged | — | — |

## Default branches

| Repo | Head | Open PRs | Nightly reds (inherited set) | Ruleset |
|---|---|---|---|---|
| GBOGEB/ABACUS | `85157cf0` | 18 | Code Quality Checks, Full Red Proof Summary, Security Scanning | active, bypass 6 |
| GBOGEB/CODEX | `ae430f01` | 3 | — | none |

## Follow-ups

- GBOGEB/ABACUS#1878 (closed): Gate: mark PR Feedback Gate pending on pull_request synchronize (A→B→A reuse) — check: A→B→A head move leaves the gate pending on main
- GBOGEB/ABACUS#1879 (closed): Gate: correlate Codex outage reply to a current-head @codex request — check: outage reply to an earlier-head request keeps the fallback closed on main

## Next actions

- Meet L2: Gate restored (ruleset active, no bypass, expected rules present) (active, bypass=6, rules=5; missing: required_status_checks rule absent)
- Meet L5: Admission integrity (no merge since the unblocker without a green gate) (97 merged; gate green on 1; 64 merged with red checks)
- Meet L4: Open PR backlog at most a quarter of the baseline (18 open (baseline 20))
- Turn every inherited red into a dated burn-down item; never repair it inside an unrelated PR
