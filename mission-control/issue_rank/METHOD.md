# Issue burndown ranking — method v2

`issue-rank-method/2.0`. Advisory only: no closure, merge or dispatch authority. A ticked box is
self-reported, not a verified DoD.

## 1. Questions the method answers

| Question | Output |
|---|---|
| What should be worked next, per repo, JADE, USER? | `views.action_queue`, `rollups.<scope>.action_queue`, `rank_repo` |
| What unblocks the most, and what is the bottleneck? | `score_parts.inherited`, `unblocks_now`, `pressure`, `chain`, `graph.critical_chain` |
| How far is each item from closed? | `progress` (`4/7 (DOD 2/3, DOV 1/2, STEPS 1/2) +3 untracked`), `golden_thread` (`5/9`, first break, next step), `chain.below` |
| What is nearly finished? | lanes `CLOSE_CANDIDATE`, `NEARLY_DONE`, `MERGE_READY`; `rollups.<scope>.nearly_finished` |
| Is the backlog burning down? | `rollups.<scope>.flow` (rates with intervals, Little's law, ETA or `NOT_CONVERGING`) |
| What moved since last pulse? | `delta.json` (new and rooted items, links, PR dependencies, ticks vs scope growth, thread moves) |
| How sure is the rank? | `rank_interval` (90%), `p_top`, `robust_top`, `method.monte_carlo.spearman_median` |

## 2. Data and identities

One pulse is one snapshot: each repository's default-branch head SHA is read once (AGENTS.md L6). The
snapshot holds:

- open issues and PRs;
- issues closed inside the window (`--window-days`, default 14);
- every referenced item, with its state resolved.

Edges carry a **binding**:

- `OBSERVED`: GitHub's own relations (`blockedBy`, `blocking`, `parent`, `subIssues`,
  `closedByPullRequestsReferences`), PR `closingIssuesReferences` and timeline cross-references.
- `DECLARED`: references parsed from issue or PR text by
  `issue-expedition/triway_burndown.references()`, the parser owner.

A blocker whose state is unknown counts as open (fail closed). A reference to nothing is dropped.

## 3. Item structure (DoD / DoV / steps)

`triway_burndown.checklist()` assigns each checkbox to DoD, DoV, STEPS or OTHER and records the basis
(explicit heading, calibrated synonym, inline label). Plain bullets and prose under those headings are
**declared but untracked**. When a body has no live checkbox, progress is `null`. It is never `0/0`
and never 0%.

## 4. Urgency (own)

For item *i*, the features in [0, 1] are:

| Feature | Value | When it is unobserved |
|---|---|---|
| priority | overlay > label/title: P0 1.0, P1 0.66, P2 0.33, P3 0.1; critical/urgent/blocker 0.66 | prior 0.33 (P2) |
| nearness | ticked / total; 1.0 when all ticked | scope mean |
| pr_ready | linked or own PR merged/green 1.0, red or pending 0.5, present without checks 0.25 | scope mean (no PR) |
| age | percentile of age | always observed |
| idle | percentile of days since the last update | always observed |

```
u_i = Σ_f w_f · x̃_if / Σ_f w_f        w = (0.35, 0.20, 0.15, 0.15, 0.15)
x̃_if = x_if if observed, else prior_f or mean_j(x_jf)
coverage_i = Σ_{f observed} w_f / Σ_f w_f
```

**Unknown is not zero.** v1 scored a missing checklist as nearness 0. That made 82% of issues look
"not started". Mean imputation removes the bias for the parts that are plausibly missing at random.

**Priority is the exception.** It is missing not at random: owners label the urgent few. The mean of
the known labels would promote every unlabelled item to near-P0, so priority takes a declared neutral
prior (P2), recorded in `method.priors`.

`imputed` lists the parts filled in, so a reader can discount a low-coverage rank. Parked intents
(`parked-intent` label or `<!-- parked-intent:v1 -->` marker) are scaled by 0.1. Urgency has a floor of
0.01, so every item restarts some mass.

## 5. Pressure (own + inherited)

**Wait-for graph *W*.** For every dependency edge there is a WAITS edge from waiter to blocker:

- DEPENDS_ON: from the waiter to the blocker.
- CHILD: from the parent to the child task.
- PARENT: from the parent to the child issue.
- CLOSES: from the issue to its PR.

Mentions, cross-references, supersession and duplicates are SOFT edges in the mention direction, with
weight *s* = 0.15. The nodes are every open (or unknown-state) item; closed items are satisfied and
leave the walk.

**Pressure** is the stationary distribution π of PageRank on *W*, with damping *d* = 0.85, restarting
in proportion to *u* (dangling mass restarts the same way):

```
π = (1 − d + d·D)·t + d · Pᵀ π          t = u / Σu,  D = dangling mass
own_i       = (1 − d + d·D) · t_i
inherited_i = d · Σ_j π_j · w_ji / out_j
score_i     = π_i / max_k π_k = (own_i + inherited_i) / max_k π_k
```

Reading it: an item ranks by its own urgency **plus the urgency of everything waiting on it**,
discounted per hop by *d*. A quiet blocker of three P0 items outranks a loud item that blocks nothing.
That is the "pressure to unlock and de-bottleneck".

The split is exact at the fixed point, which `test_issue_rank_v2.PressureWalk` asserts. With *u*
uniform, the walk reduces to the classical PageRank in `pagerank()`.

**Why this replaces v1's weighted sum.** v1 added `pressure` (transitive waiters, 0.25), `centrality`
(PageRank on references, 0.15) and `bridge` (betweenness, 0.10). Those are three correlated views of one
graph, 50% of the weight, and they ignored *who* was waiting: a parked item counted the same as a P0.
The walk counts the structure once and weights it by the waiters' urgency. PageRank, betweenness and
degrees stay in the output as diagnostics.

**Actionability.** The lanes PARKED, DEADLOCK and BLOCKED are excluded from the action queue. Their
urgency is not lost: the walk pushes it onto their blockers.

## 6. Structure

- **Deadlocks**: the strongly connected components of size > 1 in the waiter → blocker graph
  (Tarjan's algorithm). They get the lane DEADLOCK and the action "drop or re-plan one edge".
- **Blocker chains**: these are computed on the condensation DAG.
  - `chain.below`: the longest sequence of open items that must close, one after another, before
    this one can.
  - `chain.above`: the longest sequence of waiters on top of it.
  - `graph.critical_chain`: one longest chain overall.
- **unblocks_now**: the number of open items whose *only* open blocker is this one, which closing it
  frees immediately. `pressure` is the transitive count it relieves.

## 7. Golden thread (bottom-up view)

These lifecycle gates are scored by `jade_temple/tools/rolling5.golden_thread()`, which AGENTS.md
assigns as the owner. Each gate is PASS, FAIL or UNKNOWN.

| Track | Gates in order |
|---|---|
| CODE (an issue with a linked PR) | DEFINED, VERIFIABLE, OWNED, STARTED, UNBLOCKED, PR_GREEN, REVIEWED, DOD_MET, DOV_MET |
| OWNER (an issue without a PR) | DEFINED, VERIFIABLE, OWNED, STARTED, UNBLOCKED, DOD_MET, DOV_MET |
| PR | LINKED, READY, PR_GREEN, REVIEWED |

`position` is the number of consecutive passes from the start, and `first_break` is where to act.
REVIEWED fails on a live PR without an approving review: the D+14 audit's merge-without-review gap shows
up per item. A merged PR with no review record is UNKNOWN, never assumed. `lineage` (older references
back to a root) is provenance, not the golden thread.

## 8. Flow and burndown

Flow is per scope, for issues only, over a window of *T* days:

- arrivals *A* (created in the window), closures *C* (closed in the window, split by `stateReason`),
  WIP *N* (open now);
- rates *A/T*, *C/T* with **exact Garwood Poisson** 90% intervals;
- net burn (*C − A*)/*T* ± *z*·√(*C + A*)/*T* (normal approximation to a Poisson difference);
- Little's law: the time in system is about *N* / (*C/T*), with the interval taken from the closure
  rate;
- an **ETA** of *N* / net burn, given **only when the lower bound of the net burn is > 0**. Otherwise
  the status is `NOT_CONVERGING` or `GROWING`. A noisy positive estimate is not reported as a date.

**Predicate leaks** are issues closed as COMPLETED that have unticked items and no open successor
(SUPERSEDES / DUPLICATE_OF) or open parent to carry them. This is the pattern of the D+14 E-07 closure: the issue
closed, but its residual predicates have no home.

## 9. Uncertainty

The weights, *d* and *s* are judgements, so the rank is reported with its sensitivity.

*R* = 200 seeded draws (`MC_SEED`, reproducible). Each draw samples:

- weights ~ Dirichlet(20·w);
- *d* ~ U[0.75, 0.92];
- *s* ~ U[0.05, 0.30].

Per item it reports:

- the p05 / p50 / p95 rank;
- `p_top`, the probability of reaching the top 10;
- `robust_top`: the items with `p_top` ≥ 0.8.

Stability is the median and p05 of Spearman ρ between the base ranking and each draw. The three views
are compared with Kendall τ-b (`views.agreement`). They are different questions, so low agreement is
information, not error.

Bradley–Terry (gg_MATH `bt_uncertainty`) stays **withheld**. It needs observed pairwise outcomes, and
issues have none. The ordering is labelled `NON_BT_REVERSE_PRESSURE_PAGERANK`, consistent with the W2
issue-expedition doctrine.

## 10. Privacy

The hub is public and QPS is private.

- `out/` is gitignored.
- `--redact-private` replaces every private key in the model and the delta with a rank-ordered
  pseudonym (`owner/repo#PRIVATE-007`). It also drops titles, URLs, numbers, labels, assignees, overlay
  notes, free-text actions and head SHAs.
- The result must be a fixed point of `jade_temple/tools/private_boundary.py`.
- Pseudonyms are stable within one pulse only, so private deltas are counts.

## 11. Invariants under test

| Invariant | Tests |
|---|---|
| π sums to 1, π = own + inherited, uniform restart = classical PageRank | `PressureWalk` |
| an unobserved part is never 0; the priority prior is not the mean of the known values | `Urgency` |
| pressure reaches the blocker, the queue skips blocked items; sole-blocker count; deadlock; chain | `Structure` |
| rolling5 thread positions, CODE track breaks at REVIEWED | `GoldenThread` |
| Poisson matches the Garwood table; ETA only on a significant burn; leaks need no open successor | `Math`, `Flow` |
| seeded Monte Carlo is byte-reproducible; intervals stay in [1, n] | `MonteCarlo` |
| the redacted model and delta are private_boundary fixed points and leak no key, title or SHA | `Privacy` |
| net ticks and scope growth are separated; rooted vs unrooted new items | `Delta` |

## 12. Limits

- Comments are status notes and are not the plan: only body checklists count. Ticks are
  self-reported.
- Body references are DECLARED candidates. A text "depends on" can be wrong; prefer GitHub's
  blocked-by relation.
- The flow window counts issues closed in the window by API `since` (updated since). It is complete
  for the window, but not a time series. The series comes from the ledger across pulses.
- Weights are a declared policy, not fitted. Fitting needs observed outcomes, for example time to
  close per unit of pressure across ≥ 3 pulses. That is when the gg_MATH `bt_reverse_pressure`
  readiness should be re-checked.
