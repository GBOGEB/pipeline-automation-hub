# N1 — CI naming and title-taxonomy crosswalk (shadow)

**Scope:** Read-only display aliases for B00–B12 from the single canonical parser in [title_taxonomy.py](../mission-control/issue_rank/title_taxonomy.py). This adapter does not introduce another PR-title grammar or check authority.

## Run and expected classification

```bash
python mission-control/jade_temple/devops/ci_bundle_title_crosswalk.py --title "refactor(ci/B02): clarify unit tests"
python -m unittest discover -s mission-control/jade_temple/devops/tests -p 'test_ci_bundle_title_crosswalk.py' -v
```

A bundle identifier must appear explicitly in the conventional title **prefix** to become an advisory bundle candidate. A body mention is not enough. Output includes the existing canonical action family, declared scope tokens, optional display aliases and `authority=ADVISORY_ONLY`. No test existence, test pass, engineering acceptance or merge status is inferred.

## Compatibility and next actions

- Do not rename workflow names, job/check contexts, GOGREEN required-gate population, rulesets or branch protection in this PR.
- Before any future migration, create a reversible old-name-to-display-alias crosswalk, cross-check the current `ADMISSION.json` and generated recheck workflow names and preserve the three currently required contexts.
- No new metric owner; canonical parser, workflow parser and Actions metrics remain unchanged.
- This is an N1 sibling of N2, both based on N0 source head `1048fc4f7074e06a2118e7705d15c98383e96bf9`; verify independently and integrate only after exact-head review.


## Legacy-namespace collision and N1 regression

The merged [#992 source-of-truth CI spine](ci-spine/README.md) uses the legacy namespace `ci-spine:bundle:B00…B09`. Candidate B00–B12 in PR #997 use **a different namespace**, `jade.devops.ci_candidate:B00…B12`. Identical short labels imply **no equivalence**. In particular, the spine's B07 required fan-in is not the candidate B07 scientific-math family.

The adapter now outputs `candidate_namespace`, `candidate_urns`, `legacy_spine_namespace` and `legacy_label_equivalent=false`, validates the advisory catalog schema, and rejects promoted/duplicate/legacy catalogs. Existing short ID aliases remain display-only.

**Native testflight:** [`ci-bundle-title-shadow.yml`](../.github/workflows/ci-bundle-title-shadow.yml) is an additive, read-only caller of the **existing JADE reusable CI**; it runs the 14 N1 tests with a `min-tests=14` guard, SHA-bound checkout and CI receipt. It does not add a canonical metric owner or an enforced status. Its native exact-head result must be checked separately and remains pending at authoring time. Consider consolidating this caller with N2's shadow workflow during controlled landing to avoid permanent duplicate CI minutes.
