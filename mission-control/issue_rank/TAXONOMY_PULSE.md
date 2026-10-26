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

## Integrated single-writer output and chain (N+2)

The existing `issue_rank.py run` / `rank` path now emits `taxonomy_pulse.json`
and `taxonomy_pulse.csv` alongside its original `issue_rank.json/.csv/.html`
and `delta.json`, using the SAME output hash manifest / JSONL ledger writer.
There is no competing scheduled trigger, webhook or artifact authority.

    python mission-control/issue_rank/issue_rank.py run --scope jade       --redact-private --parser-sha <CURRENT_EXACT_40_HEX_SHA>       --previous-parser-sha <PREVIOUS_EXACT_40_HEX_SHA>

N and N+1 both contribute long-form CSV rows keyed by
`observed_at, wave, scope, facet_dimension, facet`. Each carries its
own denominator; never add counts from different waves or JADE + USER.
Zero-item repositories are retained with an explicit zero denominator.
For an unmatched parser producer SHA, classification-change attribution is
WITHHELD, not a validated title rename. Repo-population drift prevents matched
current-versus-previous delta claims. The publicly safe projection excludes
private rows even when the existing local rank model retains them.

To visualize locally, use the disjoint `taxonomy_explorer.py` producer in
PR #941, which operates read-only on the same rank model and never needs
the taxonomy-pulse output. Before any Pages publication, perform owner
privacy review plus browser/Playwright visual QA. This integration creates
no automatic publication route.
