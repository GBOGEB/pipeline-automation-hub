# Recursive Build 3P* -> MIP lossless handover — 2026-09-18

## Mission

Rehabilitate the historical recursive-build surface without creating a second QPS/document truth authority.

## Authority anchor

- repo: `GBOGEB/pipeline-automation-hub`
- starting master: `b3a7df1f7aa24765c243eb282dca58d3c9ea3668`
- tracking issue: #278
- authority transfer: false

## Burned sequence

`3PR Refresh -> Probe -> Rank -> MIP Modernize -> Innovate -> Perpetuate`

### 3PR disposition

First-red: `RECURSIVE_BUILD_NOT_REPRODUCIBLE_OR_LINEAGE_COMPLETE`.

### MIP result

- Modernize: canonical portable deterministic master engine added.
- Innovate: transparent bounded ranking + machine/human indexes added.
- Perpetuate: compatibility shim, tests, CI, VS Code/Ariana optional tasking, architecture note, and durable receipts added.

## Canonical files

1. `scripts/Recursive_Build_Master.py`
2. `scripts/recursive_build.py` (compatibility)
3. `tests/test_recursive_build_master.py`
4. `.github/workflows/recursive-build.yml`
5. `.vscode/tasks.json`
6. `docs/recursive_build/ARCHITECTURE.md`

## Runtime contract

```bash
SOURCE_DATE_EPOCH=<unix-seconds> python scripts/Recursive_Build_Master.py --outputs-dir app/public/outputs
python -m unittest -v tests.test_recursive_build_master
```

## Stop / restart rule

Do not add GUI prompts to CI. If local Tkinter is later added, it must remain a thin caller of the canonical CLI.

Do not treat relevance score as engineering importance. Do not promote metadata-only references into document truth.

Restart from issue #278 and the PR created from branch `feature/recursive-build-3pstar-mip-20260918`.
