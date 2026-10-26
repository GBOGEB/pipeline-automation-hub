# Portfolio title taxonomy explorer — local review surface

The **only** taxonomy parser and vocabulary owner is
mission-control/issue_rank/title_taxonomy.py (merged PR #927).
This viewer consumes the existing issue_rank.json produced by issue_rank.py.
It does not define a new owner, authoritatively inherit families,
rewrite GitHub work items or merge PRs.

## Local static page

    python mission-control/issue_rank/taxonomy_explorer.py \
      --model /OWNER_PRIVATE/out/jade/issue_rank.json \
      --out /OWNER_PRIVATE/out/jade/taxonomy_explorer.html

Default output is PUBLIC_PROJECTION. Private issue/PR rows, repository names,
source heads, titles, derived cluster membership and item links are excluded
at the model boundary BEFORE HTML rendering. The page has no network calls,
external scripts, privileged tokens or write actions.

The optional --private-local switch may be used only in owner-controlled
private storage. NEVER publish PRIVATE_LOCAL_ONLY HTML or a raw model to Pages.

## Interactive read-only filters

The standalone HTML contains independently filterable:
- Repository, Issue vs PullRequest, primary action type
- Programme/topic families, technical clusters, wave/cohort codes
- Classification state, free text
- Peer counts per repository (baseline and visible-after-filter)

Scope, title and graph path are observational attributes; no semantic
classification is a completed engineering or security decision. The page
shows raw source titles only for visible permitted public items. Every item
has one primary action; multi-topic and multi-cluster membership is
nonadditive, so do NOT sum matching facet counts as work items.

## Proof contract

Native Python 3.11/3.12 tests enforce HTML/attribute/script escaping;
an untrusted source URL can never become a javascript: anchor; canonical
GitHub item URLs are generated from validated identities; private rows
and even private repository names must not appear in public HTML.
Wrong source SHA, wrong taxonomy version, duplicated/cross-repo identities,
and privacy mismatches must fail closed.

Native source-head tests do not replace actual browser screenshot QA.
The generated reader page is a LOCAL review surface, not an authoritative
GitHub Pages publication, source SSOT, runtime certificate or release.
Use a separate governed browser/Playwright acceptance before publication.
