# N+2 / N+3 — CREW SIPOC pulse scaling matrix (advisory)

**Owner:** MissionControl GoGREEN, extending `sipoc_instances.py` and `actions_metrics.py` (canonical queue metrics). **No new scheduler or KPI ledger.**  
**Wave identity:** source SHA + pulse ID + run/attempt/job + receipt hash; `N-1 -> N -> N+1` lineage is append-only and consumer-specific.

## Layered execution architecture

- **Execution DAG:** S -> I -> P(fan-out) -> O(fan-in) -> C. Same-pulse cycles are forbidden. Branch isolation, root ownership and path leases decide whether mutations may share a wave.
- **SIPOC ports:** suppliers and exact input, versioned process, produced artifacts + receipts, independent downstream admission. `CONTINUE_NEXT` is intra-pulse; `SELF_REENTRY` enters only a later pulse; `PAY_IT_FORWARD` is a candidate for another process, never automatic dispatch.
- **MYCELIUM / Golden Thread:** graph navigation, reverse pressure, consumer relationships, persistent source/receipt identity and re-entry history. They are not new execution authority.
- **Quality sidecar:** artifact QA, process QA and statistical QA are separate. `gg_MATH` remains provider of advanced statistical diagnosis; do not call PCA/BT on incomparable or insufficient cohorts.

## Stage x lane x CREW matrix

| Stage | SIPOC | Writer/worker lanes (disjoint) | Independent verifier/CREW lane | Deliverable / gate |
|---|---|---|---|---|
| P0 Source freeze | S | SCOUT-A GitHub sources; SCOUT-B QPS native source family (read-only) | Sentinel/Doctor verifies source SHA and provenance class | Source census, exact-head identities |
| P1 Admit | I | Planner binds parent pulses; consumer declares admissible inputs | Auditor validates source/consumer rights, authority = false | ACCEPT / DEFER / REJECT with evidence |
| P2 Fan-out | P | W-A Hub scale controller; W-B QPS comment adapters; W-C CODEX PAY_IT_FORWARD observer; W-D ABACUS TestPilot | Independent paired validators A'–D'; read-only scouts may outnumber mutators | Path/root leases, group safety, bounded 2 initially |
| P3 Testflight | P | Runner executes isolated native tests, fixtures, fails early on first material red | Doctor runs adversarial/negative contract checks, exact-head comparison | Native run+attempt+job receipts; no synthetic -> native substitution |
| P4 Fan-in | O | Composer links SHA-bound outputs; no shared in-wave mutation | Reconciler validates DAG and receipt chain, renders matrix, checks QPS ENG HOLD | Source-bound QA evidence, unresolved findings |
| P5 Consumer / REX | C | Owner proposes admission, PAY_IT_FORWARD or SELF_REENTRY into N+1 | Independent eligible reviewer, security and domain owners retain veto | PR Draft/Review/HOLD; unchanged source history |

All role names are **logical CREW assignments**. A name on the matrix is not an authenticated dispatched agent. The existing canonical CREW registry determines actual eligible actors. Do not invent runner identities.

## Scale pulses and deliberately noncompensating stop rules

| Gate | Mutating concurrency | Prerequisite to advance | Next legal action |
|---|---:|---|---|
| N+2 W0 | 2 | Source census; no path collision; native CI diagnostic | Local repair first material red; disjoint read-only scouts continue |
| N+2 W1 | 2 | Two worker/verifier pairs, native distinct run IDs, exact-head tests and independent review | Mark proposed two-pair cohort; no actual auto-dispatch |
| N+2 W2 | 2 | Two **consecutive** qualified comparable pulses, no root recurrence or security hold, canonical queue p95 nonregression | Proposal for 4, separately authorized |
| N+3 W3 | max 4 **after approval** | Real runner capacity, source and lease refresh, changed-head requalification | Additional disjoint lane flight with new first-red / queue receipts |
| N+j CONTROL | conditional | Accepted causal-root closure and nonrecurrence; measured consumer adoption | Stop at bounded DoV or materially changed evidence; do not spin |

Do not recurse on unchanged inputs, presumed approval, skipped/neutral CI, or stale GREEN. A return pulse must identify the changed source or new evidence.

## Evidence requirements for `sipoc_scale_gate.py`

Input schema `missioncontrol.sipoc-scale-observation.v1`: explicit source heads, two ordered pulses, exactly two disjoint worker+verifier pairs per pulse, distinct actor and native run/job/attempt receipt identities (each `(run_id, attempt, job_id)` and each `receipt_sha256` used by at most one worker or verifier record across all assessed pulses), per-pulse completed review, no first red/security recurrence, and **external** comparable `queue_p95_seconds` from the existing Actions metric owner. Each metric window names its `pulse_id` and that pulse's exact `source_heads` (a pulse's own census, else the top-level heads); `after` is the latest pulse and `before` an earlier listed pulse. The projector validates input *claims*, **not** their truth against live GitHub. Its positive return is `SCALE_CANDIDATE_EXTERNAL_GATE`, never `SCALE_APPROVED`.

Actual values are **WITHHELD** until a complete comparable metric cohort and real exact-head run/job readback are available. An empty status list is not CI pass. Green test labels are not independently accepted causal-root closure.

## N+2 observation / first-red snapshot (2026-10-28)

- Hub #991 `2decbc3af1`: native `CBD Subtype Worker Orchestrator` run **40709718986** passed its SIPOC instance regression step, then failed in live BD census with HTTP 404 reading `/repos/{repo}/pulls`. Repair the access/target root, not the preceding SIPOC test. Do not downgrade the gate.
- QPS #2167 `150f1bffc6`: targeted PPTX integrity run **40709730794** failed with no reported executed steps, as did three W69 OS probe families. Classify cause as runner-infrastructure-suspected pending native diagnosis. No parser PASS, native Office proof or engineering approval.
- QPS #2164 remains owner of 37 comment entries / 18 threads; N+2 legacy singleton adapter **cannot** establish this real source population. Modern reply semantic acceptance is a separate controlled stage.

## DoD / DoV

- [x] Implement first read-only 2-to-4 governor on a disjoint branch and draft PR.
- [x] Add synthetic positive/negative fixtures for invalid source, lease, reviewer, native receipt and metrics.
- [ ] Current exact-head native GitHub CI of the governor on the **latest** PR head; no red or skipped required check.
- [ ] Independently fetch and verify two real pulse cohorts with actual job/run IDs, exact source SHA, receipt bytes and comparable canonical metrics.
- [ ] Confirm CODEX/QPS consumer acceptance on their own heads. No transferred engineering authority.
- [ ] Independent eligible review and branch protection verification before promotion. `merge_admission=HOLD` until then.
- [ ] After next pulse, compare p50/p95 and accepted causal-root outcomes to preregistered targets, preserving unknowns.

**Success is measured accepted nonrecurring causal-root closure / qualified consumer adoption, not runner count or PR count.**