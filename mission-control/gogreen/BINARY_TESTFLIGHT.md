# GoGREEN Binary TestFlight — Read-only PPTX and HTML evidence

This source-only adapter is attached to the existing
`mission-control/gogreen/` spine. It **does not** replace the existing
ABACUS `tools/qps_binary_bridge.py` semantic parser, the ABACUS Office-style
extractor, CODEX visual golden controls or governed QPS publication.

## Why this exists

The hub M09 legacy processor was found to emit a purported PPTX success for
an invalid file named `.pptx` without parsing its bytes. This adapter performs
an actual binary validation first, rejects invalid packages, preserves slide
order using `presentation.xml` relationships, and retains source SHA-256.
It deliberately does **not** claim that it has visually rendered slides.

## Controlled execution

`python -m unittest discover -s mission-control/gogreen/tests -v`

`python mission-control/gogreen/binary_flight.py archive1.zip archive2.zip --out /tmp/binary-testflight.json`

The reader accepts nested `.pptx`, `.pptm`, `.html`, `.htm`, `.svg` files. It
returns only opaque hashed member identities and aggregate observations. Do
not publish full internal source manifests outside the authorized project.

## Contract and CI tiers

- `G0`: ZIP byte integrity, OPC parts and PPTX slide relationships; unit and
  negative tests; source SHA-256; no macros executed.
- `G1`: source-matched slide/content digest, group counts, slide geometry and
  text-only duplicate candidates; do not classify a text hit as visual equality.
- `G2`: explicit opt-in render sample and native PptxGenJS output QA using the
  supported rendering tools, without placing corporate data in public CI.
- `G3`: HTML/SVG runtime in sandboxed Playwright at desktop/laptop/mobile,
  with link, console, interaction and image checks.
- `G4`: join ABACUS semantic anchors + style observations, CODEX visual golden,
  GoGREEN receipts and child-owned accepted content in a versioned graph.
- `G5`: governed variants and release proof; parent source remains authoritative.

## Non-negotiable boundaries

1. A file extension is not proof of a valid binary. Invalid `.pptx` bytes
   must fail structurally; zero-slide or incomplete packages cannot be green.
2. A parsed ZIP is not a rendered/visual PASS. Off-canvas counts are candidates.
3. A generated screenshot is not source-text or editing/roundtrip parity.
4. A PPTM file is treated as macro-capable; no macro or embedded object executes.
   Ordinary embedded objects are counted separately from active content.
5. Untrusted SVG with a DOCTYPE is rejected by the conservative XML gate;
   use an independently qualified sanitizer before visual acceptance.
6. The output is content-minimized and contains no raw slide text or headings.
7. No security waiver, authority transfer, local/remote dispatch or merge.
8. Existing GoGREEN artifact ZIP verifier remains a different native-run receipt
   validator; archive byte validation here is not authenticated CI evidence.

## Measured local exploratory wave (non-public corpus)

A local exercise against three privately supplied archive inputs observed 80
PowerPoint-family files (76 PPTX and 4 PPTM), 78 structurally parsed packages,
1,643 slides, 105 HTML files, and 34 SVG files. Two PPTX-named inputs were
non-ZIP. Ten SVG assets passed the conservative XML gate; 23 SVG assets were
rejected for unsafe XML declarations and one for malformed XML. SVG rejection
is a policy/sanitization follow-up, not proof of intrinsic rendering failure.

Runtime is measured per invocation. No repeated-run stability, visual defect
closure, test coverage of external source content, publication authorization,
macro execution, or approved engineering-root closure is inferred.

## Responsibility and BD lane

- Input corruption / incorrectly accepted binary -> GoGREEN binary producer.
- Missing content anchors and title/numbering semantics -> ABACUS binary bridge.
- Style or theme failures -> ABACUS Office style provider PR #2068.
- Render regressions / screenshot mismatches -> CODEX visual-golden consumer.
- M09 filename simulation -> legacy M09 source owner, do not silently promote.
- Failed native CI -> source-owned EVERRED; avoid duplicate BD roots.
- Actual accepted root closure -> canonical parent/source decision, not this file.

Evidence level: `LOCAL_REPRODUCIBILITY`; repository CI and any public release
remain gated independently.
