# GoGREEN G10 — Directed SVG and DAG visual QA as a native test surface

This is an **independent path-disjoint lane** from G9 and a read-only consumer of G7's canonical `success_graph/runner_telemetry.py` SIPOC output. No source-owned root, BD, runner scheduler, branch settings or telemetry SSOT is duplicated.

## Actual capabilities

- Validate source SIPOC: exactly one canonical S→I→P_SOURCE→O→C spine, registered P_REVERSE/P_REX nodes, typed CAP_* atoms with provenance, unique directed endpoints, no cycles and all nodes reachable from Supplier S.
- Render source-bound accessible SVG with **15 nodes and 24 directed arrows**, fixed SIPOC role colors and per-edge binding colors. `OBSERVED`: teal 3.0 px, `DECLARED`: amber 1.6 px. Markers encode direction, not decorative line weight. Each node has full title text, edge/node keyboard focus, and explicit source/target/type metadata.
- Generate self-contained HTML viewer with Zoom/Reset/Fit controls, no external scripts/network fetches or hidden GitHub source mutation. Inputs are escaped to stop unsafe injected SVG markup.
- Emit JSON visual-QA dimensions/counts, canonical graph input, SVG and HTML, SHA256 manifest and native run/attempt/source receipts.

## Quality limits

The machine can verify structural and static rendering invariants, but **does not falsely claim a Playwright or actual human visual screenshot inspection**. `browser_visual_inspection=null` remains explicit. A later cross-platform Playwright pulse can compare SVG snapshots, viewport variants and label occlusion without giving a graph visualization independent admission authority.

## Native tests

`python -m unittest discover -s mission-control/gogreen/graph_quality/tests -p test_graph_quality.py -v`

50 positive/adversarial test methods validate arrow color and line weights, zoom/accessibility, HTML/SVG escaping, cycle, dangling edge, disconnected capability, false authority, invalid owner, bad output, reproducibility, source digest, and CLI execution. Native G10 CI enforces module-scoped `coverage.py==7.13.3`, >=85% statements and >=80% branches, with exact eligible numerators and denominators, not whole repository coverage.

## Next feedback pulse

Use a visual renderer (Playwright screenshot comparisons) when the native SVG/HTML is genuinely available as downloaded CI artifacts. Classify each mismatch as CONTENT, GEOMETRY, LABEL, STROKE, ARROW or ZOOM; route repaired source to single owner, then rerun G10 tests at the new exact head. Do not pass a static visual snapshot as mathematical correctness or QPS engineering acceptance.

**Status:** no merge authorization, no new REX root closure, no model-derived safety exception.
