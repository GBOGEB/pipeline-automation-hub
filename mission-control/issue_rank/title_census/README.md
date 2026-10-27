# Title census: artefacts and handover (data, not a code path)

Evidence and vocabulary from a full PR and issue title census of 23 GBOGEB source repositories
(pulse 2026-10-26T10:07:10Z, 7,278 titles, 17,914 PR/issue links). It feeds the title parser owned by
[`../title_taxonomy.py`](../title_taxonomy.py) (#927, schema `jade.title-taxonomy.v1`).

**Nothing here is imported or run by `issue_rank.py`, `triway_burndown.py` or CI.** There is no second
parser in the code path (AGENTS.md L4). The census tool's source is kept only as a zipped reference so
the handover is lossless; it is to be reconciled into the owner, not run from here.

## Start here

1. [RECONCILIATION.md](RECONCILIATION.md): what this census adds to `title_taxonomy.py`, with the scope and alias gaps measured against it.
2. [HANDOVER.md](HANDOVER.md): full engineering handover (the paths in it refer to the unpacked tool; see the layout table below).
3. [RESTART.md](RESTART.md): drop-in prompt to resume in a new session.

## Layout

| Path | What | Notes |
|---|---|---|
| `vocabulary.json` | 12 types, 26 families, scopes and aliases, 13 qualifier classes, type keywords, label map | Calibrated on the census; the main input to reconciliation |
| `dashboard/index.html` | Page of the published dashboard (d3 only) | Live copy: https://claude.ai/artifact/RARdwhuvVk2emp2iCRRhDw (private until shared) |
| `data/raw.json.gz` | The pulse: every PR and issue title, state, dates, labels, parent, closing references, body references and timeline cross-references (bodies themselves not stored), per-repo head SHA | Source of truth |
| `outputs/*.gz`, `outputs/*.md`, `outputs/*.json`, `outputs/conformance.csv` | Census outputs (`census.json`, `rows.csv`, `stats.csv`, `timeseries.csv`), keyword inventory, issue plan, gap table | `out/` in the handover; large files gzipped |
| `outputs/edges.csv.gz` | PR / issue links (closes, parent, title mentions, body refs, timeline cross-references; one per pair, merged evidence) with each end's family and scope | Counts only; ranking stays in `issue_rank.py` |
| `data/checks.json.gz`, `outputs/ci_*.csv(.gz)` | Per-PR CI evidence and the per-family CI view: default branch per check (test-weighted), PR-head code checks with gates apart and a Wilson-bound rank, combined state; owner statistics by scope; always-red gates; checks with SIPOC / DAG / OID; activity signatures | Built on `red_trace.classify()` and `cicd_dag.everred_metrics()` |
| `outputs/dash/*.json.gz`, `outputs/dash/blobs.json` | The dashboard's attached datasets and their blob ids | `out/dash/` in the handover |
| `outputs/apply_log.txt` | The GitHub issue edits made on 2026-10-26 (12 issues labelled, 10 retitled, user-approved) | |
| `MANIFEST.json` | sha256 of every output (uncompressed) and dataset, per-repo head SHAs | |
| `reference/title_taxonomy_src.zip` | Census tool source: `taxonomy.py`, `test_taxonomy.py`, `graph.py`, `test_graph.py`, `fetch.py`, `fetch_checks.py`, `test_fetch.py`, `ci_census.py`, `report.py`, `dash_export.py`, `apply_issues.py`, `manifest.py` | Reference only |

## Reproduce (outside the repo)

```bash
mkdir /tmp/tc && cd /tmp/tc
unzip <repo>/mission-control/issue_rank/title_census/reference/title_taxonomy_src.zip
cp <repo>/mission-control/issue_rank/title_census/{vocabulary.json,MANIFEST.json} .
mkdir data dash && cp <repo>/mission-control/issue_rank/title_census/data/*.json.gz data/
cp <repo>/mission-control/issue_rank/title_census/dashboard/index.html dash/   # the check verifies the page too
python -m unittest test_fetch test_taxonomy test_graph
python manifest.py --check --pah <repo>   # regenerates every output, CI view included; prints "reproducible"
```

Verified on Python 3.12 on the workstation only; unverified on the repository's CI runtime.
