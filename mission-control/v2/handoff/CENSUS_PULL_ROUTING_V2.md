# CP.CLOSE / CENSUS_PULL — GitHub-first federation routing extension

**Type:** source-owner routing procedure, not a new SSOT, worker dispatcher, BD register, method registry, or executable ChatGPT moniker. Extend existing [CP.CLOSE](../closeout/README.md), [CP.HANDOFF/CP.RESUME](../CP_HANDOFF_RESUME_V1.json) and [G3P operator](../../G3P_EXECUTION_OPERATOR.md).

## Routing precedence

| Data atom | AUTHORITATIVE write owner | Allowed read-only federation consumer | Return/closure requirement |
| --- | --- | --- | --- |
| GitHub source SHA, native CI run/job/attempt | GitHub itself / repository source branch | CENSUS_PULL, CP.CLOSE, Mycelium | Exact source head; terminal native + artifact bytes |
| ABACUS DOW first-red, coverage, BD/LDAB root | ABACUS source owner / issue #1929 | MissionControl and CODEX read-only | Comparable eligible denominator; independent disposition |
| CODEX glossary, Mycelium semantic graph | CODEX owner glossary/API | MissionControl/QPS/ABACUS | Typed source/edge/producer receipt and separate auth |
| Fleet BD/REX root lifecycle | MissionControl existing CODE_PURPLE_BD_QUEUE_v1.json | CP.CLOSE subset and child owner | Owner-approved root closure; never derived from issue closed |
| QPS private RTM/controls/commercial data | cryoplant-project private engineering SSOT | Authorized QPS reader only | No private bytes copied to public handover; public pointer only |
| Required status and independent review | GitHub repository admin/reviewers | CP.CLOSE reports HOLD/observed state | Effective REST rules + negative RED canary + approved current head |

## CENSUS_PULL transport classes

- `PUBLIC_SAFE`: GET-only public core repos, ordinary issue counts excluding PRs, open PR counts, head SHAs, dated non-atomic observation. It may be committed to this public repository.
- `RESTRICTED_OWNER_RETURN`: private repo is read in an authorized scope; no private SHA, ticket title, sensitive payload or workload summary is committed to a public surface. Owner reports only an approved public receipt pointer or UNKNOWN.
- `HISTORICAL_FROZEN`: prior SHA/runs remain evidence about that revision; no promotion to current-head evidence.
- `SOURCE_BOUND_NATIVE`: run id, attempt, job+step identity, exact head, test denominators, real JUnit/JSON/ZIP digests, receipt source. GitHub artifact metadata alone is not accepted engineering closure.

## Controlled pull/push lifecycle

`PULL → IDENTIFY(typed atoms and source SHA) → NORMALIZE(public-safe) → RECONCILE(CPQ/issue/PR/root non-equivalence) → CP.CLOSE -> NATIVE_QA -> DRAFT_PR -> INDEPENDENT_REVIEW -> EXACT_MASTER_READBACK -> CP.RESUME`.

Every published count must name repo set, branch, issue-vs-PR filter, timestamp precision and complete returned population. `null` is UNKNOWN. A non-atomic comparison is INELIGIBLE if source/config/instrumentor/eligible population differ. No GH issue auto-closure or branch protection mutation in this method.

## Operator commands

```bash
python mission-control/v2/handoff/closeout/public_census_pull.py --out /tmp/public-census.json
python -m unittest mission-control/v2/handoff/closeout/test_public_census_pull.py
python mission-control/v2/handoff/closeout/cp_close.py --intake mission-control/v2/handoff/closeout/intakes/CP-FED-CENSUS-W4-20261018.json --bd mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json --out /tmp/cp-fed
python mission-control/v2/handoff/closeout/cp_close.py --intake mission-control/v2/handoff/closeout/intakes/CP-FED-CENSUS-W4-20261018.json --bd mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json --out /tmp/cp-fed --check
```

**DoV:** native run against exact PR SHA generates canonical nine-artifact packet with manifest; deterministic replay matches; CENSUS excludes private payloads and keeps issue/PR/root counts distinct; P0 policy and actual worker dispatch unchanged. A PR source commit and passing unit tests do not grant main admission.

## W5 measurable handover and graph projection (read-only extension)

The source-owned [W5 operational handover](w5/README.md) adds measurement to the existing CP.CLOSE W4 continuation, without creating a second CPQ/BD register, MYCELIUM authority, MASTER_DAGS registry or Crew dispatcher.

The W5 output includes a fully scoped four-public-repository GitHub CENSUS, the 90 exact-source-head workflow run denominator (35 success, 4 fail, 4 skipped, 47 nonterminal at its frozen dated observation), a 25-node/33-edge typed dependency and reference graph, a five-stage SIPOC, canonical CPQ 19-item lifecycle projection, first-red run/job/step bindings, N-1/N job-queue conservation, and a CP.RESUME drop-in. Its 12 native static assertions, three-Python read-only testflight and canonical W4 CP.CLOSE byte-parity gate are defined by `.github/workflows/w5-handover-telemetry-qa.yml`.

**New invariant:** no naked UNKNOWN in a control metric. A missing coverage, root, dispatch or reviewer value must include an owner, target evidence population, retrieval predicate, next observation and NULL numerical value. A pending native workflow must expose its exact SHA/run/attempt and terminal versus censored denominator. If upstream evidence is not retrieved, report `NOT_MEASURED` and why, never report fabricated zero.

Private cryoplant-project source and ticket contents stay behind `RESTRICTED_OWNER_RETURN`. This public handover excludes the private SHA/counts by construction. Approved owner returns are the only authorized cross-boundary evidence.

The graph's four topological layers express diagnostic prerequisites, not actual scheduled workers. The next G3P pulse must refresh GitHub sources and recompute all metrics rather than promote dated projections as live acceptance. No evidence observation can bypass repository-owner rules, independent reviewer, full native main DoV or authenticated ABACUS-local dispatch.
