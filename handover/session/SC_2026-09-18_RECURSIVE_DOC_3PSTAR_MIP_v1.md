# Recursive DOC / KE_BLOCK — lossless 3P* + MIP handover

## Authority

Primary repository: `GBOGEB/pipeline-automation-hub`  
Tracking issue: #268  
Authority transfer: false  
Formal credit delta: 0

## Delivered slice

`MASTER -> KE_BLOCKS -> CANDIDATE -> cd.json -> CD gate`

The implementation is intentionally small and stdlib-only. It preserves text exactly, gives every block a stable sequence and SHA-256, emits a machine-readable candidate descriptor, and fails closed if the candidate is modified after generation.

## Proof

Local proof executed before publication:

```text
python -m unittest recursive_doc_engine.tests.test_roundtrip -v
3 tests PASS
```

The same test is bound to repository CI in `.github/workflows/recursive-doc-ke-gate.yml`.

## Restart

1. Read `recursive_doc_engine/README.md`.
2. Read `recursive_doc_engine/control/RECURSIVE_DOC_3PSTAR_MIP_CONTROL_v1.json`.
3. Re-run the unit tests.
4. Run one real MASTER through `recursive_doc_engine.engine`.
5. Run `recursive_doc_engine.cd_gate`.
6. Only then expand into Office round-trip adapters, dashboards, index/ranking views, or richer KE_BLOCK semantics.

## Next ranked expansion

1. DOCX semantic adapter preserving heading/list identity.
2. XLSX/PPTX artefact adapters with outward-render QA.
3. `index.json` / `ranking_index.json` generator from actual runs.
4. VS Code task surface.
5. Offline pack manifest for multi-artefact regeneration.

Do not skip retest when scaling input size or adding a new artefact class.
