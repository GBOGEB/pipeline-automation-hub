# W286/W287 parent closure receipt — IDE/MCP/Jupyter runtime

**Child repository:** `GBOGEB/codespaces-jupyter`  
**Original child PR:** #3  
**Repair child PR:** #4  
**Repair exact head:** `e3295e67a442beee7e7102c33275cddb8f621538`  
**Repair merge:** `30e537298de8a25a78e162be590d1d5763641147`  
**Parent base:** `20e3c7e233c6b346f0b2577c9e4c50013c839a20`  
**Authority transfer:** false  
**Formal / engineering credit delta:** 0 / 0

## Historical correction / supersession

The earlier parent receipt in PR #274 described the double-run notebook probe as
a materialized surface while the first workflow was still queued. Preserve that
statement as historical wording only; it was not runtime proof at that time.

The first admitted child run `35360464702` later executed real steps and failed
before notebook execution because `torchvision==0.21.0` required
`torch==2.6.0` while the repository pinned `torch==2.7.1`.

Repair PR #4 addressed that dependency defect and the Codex proof-integrity
findings without claiming engineering authority.

## Exact-head proof

Fresh run `35372777025`, job `105690401624`, executed successfully against
exact child head `e3295e67a442beee7e7102c33275cddb8f621538`.

Observed proof:
- runner admitted and all workflow steps completed successfully;
- exact candidate SHA checked out, not the synthetic PR merge ref;
- source tree clean before execution: true;
- run 1 executed code cells: 2;
- run 2 executed code cells: 2;
- all-MIME canonical output digest equal:
  `ca07a3ff2cfe6f65c1bf7df8ead95413b68cc50a28484302f47a8787695c0fd6`;
- receipt status: `PASS_REPRODUCIBLE_GT0_CELLS`;
- artifact ID: `10559550253`;
- artifact ZIP SHA-256:
  `82daa0df32c4b12558779f870650a2c934d4e56875bd703e1654d6003bf18b2d`.

## Method closure

- 3P* Refresh / Probe / Rank: PASS
- MIP Modernize / Innovate / Perpetuate: PASS
- 3PC Prepare: PASS
- 3PC Prove: PASS_EXACT_HEAD
- 3PC Commit: PASS_CHILD_PR4_MERGED
- 3P3: not advanced; no need to broaden this slice

## Operator re-entry

For an existing local clone after this closure:

```bash
git switch main
make sync
make scoopo
make probe
```

For a clean machine, clone
`https://github.com/GBOGEB/codespaces-jupyter.git` first.

Notebook execution, MCP mutation, parent receipt status, and CI success remain
tooling/runtime evidence only and do not create engineering or domain-validation
authority.
