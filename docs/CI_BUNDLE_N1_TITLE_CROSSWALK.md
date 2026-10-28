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
