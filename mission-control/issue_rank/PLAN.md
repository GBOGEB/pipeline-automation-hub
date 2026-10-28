# Issue burndown — plan, architecture and first pulse (2026-10-26)

Method: [METHOD.md](METHOD.md). Owners: parsing is `issue-expedition/triway_burndown.py` (#906, #928) and
ranking is `issue_rank.py` (#907, #929, this PR). The hub is public, so QPS appears here as counts only.
Run with `out/` locally for the full private view.

## 1. Execution architecture

```
GitHub GraphQL (read-only, gh keyring)            one pulse = one head SHA per repo (L6)
  ├─ open issues + PRs, relations (blockedBy / blocking / parent / sub-issues / closing PRs)
  ├─ issues closed in the window, PR checks + approvals, timeline cross-references
  └─ referenced items resolved (state, created)
        │ snapshot.json (local, gitignored; not persisted with --redact-private)
        ▼
triway_burndown.checklist() / references()        DoD / DoV / STEPS, typed DECLARED references
        ▼
issue_rank.build_graph()                          OBSERVED + DECLARED edges, stubs, closed-window nodes
        ▼
urgency()  ──►  pagerank(teleport=u, split)  ──►  monte_carlo()     score = own + inherited, 90% rank interval
issue_math: strongly_connected / blocker_chains   deadlocks, chain.below, critical chain, unblocks_now
rolling5.golden_thread()                           lifecycle position + first break + next step
flow() / predicate_leaks()                         Poisson rates, Little's law, ETA, closed-with-open-items
        ▼
rollups: USER / JADE (TOP21) / FOCUS4 / repo      views: bottom-up, top-down, graph, action queue, agreement
        ▼
out/<scope>/issue_rank.{json,csv,html}, delta.json, ledger.jsonl (sha256 chain)
        └─ --redact-private: pseudonyms, then private_boundary fixed point
```

**Cost of one USER pulse** (25 repositories, 214 open items, 1,755 nodes, 4,414 edges):

- 117 GraphQL calls, 118 rate-limit points (4,745 left);
- 164 s wall time;
- 200 Monte Carlo draws.

The walk converges in 109 iterations, with a residual of 1e-10.

## 2. First pulse (USER, 2026-10-26T08:29Z)

| Scope | Open issues | Open PRs | Ticked / total | Checklist coverage | DoD declared | DoV declared | Arrivals / day (90%) | Closures / day (90%) | Status |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| USER | 175 | 39 | 49 / 392 | 19% | 47% | 13% | 4.64 (3.74–5.71) | 1.71 (1.18–2.41) | GROWING |
| JADE (TOP21) | 174 | 39 | 49 / 392 | 19% | 47% | 13% | 4.57 | 1.71 | GROWING |
| FOCUS4 | 168 | 39 | 49 / 346 | 18% | 46% | 13% | 4.57 | 1.71 | GROWING |
| ABACUS | 43 | 3 | 41 / 160 | 28% | 49% | 5% | 1.50 | 1.50 | NOT_CONVERGING |
| hub | 45 | 35 | 5 / 65 | 13% | 27% | 27% | 1.36 | 0.07 | GROWING |
| CODEX | 14 | 0 | 0 / 15 | 14% | 29% | 0% | 0.57 | 0.00 | GROWING |
| QPS (private, counts only) | 66 | 1 | 3 / 106 | 15% | 62% | 12% | 1.14 | 0.14 | GROWING |

The window counts matched the search API exactly in all four repositories (closed / created since
2026-10-12: hub 1 / 19, ABACUS 21 / 21, CODEX 0 / 8, QPS 2 / 16).

Of the 24 closures, 15 were DUPLICATE and 9 were COMPLETED.

| Finding | Value | Meaning |
|---|---|---|
| Net burn, USER | −2.93 / day (−4.04 to −1.82) | The backlog grows at 90% confidence. No ETA is given. |
| Little's law, USER | 102 days (73–148) | Mean time in system at the current closure rate. |
| Nearly finished | 0 items | No open issue is at 70% or more ticked. "Nearly done" cannot be shown today. |
| Golden thread first break | DEFINED 84, VERIFIABLE 83, OWNED 7, STARTED 1 | Almost every issue stops before ownership: a definition and verification debt, not an execution debt. |
| Untracked criteria | 535 | Declared DoD/DoV bullets or prose with no checkbox. These are the cheapest progress signal to unlock. |
| Unassigned | 183 of 214 open items | The OWNED gate fails for nearly all items. |
| Deadlock | 1 cycle (2 QPS intake issues) | Re-plan one edge. |
| Longest blocker chain | a QPS P0-A item → hub #604 → CODEX #1198 | A cross-repository chain of 3. |
| Predicate leaks | 0 in the window | No COMPLETED closure left unticked items without a successor. |
| Rank stability | Spearman median 0.994 (p05 0.986) | The order is robust to the weight, damping and soft-edge choices. |

**View agreement.** Kendall τ-b is 0.34 between bottom-up and pressure, and 0.58 between graph and
pressure. The top-10 Jaccard between bottom-up and pressure is 0. The oldest items are not the most
pressing, so the three views answer different questions.

**v1 against v2 on the same snapshot.**

- Kendall τ 0.58, Spearman 0.78, top-10 overlap 5 of 10.
- v1 scored nearness 0 for **142 of 175 issues (81%)** because they had no checklist.
- v1's centrality and bridge parts correlate at ρ = 0.68: the same structure is counted twice.

## 3. Ranked action queue (public repositories; actionable only)

| Pressure rank (90%) | Item | Lane | Progress | Golden thread | Why it ranks |
|---|---|---|---|---|---|
| 2 (2–3) | hub #372 MIP-STABILIZE | BOTTLENECK | 16 criteria, none tickable | 0/7, DEFINED | Frees 1 now and relieves 3 |
| 3 (2–3) | hub #336 W305-A1 required-status barrier | TRACK_DOD | 7 criteria, none tickable | 0/7, DEFINED | P0-A overlay; frees 1 |
| 4 (4–5) | ABACUS #1929 BD–LDAB root-cause census | DEFINE_DOD | no checklist | 0/7, DEFINED | Blocks #1860 (rank 1, blocked) |
| 5 (5–7) | ABACUS #1738 Bandit/Safety baseline red | TRACK_DOD | 6 criteria | 1/7, VERIFIABLE | P0-C; blocks #1860 |
| 6 (5–7) | ABACUS #1996 A10 confidentiality disposition | NOT_STARTED | 0/5 DoD | 1/7, VERIFIABLE | P0 title; frees 1 |
| 8 (8–10) | hub #636 QPS TRIAGE N2 census | TRACK_DOD | 2 criteria | 0/7, DEFINED | P1-C overlay |
| 12 (9–22) | CODEX #753 QPS v6 publication lane | DEFINE_DOD | no checklist | 0/9, DEFINED | P1-B overlay |
| 13 (13–20) | ABACUS #1278 CI governance red → merge | BOTTLENECK | no checklist | 0/7, DEFINED | Relieves 2 |
| 14 (10–20) | CODEX #977 authenticated crew execution | NOT_STARTED | 0/7 steps | 1/7, VERIFIABLE | P0-A overlay |

ABACUS #1860 holds rank 1 (interval 1–1, P(top 10) = 1.0) with 96% of its score inherited. It is BLOCKED,
so its pressure is the reason #1929 and #1738 rank 4 and 5. The QPS P0 lanes from the D+14 audit rank
37–50: they are high priority but have few waiters. The QPS P0-A item is itself blocked by hub #604.

## 4. Plan

| # | Step | Owner | Done when (DoD) | Verified by (DoV) | KPI it moves |
|---|---|---|---|---|---|
| 1 | Merge #928, then #926 and #929, then this PR, in that order | GBOGEB | All four merged with First-Pass Closure green and one independent approval each | Native `issue-expedition` and `issue-rank` checks on py3.11 / 3.12 at the merged SHAs | No double ownership on master |
| 2 | Convert declared criteria to checkboxes, top-ranked first (hub #372, #336, ABACUS #1738, #1996 …) | Issue owners (edits issues, so the owner decides) | The top 20 of the action queue have a DoD and a DoV checklist | The next pulse shows a measurable share above 61% and DEFINED / VERIFIABLE breaks below 84 / 83 | Measurable share, thread funnel |
| 3 | Assign owners to the action queue | GBOGEB / SPOCs | Every item in the top 20 has an assignee | `by_assignee`; OWNED breaks fall from 7 | OWNED gate |
| 4 | Re-plan the QPS intake deadlock | QPS owner | The cycle is gone from `graph.deadlocks` | Next pulse | Deadlocks = 0 |
| 5 | Use GitHub blocked-by / sub-issue relations instead of text | Issue authors | New dependencies are recorded as relations | `edges_by_binding.OBSERVED` among DEPENDS_ON / PARENT rises | Edge evidence quality |
| 6 | Scheduled public pulse (cron, three public repos, `--redact-private`, ledger as an artifact), plus `dock_issue_rank` in `scale_dock.py` in its own PR | Mission Control | A workflow runs daily with read-only permissions | Ledger chain verifies across ≥ 3 pulses | Time series for burndown |
| 7 | After ≥ 3 pulses, fit the weights to an observed outcome (days to close per unit of pressure) and re-check gg_MATH `bt_reverse_pressure` readiness | gg_MATH / Mission Control | A fit or an explicit WITHHELD decision is recorded | The ggmath_bridge envelope | Calibrated weights |
| 8 | Upstream PageRank / Brandes / SCC / chains / Poisson to gg_MATH and bind them by SHA | gg_MATH | The kernels merge in gg_MATH and `ggmath_bridge rebind` is done | Digest-verified import | One math owner |

## 5. Telemetry per pulse (ledger row)

- **Head SHAs**: every repository in scope, read once per pulse.
- **Fetch**: calls, retries, GraphQL cost, remaining points and seconds; references resolved and missing.
- **Graph**: nodes, edges by kind and binding, components, isolated items.
- **Model**: method version, walk iterations and residual, Monte Carlo draws, seed and Spearman median /
  p05.
- **Per scope**:
  - open items, tasks ticked / total, untracked criteria;
  - checklist / DoD / DoV coverage, measurable share, mean coverage;
  - lanes and thread funnel;
  - actionable / parked / deadlocked counts;
  - pressure share;
  - flow: arrivals, closures, intervals, net burn, Little's law, ETA, status;
  - predicate leaks.
- **Delta**: new items (rooted and unrooted), gone items by reason, new and removed links, new PR
  dependencies, net ticks against scope growth, lane and thread moves.

MERGE_ADMISSION=HOLD · authority_transfer=false · formal_credit_delta=0. The ranking is advisory. No issue,
ruleset or Pages mutation is made by this tool.
