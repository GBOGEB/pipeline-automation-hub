# Three-view Issue Expedition / DoD-DoV plan

This is an additive read-only consumer of Mission Control #308 (issue expedition), #324 (measured PCA/BT), #372 (root and proof lifecycle), #604 (evidence graph), QPS #481 and the canonical gg_MATH provider. It is NOT a new issue SSOT.

## Three views and fourth owner-review ordering

1. Golden thread = oldest created issue first. Oldest does not mean executable.
2. Mycelium = newest created issue first. This is an issue intake view, not the CODEX workflow run historian.
3. Graph = most dependent candidate issues, then undirected textual association degree. Text mentions are NONCAUSAL.
4. Owner-review = labelled P0..P4 first, then candidate dependents, linked open PRs, checkbox-only near-finished signal and age. Unknown priority sorts last. Never confuse this advisory ordering with PCA or Bradley-Terry inference.

DoD and DoV are separated by explicit source headings. Checked counts are SELF-REPORTED and not accepted. An absent checklist is null, not 0/0 and not 0%. Each record includes complete steps, source body digest, per-repo/global ordering, open PR overlap and out-of-scope references. Formal engineering, merge and owner acceptance stay UNKNOWN/HOLD.

## Replay/validation

Run from root with:

    python -m unittest discover -s mission-control/qps-triage-ultra/issue-expedition -p test_triway_burndown.py -v

    python mission-control/qps-triage-ultra/issue-expedition/triway_burndown.py --github --out triway-private.json --csv triway-private.csv

Requires GitHub token for private repos. Alternative: --input census-private.json. Add --previous matched-prior-projection.json for noncausal issue identity deltas. Never commit raw full bodies: private owner material may be present. GitHub REST defaults to GET only; API calls are bounded to 20 pages each; missing timestamps, SHA and denominators fail closed.

## N+2 parser (this pulse)

`checklist()` and `references()` now own every parsing rule the issue ranking needs, so
`mission-control/issue_rank/issue_rank.py` can import them instead of keeping its own (AGENTS.md L4).
The change is additive: existing keys and results stay.

- Sections: DoD, DoV, STEPS, OTHER. Each item records its `basis`: `EXPLICIT_HEADING` (the original
  DoD/DoV rule), `SYNONYM_HEADING` or `INLINE_LABEL` (`- [ ] DoD: ...`). The synonyms ("Done when",
  "Acceptance", "Closure predicate", "Verification", "Steps", ...) were calibrated on the 168 open
  QPS/ABACUS/CODEX/hub issues of 2026-10-26. A strict consumer keeps only EXPLICIT and INLINE_LABEL.
- Bold-line headings, `+` and numbered lists, and blockquoted items are parsed. Fences and HTML comments
  are skipped. `[~]`, `[-]` and fully struck-through items are `withdrawn` and never counted.
- Plain bullets and prose paragraphs under a DoD/DoV/STEPS heading are `declared`, counted as `untracked`,
  never as done. A checklist still has progress `null` when it has no live checkbox.
- References: issue and pull URLs, `GBOGEB/repo#N`, federation shorthand (`QPS #N`, `ABACUS PR #N`,
  `hub #N`, `Mission Control #N`), chained `/#N` and `/PR#N`, and bare `#N`. Each row carries `repo` and
  `number`. A keyword binds to the next reference only. A run joined by commas or "and" keeps its head's
  kind, and a negation keeps a reference textual. The new candidate kinds are `DECLARED_BLOCKS_CANDIDATE`
  (reversed in `project()`), `DECLARED_PARENT_CANDIDATE`, `DECLARED_SUCCESSOR` (the target replaces this),
  `DECLARED_PREDECESSOR` (this replaces the target), `DECLARED_DUPLICATE_OF` and `DECLARED_CHILD_CANDIDATE`
  (a live checklist item that names an issue, with `ticked`).
- `parked_intent()` reads the `<!-- parked-intent:v1 {...} -->` marker. `project()` adds `Steps` and
  `parked_intent` to each issue.

Replay on the 168 open issue bodies of 2026-10-26 (counts of issues, except where marked):

| Measure | before | after |
|---|---:|---:|
| Checkbox items (all sections) | 346 | 346 |
| Measurable DoD (live checkbox) | 7 | 13 (strict: 7) |
| Measurable DoV | 1 | 1 |
| DoD declared (checkbox, bullet, prose or heading) | n/a | 78 |
| DoV declared | n/a | 22 |
| References | 499 | 552 |
| Typed references (not text association) | 0 | 75 |

Only 13 of 168 issues have a measurable DoD and 1 has a measurable DoV. Converting declared criteria
into checkboxes is the largest single lever on measurable burndown. That edits issues, so the owner
decides.

## Next pulses

N+1: native source-head tests, concurrency/auth 403/429, pagination boundary, review and exact-head CI.
N+2: source-bound explicit blocker/supersession edges, cycle handling, PR review/run evidence and immutable progress receipts.
N+3: integrate registered JADE Top21 and global USER cohorts rather than claiming five repos represent the full estate; gg_MATH PCA/BT must remain withheld until comparable measured features/pairs and identifiable fits exist.
N+4: independent owner DoD/DoV sign-off, semantic root deduplication, and matched same-population time-series burndown.

Governance invariant: MERGE_ADMISSION=HOLD; authority_transfer=false; formal_credit_delta=0. No ruleset/issue mutation, owner acceptance or Pages publication authorized here.
