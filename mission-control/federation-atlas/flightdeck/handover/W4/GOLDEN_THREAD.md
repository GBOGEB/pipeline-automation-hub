# W4 Golden Thread — truth-bearing history and new root proposal

| Pulse | Exact SHA / artifact | Evidence | Admission |
|---|---|---|---|
| W1 | Source PR [#537](https://github.com/GBOGEB/pipeline-automation-hub/pull/537) | Merged W1/W2 Python/SSOT, historical local output | SOURCE IMPLEMENTED |
| W2 | Frozen combined ZIP in `parents/` | Local 42 tests and generated HTML, SVG, XLSX, DOCX, PPTX, PDF | LOCAL QA, not Pages |
| W3 source | PR [#541](https://github.com/GBOGEB/pipeline-automation-hub/pull/541), original PR head `077391d69e31510c0f40b148e8476480e7e4b295` | W3 Atlas integrated, but exact-head native workflow RED | NOT VERIFIED |
| W3 historical local | Source `f9f7b0101426b96ad3e9f701cce80a1dddcb172d` in frozen parent | 42 local tests; 99.6337% line / 98.3051% branch on focused Flight Deck only; ten hashed output files | LOCAL_REPRODUCIBILITY |
| W4 repair | [Branch `d2ec6e0df8f5edf178a1225b79c687072479d3eb`](https://github.com/GBOGEB/pipeline-automation-hub/tree/d2ec6e0df8f5edf178a1225b79c687072479d3eb) | 2 root-specific false-red repairs + N+2 stage/nav restoration + root register | IMPLEMENTED, native pending |
| W4 handover | This immutable package (external SHA in release receipt) | 4 exact-byte parents, 14 proposed BD items, 36 evidence leaves, 5 historical anchors, schema/DAG/HTML | LOCAL QA only |

## Evidence manifest versus PR source

A GitHub PR preserves **tracked source files** and commit history. A successful workflow uploads *derived* archives with retention and an exact-head reference. Generated Word/Excel/PowerPoint/PDF need not be committed; they must remain reproducible from controlled source, with a generator receipt, SHA-256 manifest and durable custody. A source-controlled Mermaid `.mmd` and JSON Schema can be reviewed via PR; their HTML/SVG versions are renderings, not independent engineering sources. Corporate originals remain unchanged in external controlled-document storage, referenced by ID/version/hash and release approval when available.

## Recursive session boundary

Existing PR [#540](https://github.com/GBOGEB/pipeline-automation-hub/pull/540) implemented the controlled intake adapter. Its fixture has just two manually reconstructed intents, so **no actual platform transcript completeness** or messages/timestamps can be claimed. The next sanitized intent is proposed, NOT appended. Prior ledger hash must be independently retrieved and validated first.

## Historical observed native blockers

* W3 Atlas [run 38739254875](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739254875) and [run 38739428503](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739428503): 87 tests, one false-positive text assertion, first-red before full Flight Deck.
* Session Hook [run 38739313365](https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/38739313365): 19/19 internal tests PASS, generated HTML title expectation false-red, no uploaded valid session receipt.
* GitHub `master` reports `protected=false` and no active repository rulesets. Native red and effective protection are independent non-compensating HOLDs.

## Release/append contract

New pulse N+1 must preserve old parent ZIP's SHA-256 and serialized content hash registry. Its own manifest hashes every new or retained file but not itself; a separate release receipt binds final ZIP. A verified archive is not a formal source acceptance. Root resolved requires an attributable native producer and native exact-main recurrence; repair-code commit alone is not root closure.