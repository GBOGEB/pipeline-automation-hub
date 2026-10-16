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


## Coverage treatment rule

**Grow coverage through behavior, not by excluding difficult lines.**

Coverage workers shall prefer executable behavioral tests, negative controls,
failure propagation and state-transition proofs over excludes, omit pragmas,
denominator shrinkage or test-only source rewrites. A reported uplift is valid
only when the measurement scope and denominator remain comparable to its
baseline. Difficult lines may remain uncovered and visible until a safe
behavioral harness exists; they shall not be hidden to improve a KPI.

## 16 October 2026 — disjoint lease and Testflight root treatment

Native source hardening on [PR #561](https://github.com/GBOGEB/pipeline-automation-hub/pull/561) now validates each mutation lease as a canonical repository-relative POSIX path. Empty components, `.`, `..`, `.git`, absolute and Windows paths fail closed. Two modifying packets in one repository conflict if their paths are identical **or one is an ancestor of the other**: `ci/governance` and `ci/governance/workflow_policy.json` cannot share a worker wave. Sibling files may share a wave when the owner and reviewed path contracts permit it. Cross-repository paths are not aliases.

The native workflow also repairs literal-escaped newlines in the prior test and receipt validation code, uses `unittest discover` for the hyphenated source directory, pins the checkout to the actual PR-head SHA, disables credential persistence, uses SHA-pinned core actions, and publishes real branch-aware source coverage JSON. Authored tests are not native proof; only terminal exact-head CI and inspected artifacts establish DoV.

**Concurrency distinction:** the 18-packet frozen sample declares `max_parallel=3`, allowing three *planned* packets per sample wave. The independent CBQ reverse-pressure expansion in [#562](https://github.com/GBOGEB/pipeline-automation-hub/pull/562) proposes **two read-only scouts per wave**. This is intentionally more conservative and is not a retroactive modification of #561's sample, nor evidence that any two or three workers launched. Increasing to four requires actual source-bound worker receipts, absence of path overlaps and comparable queue-p95/verification-yield observations.

### Candidate N+2 routing

- First read-only pressure wave: canonical workflow-policy reconciliation and independent security inspection; no mutating worker is scheduled on owner-blocked content.
- Second read-only proof-drain wave: inspect the two highest nonterminal PR-head CI backlogs from #562's eight-PR snapshot and classify the actual elapsed queue/run timers via ABACUS #2033.
- Independent source-owned mutation later: compatibility, coverage C2/C3/C4/C5 and security groups only after an owner selects source paths and the latest exact head.
- REX/control: count genuine root reopenings only when accepted integrated-main evidence, source SHA, root ID, run/job/attempt and archive bytes prove them. Missing sessions remain UNKNOWN.

A pressure score is a policy-weighted workload indicator, not a PCA loading, BT strength, expected root closure or instruction to dispatch.
