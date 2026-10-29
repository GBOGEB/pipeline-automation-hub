# Issue burndown ranking

`issue_rank.py` ranks every open issue and PR, per repository, for JADE (the four
federated repositories) and for USER (every repository of the owner that has open
items). It reads them from three sides:

| View | Order | Question it answers |
|---|---|---|
| 1. Bottom-up + golden thread | oldest first | Which old roots still carry open work, and through which chain of references? |
| 2. Top-down (mycelium) | newest first | What does each new item attach to (hyphae), and how far does it reach in two hops? |
| 3. Nodes / edges / graph | PageRank | Which items are central, which ones bridge clusters, and which ones block others? |

The ranking is **advisory**. It grants no closure, merge or dispatch authority.
A ticked checkbox is not a verified DoD; `CLOSE_CANDIDATE` means "verify the
evidence and close", not "closed".

## Run

```bash
python mission-control/issue_rank/issue_rank.py run --scope focus   # the four federated repos
python mission-control/issue_rank/issue_rank.py run --scope jade    # TOP21 roster
python mission-control/issue_rank/issue_rank.py run --scope user
python mission-control/issue_rank/issue_rank.py verify-ledger --ledger mission-control/issue_rank/out/jade/ledger.jsonl
python mission-control/issue_rank/issue_rank.py rank --snapshot out/jade/snapshot.json --prev old/issue_rank.json --out /tmp/r
```

`run` makes read-only GraphQL calls through `gh` (keyring auth; `unset GITHUB_TOKEN GH_TOKEN`
if it returns 401). Each scope writes to `out/<scope>/`: `snapshot.json`, `issue_rank.json`,
`issue_rank.csv`, `issue_rank.html`, `delta.json` and `ledger.jsonl`.

`out/` is gitignored. This repository is public and `cryoplant-project` is private, so
snapshots and rankings never get committed. `--redact-private` strips titles, URLs and
free-text actions of private items before anything is written, and does not persist
`snapshot.json` (raw bodies and comments): it deletes any earlier copy and keeps only the
snapshot digest in the ledger.

## Per-item progress (DoV / DoD / steps)

Parsing belongs to the triway burndown: `parse_checklist()` here maps
`triway_burndown.checklist()` (in `qps-triage-ultra/issue-expedition/`) onto counts per
section, and its plan file holds the vocabulary. In short, the parser reads the issue
body (comments are status notes, not the plan):

- `- [x]` is done, `- [ ]` is open; `- [~]`, `- [-]` and fully struck items are
  withdrawn and not counted.
- The nearest heading sets the section: **DOD** (DoD, definition of done, done when,
  acceptance, exit criteria, closure predicate, ...), **DOV** (DoV, verification,
  validation, required proof, ...), **STEPS** (steps, tasks, to-do, checklist,
  deliverables, plan, ...). An inline `- [ ] DoD: …` overrides the heading. Status
  headings such as "evidence" are not DoV.
- Plain bullets and prose paragraphs under a DOD / DOV / STEPS heading are **declared
  but untracked** criteria. They are counted as `untracked`, never as done.
- A live checklist item that references another issue (`- [ ] #123`, `- [x] #123`) makes
  that issue a CHILD; a withdrawn one (`- [~] #123`) stays a MENTION. A tick that
  disagrees with the child's state is reported as checklist drift.

Progress reads like `4/7 (DOV 1/2, DOD 2/3, STEPS 1/2) +3 untracked`. The checklist
state is one of `NO_CHECKLIST`, `UNTRACKED_CRITERIA`, `NOT_STARTED`, `IN_PROGRESS` or
`ALL_TICKED`.

To make an issue measurable, write it like this:

```markdown
## DoD
- [ ] behaviour X on exact head SHA, test name
- [ ] owner disposition recorded in #NNN
## DoV
- [ ] native CI run URL on the merged SHA
## Steps
- [ ] #NNN child task
Blocked by #MMM
```

## Edges

References come from issue and PR bodies, the last five comments, PR closing
references and the timeline (cross-references, connected PRs). `extract_refs()` maps
`triway_burndown.references()`, which reads GBOGEB references only: issue and pull URLs,
`GBOGEB/R#N`, federation shorthand (`QPS #N`, `ABACUS PR #N`, `hub #N`, `Mission
Control #N`), chained `/#N`, and bare `#N` (home repository). Fences, comments and
code spans are skipped.

The words just before a reference type it, and a keyword binds to the next reference
only:

| triway kind | Edge here |
|---|---|
| `PR_CLOSURE_CLAIM` (PR bodies only) | `CLOSES` |
| `DECLARED_BLOCKER_CANDIDATE` | `DEPENDS_ON` |
| `DECLARED_BLOCKS_CANDIDATE` | `BLOCKS`, stored reversed as `DEPENDS_ON` |
| `DECLARED_PARENT_CANDIDATE` / `DECLARED_CHILD_CANDIDATE` | `PARENT` / `CHILD` |
| `DECLARED_PREDECESSOR` / `DECLARED_SUCCESSOR` | `SUPERSEDES` / stored reversed as `SUPERSEDES` |
| `DECLARED_DUPLICATE_OF` | `DUPLICATE_OF` |
| `TEXT_ASSOCIATION`, `PR_ASSOCIATION` | `MENTION` |

A negation (`not part of #N`) keeps it a MENTION. Every referenced item outside the
snapshot is resolved for its state and creation time; references to nothing (`#1` used
as list numbering) are dropped. A blocker whose state is unknown counts as open (fail
closed).

## Score and lanes (method v2, see METHOD.md)

Two stages, so graph structure is not counted three times:

1. **Urgency** `u` (what the item asks for on its own) is a weighted mean of
   `priority 0.35, nearness 0.20, pr_ready 0.15, age 0.15, idle 0.15`, each in [0, 1].
   A part that is not observed is **never 0**: priority takes a declared neutral prior
   (P2, because owners label only the urgent few), and the other parts take the scope
   mean. `coverage` is the share of weight actually observed, and `imputed` lists the
   parts that were filled in. Parked intents are scaled by 0.1.
2. **Pressure** is PageRank over the wait-for graph (waiter → blocker on DEPENDS_ON /
   CHILD / PARENT, issue → the PR that closes it; mentions as soft edges, weight 0.15).
   The walk restarts in proportion to `u`, with damping 0.85. At the fixed point
   `score = own + inherited` exactly, where `inherited` is the urgency its waiters push
   onto it. A blocker of an urgent item ranks high even when it is quiet itself.

A **Monte Carlo** run (200 seeded draws, perturbing the weights (Dirichlet,
concentration 20), damping in [0.75, 0.92] and soft weight in [0.05, 0.30]) gives each
item a 90% rank interval `rank_interval` and `p_top`, the probability of reaching the
top 10. `robust_top` lists the items with `p_top` ≥ 0.8. The ordering is
`NON_BT_REVERSE_PRESSURE_PAGERANK`: Bradley–Terry stays withheld, because issues have no
observed pairwise outcomes.

Structure per item:

- `pressure`: open items that wait on it transitively.
- `unblocks_now`: items for which it is the only open blocker.
- `chain.below`: the longest blocker chain that must close first.
- `deadlock`: membership of a dependency cycle.
- Each edge has a `binding`. GitHub's own relations (blockedBy / blocking / parent /
  sub-issues / closing PRs) and timeline events are `OBSERVED`; parsed text is
  `DECLARED`.

The **golden thread** is the lifecycle gate chain scored by
`jade_temple/tools/rolling5.golden_thread()`. The gates are DEFINED, VERIFIABLE, OWNED,
STARTED, UNBLOCKED, then on the CODE track PR_GREEN and REVIEWED, then DOD_MET and
DOV_MET. It reports a position (for example `5/9`), the first break and the next step.
`lineage` (older references back to a root) is provenance, not the golden thread.

The lane gives the next action, checked in this order:

- PRs: `FIX_RED`, `IN_FLIGHT` (draft), `REVIEW` (not approved), `AWAIT_CHECKS` (approved,
  checks not all green yet), `MERGE_READY` (approved and every check green).
- Issues: `PARKED`, `DEADLOCK`, `BLOCKED`, `CLOSE_CANDIDATE`, `FIX_RED`, `REVIEW` (the
  linked PR is green but not approved), `MERGE_READY`, `BOTTLENECK` (two or more
  waiters, or two or more freed now), `NEARLY_DONE` (70% or more ticked, or one item
  left of three or more), `TRACK_DOD`, `DEFINE_DOD`, `NOT_STARTED`, `IN_PROGRESS`.

The **action queue** is every item not BLOCKED, DEADLOCK or PARKED, in pressure order.

## Recursive title families for issues and PRs (v1)

Both issues and pull requests now consume the same deterministic prefix grammar from title_taxonomy.py. Source titles remain unchanged. Parser precedence: safety markers, bracket tags, chained Conventional Commit heads, recursively nested parentheses, then leading programme/wave clauses. Do not derive action family from ordinary body prose.

| GitHub title example | Primary family | Canonical prefix path | Distinct facet |
|---|---|---|---|
| metrics: refresh DMAIC commit metrics | metrics | metrics | DMAIC in description only |
| metrics: #### ###(fix) refresh | metrics | metrics/fix | Markdown heading fragments are presentation, not family IDs |
| metrics: ###(fix(test W51-C0)) repair | metrics | metrics/fix/test/W51/C0 | nested post-head action, test, wave, cohort |
| feat(test W51-C0): zero-to-positive coverage | feat | feat/test/W51/C0 | W51 wave; C0 cohort |
| metrics: fix(test W51-C0): ... | metrics | metrics/fix/test/W51/C0 | nested action fix + test |
| fix(jade devops): ... | fix | fix/JADE/DEVOPS | two scope levels |
| [U14] Main red since ... | UNCLASSIFIED | UNCLASSIFIED/U14 | U14 work ID; no invented fix |
| P0 CBS N+4: ... | UNCLASSIFIED | UNCLASSIFIED/P0/CBS/N+4 | label text is not accepted owner priority |
| DO NOT MERGE — MACH-II canary | UNCLASSIFIED | UNCLASSIFIED/MACH-II | DO_NOT_MERGE flag survives |
| QPS BNB N+4 R01 — ... | UNCLASSIFIED | UNCLASSIFIED/QPS/BNB/N+4/R01 | programme and wave |

Each item emits title_taxonomy.family, path, prefix_segments with nesting depth and source, programmes, codes, priority, policy_flags, classification and lint. The item also records related_families from up to two graph hops with source item, edge type and UNVERIFIED_ASSOCIATION_ONLY grade. Related PR names never overwrite an issue's family or confer closure, status, ownership or acceptance.

Each rollups[repo].title_taxonomy and rollups.JADE/USER.title_taxonomy contains disjoint family counts split by Issue/PullRequest, exact leaf_clusters, non-additive hierarchy_nodes_nonadditive, programme/code facets, **nonexclusive topic_families and technical_clusters from case-insensitive, word-bounded matches on title and labels**, lint counts and coverage. Family totals sum to the actual item population; parent hierarchy nodes must not be summed as totals. HTML presents a per-repo/JADE/USER family census and top leaf clusters; CSV adds family, prefix_path, prefix_codes and candidate-family fields; delta.json records taxonomy_moves separately from real completion.

Privacy: --redact-private replaces every private title taxonomy with REDACTED_PRIVATE, removes private-issue linked candidate labels, and rebuilds each rollup from public records only; private_items_excluded is explicit. Do not commit raw snapshots or unredacted QPS title clusters into public repositories.

Overlap control (26 October): #925 is an independent parallel title-taxonomy draft that touches the same paths. Its selected topic and technical cluster vocabulary is integrated here as secondary, nonexclusive observational facets. #925 and #927 must not both merge independently. #926 fixes critical prior #907 privacy, ready-state and dropped-checkbox bugs and should be governed-landed first; rebase/retest this PR afterwards. No check success on this PR authorizes bypassing #926. Explicit syntactic prefix family and associated title/label topics are **different dimensions**; only primary families are disjoint and additive. Inferred cross-linked candidates do not inherit authoritative family, class, DoV/DoD, reviewer or owner approval.

No automatic GitHub issue title rewrites. A later owner-authorized metadata migration can propose conventional family prefixes on issues while retaining old title, number, source signature and dependency edges; until then unknown prefixes stay UNCLASSIFIED.

## Rollups and telemetry

Scopes are USER (every fetched repository), JADE (the TOP21 roster in
`jade_temple/data/TOP21_PORTFOLIO.json`), FOCUS4 (the four federated repositories) and
each repository. `complete` says whether every repository of the scope was fetched.
Per scope the rollup reports:

- open issues and PRs, and tasks ticked / total;
- untracked criteria, checklist / DoD / DoV coverage, measurable share and mean coverage;
- state, lane and golden-thread first-break distributions;
- red and unapproved PRs, median age, items idle for more than 21 days, checklist drift;
- actionable / parked / deadlocked counts and the share of total pressure;
- the top 10, the action queue, the robust top, the bottlenecks, the nearly-finished
  items and owners by summed score;
- **flow** over the window (`--window-days`, default 14).

Flow covers issues only:

- arrivals and closures per day with exact (Garwood) Poisson 90% intervals, and closure
  reasons (COMPLETED / NOT_PLANNED / DUPLICATE);
- net burn;
- Little's-law time in system;
- an ETA, given only when the lower bound of the net burn is above 0. Otherwise the
  status is `NOT_CONVERGING` or `GROWING`.

`predicate_leaks` lists issues closed as completed with unticked items and no open
successor or parent to carry them.

Every `run` appends a row to `ledger.jsonl` (`jade.issue-rank.ledger.v1`). Each row is
sha256-chained to the one before it and records:

- the snapshot and output digests;
- the default-branch head SHA of every repository (one pulse per snapshot);
- fetch telemetry: API calls, retries, GraphQL cost and remaining points, seconds, and
  resolved and missing references;
- graph stats, the method version, walk convergence and Monte Carlo stability (median
  Spearman);
- scope rollups and the delta counts.

`delta.json` lists what moved since the previous pulse:

- new items, split into rooted (linked to the existing network) and unrooted;
- gone items, split by closure reason;
- new and removed links, and new PR→issue dependencies;
- checklist moves, with net ticks kept apart from net scope growth (`2/5 → 3/6` is one
  tick plus one new item);
- lane moves and golden-thread advances and regressions.

`--redact-private` projects private items to rank-ordered pseudonyms
(`owner/repo#PRIVATE-007`) in the model and the delta. The result must be a fixed point
of `jade_temple/tools/private_boundary.py`.

`overlay.json` holds owner-declared priorities with provenance (the D+14 lanes for the
public repositories). `out/overlay_private.json` (gitignored) holds the private ones.

## Burndown slices (`burndown_apply.py`)

Reads a pulse directory and writes `burndown_slices.json` (`jade.issue-burndown.slices.v1`).
Dry-run unless `--apply` is given.

- **verify:** every open checklist item that references a closed child, with the child's
  evidence (merge SHA, check rollup on the merge commit, review decision, close reason).
  Classes: `TICK_READY` (a bare reference whose children all merged or completed),
  `VERIFY` (children closed, the item asks for more), `WITHDRAW_CANDIDATE` (a child closed
  unmerged or not planned), `WAIT` (a child still open).
- **checkbox:** for the top `TRACK_DOD` issues, turn each declared DoD / DoV / STEPS bullet
  into `- [ ]`, ticking nothing. `--skip` leaves out issues whose bullets are options or
  dispositions rather than criteria.
- `--apply tick|checkbox|all [--only KEY ...]` edits issue bodies: it re-reads the live
  body, refuses if it changed since the snapshot, and appends a sha256-chained row per
  edit to `edits.jsonl`. Issue edits are owner decisions; apply only with the owner's
  go-ahead.

```bash
python mission-control/issue_rank/burndown_apply.py --pulse mission-control/issue_rank/out/jade --skip GBOGEB/cryoplant-project#1738
```

## Reuse and ownership

- **Parsers and owners (#906, #907, #927, #928).** `qps-triage-ultra/issue-expedition/triway_burndown.py`
  owns the checklist and reference parsers, its standalone five-repo issue census and the
  oldest / newest / connected orderings. This module loads it with `importlib` and keeps
  only thin adapters; fix parsing there. This module owns USER / JADE graph ranking,
  PR / issue edges, lanes and the ledger. Both consume the title-vocabulary provider
  `title_taxonomy.py` in this directory. Neither merge establishes governance admission.
- gg_MATH (`GBOGEB/gg_MATH`) has `kernels/bradley_terry.py` (pairwise ranking),
  `kernels/spectral_graph.py` (Laplacian, Dirichlet energy) and
  `mission/federation/n5_repo_graph_math.py` (typed graph, spectral gap; at most 64
  nodes). None of them does PageRank, betweenness or transitive pressure on a graph of
  this size, so those live here. Bradley–Terry needs pairwise judgements, which issues
  do not provide.
- The CODE PURPLE BD census (`gogreen/bd_queue_wave.py`) and the scale dock's
  `dock_issue_bd` count workflow manifestations on PRs. This module ranks items; it does
  not re-count those manifestations.

## Roadmap

1. **Done (v2).** Unknown-not-zero urgency, pressure walk, Monte Carlo intervals,
   deadlocks / chains, lifecycle golden thread, flow, leaks, OBSERVED API relations,
   overlay, private projection. Contract tests on py3.11 / 3.12; see PLAN.md.
2. **Make progress measurable.** Agree the DoD / DoV / Steps template with the owners.
   Convert the `TRACK_DOD` issues, top-ranked first, from plain bullets to checkboxes.
   This edits issues, so the owner decides.
3. **Scheduled public pulse.** Run a cron workflow on the three public repositories with
   `--redact-private`, and keep the ledger as a workflow artifact. Add `dock_issue_rank`
   to `gogreen/scale_dock.py` in its own PR, since that module owns the docks.
4. **Root join.** Join `FIX_RED` lanes to EVERRED roots (`p-process/everred/harvest.py`)
   so red PRs rank by root, not by occurrence. Feed the QPS 67-ID BD recensus (#481).
5. **gg_MATH upstream.** Propose `kernels/graph_centrality.py` (PageRank, Brandes) and
   the `issue_math.py` primitives (SCC, chains, exact Poisson interval) to gg_MATH, then
   bind them through `ggmath_bridge.py rebind` and import them here instead of the
   local copy. Cross-check each component's spectral gap with
   `spectral_graph.laplacian`.
6. **Owner pairwise priority.** Where owners rank items pairwise, fit Bradley–Terry with
   `level1/runtime.py` `bt()` and add it as a score part.
