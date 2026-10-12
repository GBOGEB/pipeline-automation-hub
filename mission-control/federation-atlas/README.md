# CODE PURPLE Federation Method Atlas (v0.1)

Owned by `GBOGEB/pipeline-automation-hub` Mission Control. A read-only projection, not another QPS engineering authority, release writer, or Pages publisher.

## Bounded run / task

Workflow: `.github/workflows/code-purple-method-atlas.yml`. Runs tests and emits downloadable `index.html`, `federation.svg` and `metrics.json` on PR, relevant master update, or manual method-pulse dispatch. No automatic merge, issue mutation, web publication, or engineering-state promotion.

Stages: SIPOC, DAG, DMAIC, 3P*, conditional MIP, measured PCA, BT/backtesting and LDAB. The canonical Mission Control method registry remains `mission-control/v2/MC_METHOD_PROFILE_REGISTRY_v1.json`. SIPOC/DAG/PCA/BT/LDAB are observability projections, not newly admitted canonical stage lifecycles.

`ATLAS_GRAPH_v1.yaml` is the graphical single source for node coordinates, labels and typed edges. `build_atlas.py` renders HTML/SVG/JSON without raster assets; the generated image is not itself SSOT. Source snapshot timestamps are visible, so a green check on an older source cannot be mistaken for current CI.

Doctor/REX: only observed application red, >0 executed steps, and an exact 40-digit SHA create an advisory DOCTOR_REX_LOOKUP. 0-step red goes to DOCKMASTER. Owner-external goes to RETURN_OWNER. No regression or source repair is automatically claimed. Its next integration is historical REX lookup keyed by root-family, code signature, source context and subsequent measured repeat evidence.

## Hierarchy and links

Mission -> Sprint -> Wave -> Pulse -> Run, plus cohort -> repo -> PR -> checks/receipts. Existing dashboard and source links are in `METHOD_OBSERVABILITY_v1.json`, with hosted Pages entrypoints marked `HOSTED_CANDIDATE` until a fresh Pages URL/content-identity readback. Generated artifact can be consumed by an existing governed Pages publisher; this PR MUST NOT independently enable another publisher.

Future connector: bind actual GitHub PR/check events, workflow run evidence, exact SHA and optional runner/Kubernetes telemetry; expose missing fields as UNKNOWN. Never substitute forecast output for a gate. Feed completed `CONTROL` receipts to the next iteration; preserve HOLD/RETURN/DEFER predicates.

## QA

`python -m pip install pyyaml==6.0.3 && python -m unittest discover -s mission-control/federation-atlas -p 'test_*.py' -v`

`python mission-control/federation-atlas/build_atlas.py --out /tmp/code-purple-atlas --method DMAIC --stage MEASURE`

Admission requires exact PR-head CI and reviews, then governed merge and exact-main readback. Artifact generation is not publication.
