# Binary flight: scoped source replay

`binary_flight.py` remains the read-only owner for bounded PPTX/PPTM, HTML and SVG observations. It reads bytes, emits structural evidence and leaves admission on HOLD. It does not execute macros, extract archive members to arbitrary paths, fetch external relationships, render a document or transfer engineering authority.

## Partial archive selection

Default operation validates the entire outer member listing against the existing count, path and declared expansion budgets. When an unrelated member cannot be admitted, an operator may explicitly select exact member names in one archive:

```bash
python mission-control/gogreen/binary_flight.py input.zip \
  --member deck.pptx --member drawing.svg --out receipt.json
```

The selection passes through the same member checks. An empty selection, absent member, unsafe selected path, duplicate selected name or multi-archive selection is rejected. The archive-wide entry-count bound always applies. Unselected member payloads are not decompressed or parsed and remain unvalidated; the compressed archive bytes are still streamed for hashing. `coverage.scope`, `unselected_archive_members`, `selected_unhandled_members` and `whole_archive_member_metadata_validated` make the boundary explicit. `whole_archive_validated` stays false because metadata checks and selected parsers do not prove complete container validity. The code does not recursively traverse arbitrary nested archives.

Each outer archive is streamed once into a private compressed-byte snapshot while computing its hash. The parser reads that same snapshot, so even a path replaced and restored during inspection cannot bind replacement members to the original hash. The snapshot spools to a temporary file above 8 MiB to bound memory; selected member payloads alone are decompressed and parsed. A final streamed source hash retains the stricter policy that a persistent source change rejects the run before a receipt can be returned. Object and rejection receipts carry the source archive hash, central-directory member index and hashed member name. Private consumers retain their own original names and source maps; public receipts need not publish them.

Repeated identical `--member` arguments are rejected before conversion to a set, source inspection or output creation. A valid set of distinct names retains the existing selection behavior.

## PPTX and SVG changes

Slide records preserve presentation relationship order and now expose the native slide member, relationship ID and slide ID. Native groups are counted directly; the group-transform qualification remains `NOT_EVALUATED` when groups are present.

The existing `text_sha256` retains its shape-text definition. New `table_text_sha256` / `table_text_chars` and `all_text_sha256` / `all_text_chars` distinguish table text and all DrawingML text within that slide part. `all_text_scope` does not include notes, comments, chart workbooks, raster OCR or rendered text. Existing duplicate-text groups still use the original shape-text hash.

SVG inspection verifies the root rather than treating arbitrary XML as SVG, rejects declarations at parser level across supported XML encodings, counts native elements/IDs, and emits an individual hash-bound receipt. This is XML/structure qualification, not SVG rendering or process-line interpretation.

The historical `parse_success_*` counters are retained with an explicit `PPTX_PPTM_ONLY` scope. `selected_recognized_*` counters cover every selected supported member, including SVG and HTML. Every supported member is represented by either an object receipt or an input-rejection receipt.

## Verification

```bash
python -m unittest discover -s mission-control/gogreen/tests -p 'test_binary_flight*.py'
python mission-control/registry/engine_catalog.py validate
```

Generic tests exercise first-red cases, relationship identity, single-group counting, table text scope, SVG masquerading, encoded XML declarations, held unselected members, fail-closed selected admission, persistent source changes, restored-path replacement races, duplicate CLI selections and unchanged source bytes. Private real-source receipts belong to the consuming project and are not bundled into this public module.
