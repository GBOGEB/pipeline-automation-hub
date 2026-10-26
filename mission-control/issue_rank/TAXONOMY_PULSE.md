# Taxonomy pulse — governed N / N+1 telemetry

Owner: mission-control/issue_rank/title_taxonomy.py (merged #927).
Reader: mission-control/issue_rank/taxonomy_pulse.py.
This module is a read-only projection, not a second taxonomy parser or new
closure/acceptance authority. The earlier #925 draft is superseded, and #939
provides the canonical fail-closed alias repair.

## Build on locally retained source-pinned rank models

Run the existing ranking engine on the intended JADE or USER scope first.
Its issue_rank.json keeps source SHA per repository and raw issue/PR identities.
Then run:

    python mission-control/issue_rank/taxonomy_pulse.py \
      --current /PRIVATE/20261026_N1/issue_rank.json \
      --previous /PRIVATE/20261025_N0/issue_rank.json \
      --json-out /PRIVATE/20261026_N1/taxonomy_pulse.json \
      --csv-out /PRIVATE/20261026_N1/taxonomy_pulse.csv \
      --parser-sha <EXACT_40_HEX_CHECKOUT_SHA>

The default is PUBLIC_PROJECTION: private repo titles, private source identifiers,
private heads, and all free-text issue actions are excluded from the result.
The input issue_rank.json may itself remain private: never commit raw snapshots
or generated owner-private reports into this public Git repository.

Only if running inside owner-controlled private storage may --private-local be used.
Do not publish --private-local outputs, including their numeric/derived facets.

## Denominator and source contract

- Validate every source head is full 40-hex; parser_sha is optional but
  missing pin is explicitly marked UNKNOWN, not claimed exact.
- Validate each row has a unique repository#number identity, valid Issue or
  PullRequest type, matching repo privacy and the canonical taxonomy schema.
- One item contributes exactly one primary family and one four-part composite
  to each relevant scope (repository, JADE and USER). Never add JADE to USER.
- Theme/cluster/code memberships overlap. Their counts are NONADDITIVE.
- A composite (action/scope/family/cluster) is a deterministic advisory
  projection of canonical facets, not a rewrite of the prefix path:
  fix(jade devops): census fails closed -> fix/jade-devops/census/fail-closed.
- Compare N against N+1 only if the visible repository population is identical,
  timestamps are chronologically valid and the taxonomy schema is valid.
- New, absent, persisting and reclassified are distinct. Absent from the open
  snapshot is NOT necessarily closed or merged. A changed title is NOT a
  verified root-resolution event.
- A changing parser implementation may reclassify items even when titles do
  not change. Bind exact parser checkout SHA per pulse and retain that as a
  limitation when interpreting moves.
- Projected heads and issue queries form a NON_ATOMIC API snapshot, not a
  transactional GitHub server-wide read.
- Never automatically rename issues, mutate labels, edit rules, waive review,
  grant root closure, or grant release/engineering credit.

## Control and admission

Native unit tests run in the existing issue-rank matrix on Python 3.11/3.12.
Private-redaction negatives, wrong SHA/schema, duplicate identities,
reversed time, cohort drift, type changes, nonadditive facets and
semantic root-closure withholding are mandatory. No release or Pages
workflow is enabled by this PR.

Future: append these pulse records to the existing chained issue-rank ledger
and render a filtered viewer from local snapshots. No duplicate ledger writer.
