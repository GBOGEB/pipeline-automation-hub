# QPS TRIAGE method-slide alignment v1

Date: 2026-09-14
Status: NON-BLOCKING METHOD ALIGNMENT
Authority transfer: false

## Purpose

Bind the recovered slide-method content to the QPS TRIAGE control plane without turning the presentation into offer-specific or procurement-authority content.

The presentation remains a standalone method artefact. QPS TRIAGE consumes only the method pattern and its explicit control boundaries.

## Recovered source content

### Evaluation architecture and order of operations

1. Layer A — Static BT seed
2. Layer B — Extraction schema
3. Layer C — A vs B pairwise BT
4. Risk overlay and final score

Control rule:

> Static requirement ranking must happen before bidder comparison. Risk modifies confidence in bidder delivery, not importance of the requirement.

The Layer B source region was visually blurred; `Extraction schema` is retained from the slide intent / parsed deck text rather than silently guessed from OCR noise.

### Method governance

DMAIC sequence:

`Define -> Measure -> Analyze -> Improve -> Control`

Retained method descriptors:

- Iterative
- Evolutionary
- Recursive
- Idempotent

## QPS TRIAGE mapping

| Method element | QPS TRIAGE interpretation | Guard |
|---|---|---|
| Static BT seed | Frozen requirement-importance baseline | Must precede comparison |
| Extraction schema | Evidence normalization + source capture | May not rewrite priority |
| A vs B pairwise BT | Controlled comparison layer | Consumes frozen baseline |
| Risk overlay | Delivery-confidence modifier | May not redefine requirement importance |
| DMAIC | Recursive governance / controlled improvement | Improve and Control gates required before canonicalization |

## Boundary

This method material is **not** QPS engineering truth, offer evidence, bidder acceptance, compliance disposition, negotiation credit, release credit, or Table-10 credit.

It is a reusable reasoning/control pattern only.

The method deck therefore remains decoupled from the applicant-offer corpus even though the QPS TRIAGE framework may reference it horizontally.

## Input identities scanned in the originating session

- Evaluation architecture image SHA-256: `8e49d967d719be7f6205715d29f3044d17de92a80a948c257d9c24f0ebbfbed0`
- DMAIC image SHA-256: `af34f8f9aa8817161884faa05c12bc056d673a3c1b1660bcc3bda0498913ce65`
- Applicant technical-content workbook SHA-256: `86421bdffd8cb2d3dcefe33e5d7a1f81c637d46f5ecdb10c8e725d8a48053827`
- Applicant document-list source SHA-256: `192f27a283baed04387ec6e8e1d8552b6f507bc039c48b1e8b035896e1ee7ad9`
- QPS Addendum-II technical-requirements source SHA-256: `8bd6c3db5452766526737da0af98a995068733be025b23f3d38b582c43531d4d`
- Polished editable deck SHA-256: `bfac7eb830115378fedd6066896e40a5d02c0d685ce5321bf0e841d4846ed5b3`

## Validation completed

- OCR run against both base images.
- Presentation rebuilt with editable text and shapes rather than pasted text-as-figure.
- Render QA completed.
- PowerPoint overflow test passed.
- Ambiguous OCR retained as explicit ambiguity rather than promoted as fact.

## H4 / W2 / W3 alignment

This is non-blocking horizontal method alignment only.

It does **not** satisfy the W2 exact-runtime proof predicate and does not alter `HOLD` for W2.

It does **not** satisfy W3 local DoV and does not alter `HOLD_W2_LOCAL_DOV` for W3.

Useful carry-forward after the existing gates clear:

- W2 may reuse `Static BT seed -> Extraction schema -> Pairwise -> Risk overlay` as the ordering contract for analytical adapters.
- MIP-I may use DMAIC `Measure -> Analyze -> Improve` for diagnostics but must reach `Control` before canonical promotion.
- W3 / MIP-P should preserve idempotence: reprocessing the same exact-source evidence and same governed configuration must not create a different promoted state.

## Credit guard

Engineering / compliance / negotiation / acceptance / release / Table-10 / mission-control credit delta: **0**.
