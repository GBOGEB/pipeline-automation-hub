# CODE PURPLE — canonical 19-item CPQ / BD ledger (read-only frozen projection)

**Authority**: `mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json`, source Git blob `426a8b6ed3630c874eca4c2c1daaea7d13f3492a` at hub master `2cc9b4d433c404b50d7afc661f863b96d42e97cc`. This table is a timestamped **projection only** and cannot update/close a CPQ root.

| ID | Priority | Last state | Flow | Declared dependencies | Canonical title |
|---|---|---|---|---|---|
| CPQ-001 | P1 | DONE | NONE | — | Cohort promotion gate CI was green while executing zero tests |
| CPQ-002 | P2 | DONE | NONE | — | Flake8 propagation cohort test was not run by any workflow |
| CPQ-003 | P1 | ACTIVE | LINKED | — | v0.1 atlas QA claims had no SHA, run or receipt |
| CPQ-004 | P1 | DONE | NONE | — | Cohort modes shown as labels; promotion predicates not evaluated |
| CPQ-005 | P2 | ACTIVE | IN_PR | — | No as-of date or evidence age on the atlas |
| CPQ-006 | P2 | DONE | NONE | — | Parallel TypeScript contracts and a duplicate dashboard |
| CPQ-007 | P2 | DONE | NONE | — | Federation graph draws declared dispatch edges like receipt-bound edges |
| CPQ-008 | P3 | DONE | NONE | — | Vocabulary drift: MCP vs TCP, health enum |
| CPQ-009 | P3 | TODO | HOLD | — | Kubernetes and TCP telemetry have no data source |
| CPQ-010 | P1 | ACTIVE | IN_PR | — | ABACUS-I2 recorded as PENDING although its exact-head proof and G75 recurrence exist |
| CPQ-011 | P1 | ACTIVE | BLOCKED | — | Second fresh Top7 recensus pulse is not recorded |
| CPQ-012 | P2 | DONE | NONE | — | document-organization-system has no exact-head proof on its current head |
| CPQ-013 | P1 | ACTIVE | IN_PR | CPQ-010 | max_unchanged_root_auto_repeat_after_control is null, which blocks both promotion gates |
| CPQ-014 | P2 | DONE | NONE | — | QPS federation edge (hub -> cryoplant-project) is declared with no receipt |
| CPQ-015 | P2 | TODO | RETURN_OWNER | — | No cross-repo dispatch and return path exists; 'dispatch' edges are declarations |
| CPQ-016 | P1 | UNKNOWN_NEEDS_READER | RETURN_OWNER | — | PRs merged while First-Pass Closure was red or still running (REX-CM-005 recurrence) |
| CPQ-017 | P2 | DONE | NONE | — | Metrics and BD states must advance with each iteration, keyed by ordinal |
| CPQ-018 | P3 | UNKNOWN_NEEDS_READER | LINKED | — | LM-10 MIP roundtrip gg_MATH -> Mission Control -> ABACUS/QPS has no state newer than 2026-09-21 |
| CPQ-019 | P1 | DONE | NONE | — | ABACUS DMAIC CI red: Unit Tests (3.10) cannot install matplotlib>=3.11.2 |
 
**Summary:** 19 atoms; 10 DONE, 5 ACTIVE, 2 TODO, 2 UNKNOWN_NEEDS_READER. **Non-DONE:** 9. No accepted causal-root closures are inferred; worker capacity and observed fleet breadth are distinct UNKNOWNs.

**P0 admission lanes:** ABACUS #1860, CODEX #977 / #1037, Mission Control #336. Read effective server-side rules and prove blocked RED canary plus eligible human review, even when GitHub reports merged=true.

**Engineering lanes:** CODEX postmerge OSV #1097 first-red 6 findings/4 packages; W10 #725 annotated-green severity/corpus; current ABACUS B0 and matched statement/branch/diff; source-owned gg_MATH/QPS receiver; QPS private owner return. All require native DoV and no security waiver.

**Declared graph dependency:** `CPQ-010 -> CPQ-013`; do not dispatch a child prior to independent source qualification. Other edges remain in the original JSON. Refresh canonical JSON before adding/removing TODOs.
