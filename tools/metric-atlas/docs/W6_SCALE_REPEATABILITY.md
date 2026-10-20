# CODE PURPLE W6-A | harden existing N5 adaptive scale decision

**Authority:** `metric_atlas.adaptive_scale.decide` remains a read-only owner-decision aid. No workflows, required contexts, credential logic or dispatch paths are modified. Source owner: Mission Control Metric Atlas.

## Reproduced first-red (exact original Git blob)

`adaptive_scale.py` source blob `3162207277936259f5822eccba6d92350fd9fbc6`: the original eleven positive regressions pass. Four new adversarial tests independently reproduce false `PROPOSE_3x6_OWNER_REVIEW` for prior terminal count 0, missing scope fingerprint on both pulses, replay of identical receipt-set digest and unclassified P0/P1 presence. Each passes on this candidate, and fails when old source bytes are restored (A -> B -> A).

## W6 controls

- Validate pulse population and integer counter types in one location; reject Booleans masquerading as counts.
- Require **explicit P0/P1 absent** plus separately attested clearance before even proposing 3x6; unknown is not green.
- Recheck *prior* terminal and ZIP proof counts, population/schema and absence of authority transfer.
- Require a nonempty stable scope fingerprint, a matching 64-character source-head-set digest, two distinct native receipt-set digests, and increasing integer pulse indices. These fields prevent simple repeat-claim reuse; the digests still need **independent byte/readback attestation** from source owners.
- Keep 2x4/3x6 labels as proposals. `dispatch_performed=false`, QPS engineering acceptance false, merge admission HOLD, unknown worker hours and coverage unchanged.

## Local verification

`PYTHONPATH=tools/metric-atlas python -m unittest discover -s tools/metric-atlas/tests -p 'test_adaptive_scale*.py' -v`

The candidate 27-test focused suite covers 67/67 statements and 42/42 branches (coverage.py local, zero exclusions). Native exact-head test and independent review are separate non-compensating acceptance gates. An A/B/A reproduction is not a governed main merge or an independent trial series.
