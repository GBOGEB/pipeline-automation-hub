# Title taxonomy: engineering handover

> **In pipeline-automation-hub** this handover lives in `mission-control/issue_rank/title_census/`. There `out/` is `outputs/` (large files gzipped), the scripts are in `reference/title_taxonomy_src.zip`, and the reconciliation into the owner `../title_taxonomy.py` is in `RECONCILIATION.md`. See `README.md`.

Session date 2026-10-26. Owner GBOGEB. Status: working tool and census; one small set of GitHub issue edits applied; landed as artefacts only (no code path) in PR #934 (targets master after #927 merged). It overlaps open draft PRs pipeline-automation-hub #925 and #927 (see "Overlap").

## What it does

Puts every PR and issue title in the GBOGEB repositories into one vocabulary:

```
<type>(<scope>[,<scope>][ <qualifier>...])[!]: <subject>
fix(jade devops N12): census fails closed when blobs are missing
```

| Level | Example | Source |
|---|---|---|
| type family | `defect` | `vocabulary.json` `types.*.family` |
| type | `fix` (aliases `bugfix`, `hotfix`, ...) | `vocabulary.json` `types` |
| family (cluster) | `jade-devops` | `vocabulary.json` `families` (26) |
| scope | `census` | `families.*.scopes` with aliases |
| qualifier | `N12` (pulse), `W327` (wave), `GOV-001` (ticket) ... | `vocabulary.json` `qualifiers` (13 classes) |
| prefix | `fix(census)`; family prefix `fix(jade-devops)` | concatenation |

For each row it records **where** type and scope came from: `title` (explicit prefix), `lead` (a freeform label such as `W327:` or `CBD W4:`), `label`, `branch`, `pr#N` (closing PR), `keyword`, `parent#N`, `children`. Issues inherit recursively: own title > label > closing PR > keyword > parent issue > sub-issues, with a cycle guard. Confidence = `explicit` / `strong` / `inferred` / `none`.

Lint rules T001 to T011 (`taxonomy.py` `LINT_RULES`): no prefix, unknown type, type alias, missing scope, unmapped scope, scope alias, scope used as type, bracket tag outside prefix, long subject, empty subject, freeform lead label.

## Files

| File | Role |
|---|---|
| `vocabulary.json` | The vocabulary: 12 types, 26 families, scopes and aliases (`=alias` = only inside an explicit prefix or label, never free text), qualifier patterns, type keywords, label map, `generic` families that lose to domain families in free-text inference |
| `graph.py` | PR / issue crosswalk edges: `closes` (PR -> issue, both sides, cross-repo), `parent` (sub-issues), `mentions` (`#123`, `Repo#123`, `PR123` in titles), `refs` (body references), `xref` (timeline cross-references); one edge per pair, strongest type wins. Counts only: PageRank / betweenness stay with `issue_rank.py` |
| `test_graph.py` | 7 edge tests |
| `test_fetch.py` | 4 tests: timeline and check-suite paging, run binding for --resume |
| `fetch_checks.py` | Per-PR CI evidence (head OID, last 10 commit states, head-commit workflow runs); about 2 GraphQL points per 50 PRs |
| `ci_census.py` | Per-family CI view on the PAH owners (`red_trace.classify`, `cicd_dag.everred_metrics`, red-trace data, DAG crosswalk) |
| `taxonomy.py` | `Vocabulary`, `parse_title`, `lint`, `classify_own`, `classify_all` (recursive issue inheritance), `suggest_title` (lossless: never drops a label token or ID), `levels` |
| `test_taxonomy.py` | 18 unit tests (`python -m unittest test_taxonomy`) |
| `fetch.py` | Read-only GraphQL fetch via `gh`; one pulse, each repo's default-branch head SHA recorded (AGENTS.md L6); `--resume` reuses `data/repos/*.json` |
| `report.py` | Census: per repo and ALL, per kind (pr / issue / all), per level: n, share, rank, open/closed/merged, n_30d, trend, median days to close, first/last seen; monthly series with running totals; conformance; keyword inventory; dry-run issue plan |
| `dash_export.py` | Shapes outputs into the dashboard's datasets (`out/dash/*.json`) |
| `apply_issues.py` | Applies the issue plan with `gh issue edit`; dry run unless `--apply`; adds labels only, never removes; re-reads each issue and skips it if its title or state changed since the pulse |
| `manifest.py` | `MANIFEST.json` with sha256 of every artefact; `--check` regenerates everything from `data/raw.json.gz` and fails on any difference |
| `dash/index.html` | The dashboard page (d3 only; the dashboard host allows no other script) |
| `data/raw.json.gz` | The pulse (source of truth, 7,278 rows, 23 repos, 2026-10-26T10:07:10Z; repo-qualified closing and parent references, body references and timeline cross-references) |
| `out/` | Generated outputs (reproducible from the pulse; `manifest.py --check` proves it) |
| `out/apply_log.txt` | Log of the GitHub edits made on 2026-10-26 |

## Run it

```bash
python -m unittest test_taxonomy
python fetch.py --since 2026-08-01 --out data/raw.json          # new pulse (~10 min, GitHub can time out; rerun with --resume)
python report.py --raw data/raw.json --out out
python dash_export.py --raw data/raw.json --out out
gzip -n -c data/raw.json > data/raw.json.gz && python manifest.py && python manifest.py --check
python apply_issues.py --min-confidence strong                   # dry run; add --apply to edit GitHub
```

Windows: `unset GITHUB_TOKEN GH_TOKEN` (or the PowerShell equivalent) before `gh`; set `PYTHONIOENCODING=utf-8` for console output with emoji titles.

## Results at the 10:07 pulse

| | PRs | Issues | All |
|---|---|---|---|
| Titles | 6,652 | 626 | 7,278 |
| Explicit `type(scope)` prefix | 35.0% | 3.5% | 32.3% |
| Lint clean | 29.4% | 3.2% | 27.1% |
| Resolved to type + family | 68.8% | 63.7% | 68.4% |

Largest families: qps, ci-ops, governance, dmaic, cryo-eng, mission-control, mip-3p. The user's five named families are all present: handover, gogreen, jade-devops, watch, p-process.

## Applied on GitHub (2026-10-26, user-approved, strong/explicit only)

Labels added (never removed) and 10 titles rewritten, all verified by read-back:
ABACUS#644, #1736, #1874 (label only), #1885 (bot issue, label only); CODEX#319, #500; cryoplant-project#75, #85, #208, #211, #481; document-organization-system#51.
18 labels were created (`type:*`, `family:*`, `scope:*`). Full log: `out/apply_log.txt`.
Not applied: the remaining 156 open issues whose classification is inferred or none.

## Dashboard

https://claude.ai/artifact/RARdwhuvVk2emp2iCRRhDw (private until shared). Data are attached files, not live: refresh by re-running the scripts, uploading each changed `out/dash/*.json` to the artifact, and pointing its dataset at the new blob (`out/dash/blobs.json` holds current blob ids). Cards: conformance tiles; sort / top-N / histogram range filters; spread stats (keys, mean, median, P90, max, top-5 share, tail share, Gini) as a `levelstats` calculation; count histogram; zoomable family › scope › type map; families; types; type × family matrix; peers in a family; running totals; families per repo; prefix leaderboard; titles drill-down with GitHub links; keyword inventory; unmapped tokens; lint; issue plan with links.

## Crosswalk and dependency graph

17,914 links at the 10:07 pulse (timelines paged) (one per ordered pair, typed by its strongest evidence, every source kept in `evidence`):
10,021 `refs` (PR / issue body references: `#n`, `Repo#n`, `GBOGEB/repo#n`, GitHub URLs; code blocks and HTML comments ignored),
7,030 `xref` (GitHub timeline cross-reference events), 336 `closes` (closing references from both sides, `Closes/Fixes/Resolves`
in a PR body, closing cross-references), 274 `mentions` (title references), 4 `parent`. 1,032 cross-repo; 5,626 inside one family.
Bodies are read only to extract references and are never stored. `out/edges.csv` and the dashboard `edges` dataset carry each
end's family and scope. The dashboard adds a per-family crosswalk, a family-to-family link matrix, a force-directed graph per
family (PR circles, issue squares, nodes open GitHub; link types can be toggled) and the link list.

### Post-assignment of `(none)`

Titles whose own text maps to no family (655) get a **candidate** family voted by the families of everything they link to
(closes and parent weigh 3, title mentions 2, body refs and timeline 1). It is stored as `link_family`, `link_share`,
`link_status` on the `titles` dataset and never overwrites the title's family. Result: 136 clear (top family has at least 60%
of the weight; mostly ci-ops 40, governance 26, qps 22, cryo-eng 12), 328 mixed (links spread over several families:
cross-cutting items), 191 with no linked item that has a family (generic one-off titles such as "add ...", "repeat pass",
"accidental", Copilot setup; no hidden new family among them).

## CI health per family (EVERRED, red / green, checks, DAG / SIPOC, OID)

For every family with more than 10 titles (27 families), from `data/checks.json.gz` (`fetch_checks.py`: per PR the head OID,
the combined check state of its last 10 commits, and every check suite on its head commit, paginated). `ci_census.py` imports
the PAH owners instead of re-implementing them, and offers three lenses:

| Lens | What it measures | Owners used |
|---|---|---|
| **Default branch, per check** (headline) | Each check the family's PRs ran, classed by its default-branch history (STABLE_GREEN, RED_TO_GREEN, FLAKY, GREEN_TO_RED, EVERRED), weighted by 1 + its test jobs | `RED_TRACE_FEDERATION_N8.json`, `cicd_dag.everred_metrics()`, `jade_temple/devops` census N11 (`signals` tests / pytest per job) |
| **PR head, code checks** | Per PR: green when every non-gate check on its last commit passed; test-weighted pass share per family; rank = 95% Wilson lower bound of that share over the family's PRs | always-red gates detected from the data: failed on at least 80% of 20 or more PR heads (28 at the 10:07 pulse, mostly legacy ABACUS DMAIC / CD pipelines and PAH First-Pass Closure) |
| **Combined, incl. gates** | GitHub's single combined state over the last 10 commits, classed with `red_trace.classify()`; one red check makes the commit red | `red_trace.classify()`, `cicd_dag.everred_metrics()` |

Why three: the combined lens alone made almost every family look EVERRED (qps 739 of 1,305 PRs) because a handful of gates
fail on nearly every PR. On the default branch the five federation core repositories have 186 of 340 workflows stable green
(recovery rate 53%; PAH 56 of 78 stable, 1 EVERRED) and 410 test jobs over 17,142 test cases. Per family the default-branch
EVERRED share is 4-19% and the test-weighted code-check pass share 48-92%.

Outputs: `out/ci_family.csv` (all three lenses, rank, newest PR with head OID, main red driver), `out/ci_checks.csv` (per family
and check: outcomes, gate flag, weight, test jobs, default-branch class, DAG node, SIPOC, DMAIC, blob OID), `out/ci_scope.csv`
(owner statistics by scope), `out/ci_gates.csv`, `out/ci_signatures.csv` (PRs that ran the same check set), `out/ci_prs.csv`.
The dashboard legend toggles classes on and off (the rest close up to the left; one class left = a ranked single-class view).

LDAB: `mission-control/federation-atlas/mission_rebuild/ldab_dag_sipoc.py` crosswalks the LDAB graph to SIPOC but records
`native_test_count: None`, so test weights come from the DevOps census. 512 family x check rows bind to a CI/CD DAG node;
the DAG covers pipeline-automation-hub, cryoplant-project, DOCX_RTM_Automation, gg_MATH and yaml-grammar only.

`python manifest.py --check --pah <pipeline-automation-hub checkout>` regenerates the CI outputs and datasets too.

### Review fixes (Codex on cf91a33)

- `fetch.py` pages timeline cross-references past the first 30 (35 items had more; 16,010 events instead of 14,806).
- `fetch_checks.py` pages check suites past the first page (954 PR heads had more than 30; up to 153).
- `fetch.py --resume` only reuses per-repo files of the same run (`data/repos/_run.json`); the pulse keeps the run's start
  time. `fetch_checks.py --resume` only reuses files fetched against the same pulse.
- `manifest.py --check` also verifies every dashboard dataset and the dashboard page against the published hashes.

## Overlap with pipeline-automation-hub #925 / #927 (read before landing)

Two draft PRs opened earlier the same morning build a title taxonomy inside `mission-control/issue_rank/`:
- #927 `feat/issue-rank-recursive-title-taxonomy-20261026`: `title_taxonomy.py` (`parse_title`, `summary`, `associated_families`, schema `jade.title-taxonomy.v1`), wired into `issue_rank.rank()` and `triway_burndown.project()`, AGENTS.md ownership row, CI green on 3.11 / 3.12. **This is the owner** under AGENTS.md L4.
- #925 is an earlier, smaller version of the same idea (overlaps #927).

This work should not land as a second parser. What it adds that #927 lacks, to be merged into the owner:

| This work | #927 equivalent | Reconcile by |
|---|---|---|
| `vocabulary.json` families/scopes/aliases calibrated on 7,278 real titles, incl. cryoplant, ABACUS DMAIC, CODEX scopes | `TOPIC_FAMILIES`, `TECHNICAL_CLUSTERS`, `PROGRAMS` dicts | load the JSON or port the aliases into #927's dicts |
| lead-label parsing (`W327:`, `CBD W4:`, `RFI-QPS-CC-01:`, `MissionControl:`) | `_frontmatter` | add the cases and their tests |
| lossless `suggest_title` + `apply_issues.py` (snapshot-guarded) | none (#927 forbids renames) | separate, owner-approved tool |
| census levels, 30-day trend, median days to close, Gini/tail stats, dashboard | `summary()` rollups per repo / JADE / USER | add the metrics to `summary()`, render from its output |
| recursive inheritance title > label > closing PR > keyword > parent > children | linked family candidates, max two hops, never overwrite | keep #927's stricter rule; add closing-PR evidence |

## Known limits

- Verified on the workstation's Python 3.12 only; code avoids 3.12-only syntax but CI on the repo's declared runtime has not run. Treat as unverified until it does.
- Keyword inference is heuristic: `inferred` rows are guesses; only `explicit` and `strong` were applied.
- Dashboard data are a static copy from the 10:07 pulse.
- Links come from closing references, sub-issue parents, titles, bodies and timeline cross-references. Comments and commit messages are only seen indirectly through timeline events; references to items outside the snapshot (older or other owners) are dropped.
- 9% of titles still map to no family; see `out/keywords.md` "Unmapped" and the dashboard table.
