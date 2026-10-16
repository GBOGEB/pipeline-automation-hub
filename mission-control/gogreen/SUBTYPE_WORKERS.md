# CBD subtype worker orchestration

This layer reuses Mission Control GOGREEN and Atlas primitives to turn a flat
burndown list into **category -> subtype -> work-packet -> proof** lanes.

It is not a second SSOT. Source truth remains the producer repository, native
GitHub run/job/artifact identity, canonical owner issue, and independent
admission.

## Packet contract

Each packet carries category/subtype, exact source SHA, owner issue, priority,
DMAIC-style phase, mode, optional mutation path lease, explicit success
predicate, blockers, occurrence/fingerprint counts, source-bound proof,
independent approval, and accepted root IDs.

Only READY packets enter the bounded schedule. Overlapping mutation paths in
the same repository cannot share a wave. Read-only analysis packets may fan
out concurrently.

## KPI contract

The receipt reports packet readiness, blocked count, planned waves, source-bound
proof count, byte-verified proof count, observed occurrences/fingerprints, and
independently accepted causal-root closures.

Worker minutes/capacity, throughput prediction, matched coverage uplift, M2/M3,
PCA, and Bradley-Terry stay UNKNOWN/HOLD unless independently measured.
dispatch_authorized, merge_authorized, security_waiver, and authority_transfer
remain false.

The seeded 16 October slice covers Security B3/B4/B5 and Safety, Governance A10
and workflow classification, Python compatibility, and native ZIP evidence.
