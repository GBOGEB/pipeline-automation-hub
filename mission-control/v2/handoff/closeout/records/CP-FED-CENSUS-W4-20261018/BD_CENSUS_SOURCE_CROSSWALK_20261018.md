# W4 canonical BD / TODO source crosswalk — public-safe

**Authority:** [MissionControl CODE_PURPLE_BD_QUEUE_v1.json](https://github.com/GBOGEB/pipeline-automation-hub/blob/master/mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json), blob `426a8b6ed3630c874eca4c2c1daaea7d13f3492a`. **Read-only derived ledger, not a new BD root population.** Source was pinned to `master` SHA `91ea7f23edc9cd7ab984b8a2730650609eddb55c` during publication. Recensus on resume.

## Exact canonical CPQ object population

| CPQ source-object state | Count | Engineering-root closure credit |
| --- | ---: | --- |
| `DONE` | **10** | **Not inferred**; may be canonical object disposition only |
| `ACTIVE` | **5** | None automatically |
| `TODO` | **2** | None automatically |
| `UNKNOWN_NEEDS_READER` | **2** | UNKNOWN; never zero |
| **Total distinct CPQ queue IDs** | **19** | **Engineering causal roots OPEN/CLOSED: UNKNOWN** |

| CPQ ID | Canonical title | Last source state | Flow |
| --- | --- | --- | --- |
| CPQ-001 | Cohort promotion gate CI was green while executing zero tests | DONE | NONE |
| CPQ-002 | Flake8 propagation cohort test was not run by any workflow | DONE | NONE |
| CPQ-003 | v0.1 atlas QA claims had no SHA, run or receipt | ACTIVE | LINKED |
| CPQ-004 | Cohort modes shown as labels; promotion predicates not evaluated | DONE | NONE |
| CPQ-005 | No as-of date or evidence age on the atlas | ACTIVE | IN_PR |
| CPQ-006 | Parallel TypeScript contracts and a duplicate dashboard | DONE | NONE |
| CPQ-007 | Federation graph draws declared dispatch edges like receipt-bound edges | DONE | NONE |
| CPQ-008 | Vocabulary drift: MCP vs TCP, health enum | DONE | NONE |
| CPQ-009 | Kubernetes and TCP telemetry have no data source | TODO | HOLD |
| CPQ-010 | ABACUS-I2 recorded as PENDING although its exact-head proof and G75 recurrence exist | ACTIVE | IN_PR |
| CPQ-011 | Second fresh Top7 recensus pulse is not recorded | ACTIVE | BLOCKED |
| CPQ-012 | document-organization-system has no exact-head proof on its current head | DONE | NONE |
| CPQ-013 | max_unchanged_root_auto_repeat_after_control is null, which blocks both promotion gates | ACTIVE | IN_PR |
| CPQ-014 | QPS federation edge (hub -> cryoplant-project) is declared with no receipt | DONE | NONE |
| CPQ-015 | No cross-repo dispatch and return path exists; 'dispatch' edges are declarations | TODO | RETURN_OWNER |
| CPQ-016 | PRs merged while First-Pass Closure was red or still running (REX-CM-005 recurrence) | UNKNOWN_NEEDS_READER | RETURN_OWNER |
| CPQ-017 | Metrics and BD states must advance with each iteration, keyed by ordinal | DONE | NONE |
| CPQ-018 | LM-10 MIP roundtrip gg_MATH -> Mission Control -> ABACUS/QPS has no state newer than 2026-09-21 | UNKNOWN_NEEDS_READER | LINKED |
| CPQ-019 | ABACUS DMAIC CI red: Unit Tests (3.10) cannot install matplotlib>=3.11.2 | DONE | NONE |

Focus IDs selected in the generated existing-method `CP.CLOSE` packet: `CPQ-010`, `CPQ-011`, `CPQ-013`, `CPQ-015`, `CPQ-016`, `CPQ-018`; their names, `done_when` and `control_when` are taken unchanged from the canonical source. No new CPQ IDs, no reset, no engineered closeout is written.

## External issue/PR lifecycle and TODO ≠ BD roots

| Owner control | Live status at 18 Oct snapshot | Acceptance still due |
| --- | --- | --- |
| [ABACUS #1860](https://github.com/GBOGEB/ABACUS/issues/1860) | 1 checked / 11 unchecked | Effective branch rules, independent current-head approval, terminal required CI and negative RED merge canary |
| [ABACUS #1929](https://github.com/GBOGEB/ABACUS/issues/1929) | OPEN | Deduplicated root fingerprint and comparable source/config/CI before-after and authorized closure |
| [CODEX #977](https://github.com/GBOGEB/CODEX/issues/977) | 0 checked / 7 unchecked | Authenticated ABACUS-local disjoint executor, stage/approve/REX return |
| [Hub #604](https://github.com/GBOGEB/pipeline-automation-hub/issues/604) | 0 checked / 12 unchecked | Native MissionControl graph/browser and admission evidence; no second graph authority |
| [Hub #85](https://github.com/GBOGEB/pipeline-automation-hub/issues/85) | OPEN parent | Root-linked CONTROL and REX with independent evidence |
| [Hub #336](https://github.com/GBOGEB/pipeline-automation-hub/issues/336) | OPEN owner/admin | Effective master required-status barrier and RED canary |
| Restricted engineering child | Owner-local / restricted | No private counts, SHA, title, source bytes or accepted QPS engineering obligation disclosed here |

## GitHub object CENSUS, non-atomic and explicitly scoped

- Frozen initial four-public-repo snapshot: 82 ordinary open issues / 23 open PRs; see `CENSUS_PUBLIC_20261018.json`.
- Newer native GET-only [run 39139236501](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/39139236501) at 2026-10-18T15:10:42.787707Z: **83 ordinary open issues, 25 open PRs**; see immutable `CENSUS_PULL_NATIVE_20261018.json` (`SHA-256 78e54ba29f51ce9d34157b8c502e043fc1f95fbf41ac9e10b0f7b9364719592e`). +1 issue and +2 PR are *lifecycle counts*, not new causal roots, reopened engineering failures, or authentic worker capacity.
- Four public source heads are in the native snapshot; QPS private source stays with its domain authority. Counts remain historical the moment the next GitHub event arrives.

## Reverse-pressure, DAG atoms and admissible transitions

`[GitHub issue/PR open/closed atom] -> [root fingerprint if independently joined] -> [source-owned first-red receipt] -> [matched denominator + native return] -> [authorized independent disposition] -> [CPQ event] -> [MissionControl read-only projection]`. Never infer a missing edge from a title, issue close, PR merge, green unit test, or G3P pulse number.

**Next owner gate:** hub administrator (#336) and ABACUS administrator (#1860/#1278) repair effective independent checks and demonstrate RED blocked. CODEX #977 remains stage-only. MissionControl CP.CLOSE packet and QPS engineering child acceptance are disjoint. `MERGE_ADMISSION=HOLD`, no waiver and no authority transfer.
