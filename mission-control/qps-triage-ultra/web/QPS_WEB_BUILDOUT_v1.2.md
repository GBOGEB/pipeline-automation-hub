# QPS Web Buildout v1.2

Status: IMPLEMENTING
Owner: H4_QPS_TRIAGE
Purpose: Bind HTML/CSS/Jekyll publication into QPS triage as an evidence-preserving static surface, without creating a second operational application.

## Architecture

- Operational cockpit: existing Next/React application.
- Static publication/evidence surface: Jekyll-generated HTML.
- SSOT remains MissionControl JSON/YAML/receipts/REX.
- Jekyll consumes generated/canonical data and must not become an independent status source.

## Eight implementation items

1. Jekyll is a renderer, never SSOT.
2. HTML carries machine-verifiable release/source/schema/evidence identity.
3. QPS-UI/CSS v1.2 semantic design tokens are defined and accessibility-safe.
4. Next and Jekyll consume one shared token vocabulary.
5. Static views cover fleet, topology, crew, execution, REX, historian, evidence economics, and PCA/BT.
6. Mermaid/graph sources are pre-rendered to durable SVG where canonical evidence is required; CDN-only rendering is forbidden for governed evidence.
7. Jekyll publication executes J1-J6 gates: source, generate, structure, visual, identity, repeat.
8. Browser support is explicit: modern browser operational UI plus static semantic HTML fallback; IE11 is not an operational Next.js target.

## DoV

Promotion to CONTROL requires:

- static build succeeds;
- generated pages contain release_id, source_sha, schema_version and evidence_state;
- no hand-maintained mission state in Jekyll templates;
- token contract validates;
- required static views are represented;
- internal links and assets validate;
- exact release identity can be compared with JSON/PDF/XLSX release artifacts when available;
- two clean builds from the same source produce equivalent governed content.
