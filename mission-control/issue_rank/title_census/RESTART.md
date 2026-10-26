# Drop-in restart prompt

Paste the block below into a new Claude Code session opened in the folder that holds `title_taxonomy/` (or in the pipeline-automation-hub checkout once it has landed there).

```text
Resume the GBOGEB title-taxonomy work. Read title_taxonomy/HANDOVER.md first, then MANIFEST.json.

State on 2026-10-26:
- title_taxonomy/ parses PR and issue titles into type(scope qualifier): subject, with levels
  type family > type and family > scope > qualifier, prefix = type(scope). Vocabulary in vocabulary.json
  (12 types, 26 families, 13 qualifier classes). 18 unit tests pass (python -m unittest test_taxonomy).
- Pulse 2026-10-26T08:31:05Z, 22 GBOGEB repos, 7,273 titles, in data/raw.json.gz.
  `python manifest.py --check` must print "reproducible".
- Dashboard: https://claude.ai/artifact/RARdwhuvVk2emp2iCRRhDw (Dashboard type, attached JSON datasets,
  blob ids in out/dash/blobs.json; page source dash/index.html).
- Applied on GitHub with the user's approval: labels on 12 open issues, 10 retitles (out/apply_log.txt).
  156 lower-confidence plan items NOT applied; do not apply them without asking.
- Overlap: pipeline-automation-hub draft PRs #927 (owner of mission-control/issue_rank/title_taxonomy.py)
  and #925 already implement a title taxonomy. AGENTS.md L4: one owner per metric. Do not land a second
  parser; reconcile into #927 per the table in HANDOVER.md, or follow the route the user chose.

Rules: unset GITHUB_TOKEN GH_TOKEN before gh; re-fetch before acting; push branches early; draft PRs say
"Do not merge unless green"; never merge on red; verify on the repo's declared Python, not only 3.12.

Next steps, in order:
1. git fetch; check #925/#927 state (merged? changed?) before doing anything.
2. <the landing route the user picked>
3. Re-run fetch.py / report.py / dash_export.py / manifest.py and refresh the dashboard datasets.
```
