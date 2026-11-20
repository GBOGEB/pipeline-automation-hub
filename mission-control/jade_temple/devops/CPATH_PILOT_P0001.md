# C-PATH pilot P0001: critical path, unlock, back-pressure and attack vectors

Pulse: `data/CPATH_PILOT_P0001.json` (`jade.cpath.pilot.v1`), issue graph read 2026-11-16T18:15Z in one pass.
Method owner: `devops/cpath.py`. Runner: `devops/cpath_pilot.py`. Private repos are aggregate-only.

## Can Kahn give the critical path?

Yes. Kahn gives a valid order. One forward pass over it gives each item's earliest
start and finish, and one backward pass gives the latest start and finish:

```
ES(v) = max EF(pred)      EF = ES + d
LF(v) = min LS(succ)      LS = LF - d      total float = LS - ES
```

Zero float is the critical path. This is the Critical Path Method (CPM); with unit
durations it equals the existing hop-count `cicd_dag.critical_path()` (tested).
CPM adds what the hop count cannot show:

- **Float.** It shows how much each item can slip without moving the end date.
- **Remaining-work path.** Done items take zero time, so the path follows what is
  still open, not the original plan.
- **Ties.** H10 and H11 are both critical; the hop count reports only one.
- **Uncertainty.** A Monte Carlo *criticality index* gives the share of runs in which
  an item is critical when durations vary.
- **Deadlocks.** Cycles are collapsed (strongly connected components) and reported,
  never silently ordered.

## Findings

**1. Release gates (H01–H12): the path moved.** Over the full plan the critical path is
H01→H02→H04→H05→H10→H12, and H08 has 2 units of float. In the FOCUS5 pulse P0005
(observed 2026-11-04) H01, H02, H04, H05 and H06 pass in every repo, so the
**remaining** path is **H08 → H09 → H12**. H08 is the one gate whose closing releases
another (H09). The hop count over the full plan still points at the finished chain.
All remaining gates are UNKNOWN, not FAIL: the bottleneck is missing evidence.

**2. Issue backlog (JADE top-5): wide, not deep.** 256 open issues and PRs, 94
declared dependency edges, a critical path only 3 long, 4 waves, and 1 deadlock
(private, 2 items). 203 open items have no declared dependency at all. Throughput
limits this backlog, not the order of the work: with up to 16 workers every policy
finishes within 1 unit of the lower bound. Ordering still matters in one way:
critical-path-first or unlock-first releases the first blocked item at step 1, versus
step 15 for oldest-first with one worker. Top unlock lever:
pipeline-automation-hub#1180 (releases 3, relief 4), then #336 (2, 3).

**3. Scale (synthetic, 1k / 10k / 100k nodes, heavy-tailed effort).** CPM takes
0.008 s / 0.1 s / 2 s. Critical-path-first always reaches the lower bound. Its gain
over oldest-first is largest when the worker count is near the **balance point**

```
W* = total work / critical-path length
```

| nodes | W* | gain at 4 workers | 16 | 64 |
|---|---|---|---|---|
| 1,000 | 6.5 | 7.1% | 9.5% | 1.8% |
| 10,000 | 17.6 | 0.5% | **17.5%** | 5.5% |
| 100,000 | 51 | 0.1% | 0.8% | **17.5%** |

Below W* capacity is the limit and order hardly matters. Far above W* the path is the
limit and every order is fine. At W* about 17% of the elapsed time comes from order alone.

**4. Do the attack vectors multiply?** Not against each other. Critical-path-first and
unlock-first pull the same items forward (verdict OVERLAP: the combination equals
critical-path-first alone). The multiplier is **critical-path order × the right number
of parallel workers**: neither helps much alone, together they give the 17%.

**5. PCA/BT back-pressure on the BD queue: wired, held.** The mechanism raises or lowers
BD-class priority from BT scores and cuts the WIP cap from the PCA queue-friction
share. On committed evidence it is **NEUTRAL_HOLD**: BT has 2 measured pairs (gate 5),
PCA has 5 rows (gate 10), and there is no BD-class → BT-intervention crosswalk. A
labelled counterfactual shows what it would do: REVIEW_WAIT and ACTIONABLE ×1.5,
OWNER_HOLD and DEPENDENCY_HOLD ×0.5, WIP cap 6 → 4.

## What this means for the next slices

- **Gates:** close H08 evidence first in each FOCUS5 repo; refresh the FOCUS5 pulse,
  which is 12 days old.
- **Issues:** add capacity (disjoint parallel lanes), not reordering; declaring the
  missing dependencies is what would make critical-path ordering useful here.
- **Back-pressure:** needs an owner-approved crosswalk and 5+ BT pairs / 10+ PCA rows.

## Limits

- **Durations.** Work durations are unit (unknown, not zero); the criticality index
  shows how sensitive each answer is to that assumption.
- **Dependencies.** Issue edges come from issue and PR bodies only, via issue_rank's
  parser over REST; comments and timeline cross-references were not read.
- **Unresolved references.** 77 references were outside the open set: 65 were
  resolved, 9 were not found and 3 were out of scope.
- **Relief at scale.** Above 5,000 nodes the UNLOCK policy ranks by immediate
  releases only, because the canonical transitive relief costs one breadth-first
  search per node.
