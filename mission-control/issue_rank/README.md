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
python mission-control/issue_rank/issue_rank.py run --scope jade
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

## Score and lanes

```
score = 0.25·pressure + 0.20·nearness + 0.15·priority + 0.15·centrality
      + 0.10·bridge + 0.10·pr_ready + 0.05·age
```

| Part | Definition |
|---|---|
| pressure | open items that transitively wait on this one (DEPENDS_ON, CHILD, PARENT), log-scaled |
| nearness | ticked / total; 1.0 when all ticked |
| priority | P0 1.0, P1 0.66, P2 0.33, P3 0.1 (label or title); critical / urgent / blocker 0.66 |
| centrality | percentile of weighted PageRank (a reference passes importance to its target) |
| bridge | percentile of Brandes betweenness on the undirected graph |
| pr_ready | linked or own PR green 1.0, red 0.5, none 0 |
| age | percentile of age |

`score_parts` is stored per item so every rank can be explained. The lane gives the
next action, checked in this order:

- PRs: `FIX_RED`, `IN_FLIGHT` (draft), `REVIEW` (not approved), `AWAIT_CHECKS` (approved,
  checks not all green yet), `MERGE_READY` (approved and every check green).
- Issues: `BLOCKED`, `CLOSE_CANDIDATE`, `FIX_RED`, `BOTTLENECK` (two or more open
  waiters), `NEARLY_DONE` (70% or more ticked), `TRACK_DOD`, `DEFINE_DOD`,
  `NOT_STARTED`, `IN_PROGRESS`.

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

For each scope (USER, JADE, each repository) the rollup reports open issues and PRs,
tasks ticked / total, untracked criteria, checklist / DoD / DoV coverage, the state and
lane distributions, red and unapproved PRs, median age, items idle for more than 21
days, checklist drift, the top 10, the bottlenecks and the nearly-finished items.

Every `run` appends a row to `ledger.jsonl` (`jade.issue-rank.ledger.v1`). Each row is
sha256-chained to the one before it and records the snapshot and output digests, the
default-branch head SHA of every repository (one pulse per snapshot), fetch telemetry
(API calls, retries, seconds, resolved and missing references), graph stats, scope
rollups and the delta counts. `delta.json` lists what moved since the previous pulse:
new and gone items, new and removed links, new PR→issue dependencies, checklist moves
(`2/5 → 3/5`) and lane moves.

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

1. **Now.** Engine, contract tests (3.11 / 3.12), local pulses for JADE and USER.
2. **Make progress measurable.** Agree the DoD / DoV / Steps template with the owners.
   Convert the `TRACK_DOD` issues, top-ranked first, from plain bullets to checkboxes.
   This edits issues, so the owner decides.
3. **Scheduled public pulse.** Run a cron workflow on the three public repositories with
   `--redact-private`, and keep the ledger as a workflow artifact. Add `dock_issue_rank`
   to `gogreen/scale_dock.py` in its own PR, since that module owns the docks.
4. **Root join.** Join `FIX_RED` lanes to EVERRED roots (`p-process/everred/harvest.py`)
   so red PRs rank by root, not by occurrence. Feed the QPS 67-ID BD recensus (#481).
5. **gg_MATH upstream.** Propose `kernels/graph_centrality.py` (PageRank, Brandes) to
   gg_MATH, then bind it through `ggmath_bridge.py rebind` and import it here instead
   of the local copy. Cross-check each component's spectral gap with
   `spectral_graph.laplacian`.
6. **Owner pairwise priority.** Where owners rank items pairwise, fit Bradley–Terry with
   `level1/runtime.py` `bt()` and add it as a score part.
