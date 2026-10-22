# Mission Control Makeover W1 — Definition of Verification

**Status: VERIFY_PENDING.** This checklist never constitutes automatic merge approval, QPS owner acceptance or an independent statistical capability certificate. Exact-head native GitHub Actions and artifact byte checks must be completed.

## Controlled source scope

Canonical input paths:
- `mission-control/federation-atlas/PROCESS_LANES_v1.json` (10 lanes, 39 stage atoms)
- `mission-control/federation-atlas/CODE_PURPLE_BEAMS_DAG_v1.json` (10 beams, 13 beam edges)
- `mission-control/gogreen/samples/sipoc_instance_wave_20261016.json` (eight **historical** planner instances)
- `mission-control/federation-atlas/pages_portal.py` is the existing single Pages owner

Graph projection: 5 source-repository locators + 39 stage nodes + 10 beam nodes = **54 typed nodes**. Stage-chain edges: (39 - 1) = **38**; beam edges: **13**; total **51 typed edges**. Repository locators have no fabricated dependency edges; they do not prove a five-hop native federation.

## W1 technical DoV is a conjunction, not an averaged percentage

```text
W1_TECH_DOV =
  EXACT_HEAD_MATCH
  AND CANONICAL_54_NODE_51_EDGE_SCOPE
  AND NO_SAME_PULSE_CYCLE
  AND NO_UNTIMED_FEEDBACK
  AND W1_UNIT_TESTS_TERMINAL_PASS
  AND SOURCE_SHA256_MEMBERS_MATCH
  AND PAGES_COPY_AND_SITE_MANIFEST_MATCH
  AND BROWSER_QA_ALL_THREE_VIEWPORTS_PASS
  AND NATIVE_ARTIFACT_ZIP_AND_MEMBERS_VERIFIED
```

Required acceptance matrix:

| Gate | Eligible population / threshold | Proof |
|---|---|---|
| Source graph | 54/54 node identities, 51/51 edge identities | `graph.json`, tested at exact source SHA |
| Methods | 10/10 lanes, 39/39 stages; 10/10 beams; 13/13 beam links | Canonical input SHA-256 hashes |
| Temporal graph | Zero same-pulse cycles; 100% FEEDBACK labelled NEXT_PULSE | Source algorithm plus negative cycle tests |
| Unit contracts | 10 newly added tests; **all pass, zero fail, zero skip**; existing test suite also required | Exact-head native Method Atlas job log |
| HTML usability | 3/3 viewport checks (1440×1000,1280×800,390×844); zero browser/page errors and horizontal document overflow | `w1-browser-qa.json`, three SHA-bound PNG screenshots |
| Portal parity | 4/4 deployed-copy members identical: `index.html`, `graph.json`, `graph.mmd`, `manifest.json` | `site-manifest.json`, SHA-256 per copied member |
| Native archive | Authenticated artifact ZIP identity, ZIP digest/bytes, and matching member bytes | Native run/job/attempt/artifact ID, ZIP opened and verified |
| Admission | Never inferred from technical DoV | Eligible human review, security, branch rules, exact-main and hosted Pages checks |

The historical sample's `max_parallel=3` and `per_repo=2` are **planner settings**, not measured concurrent workers. Worker hours, queue p95, native federation receiver chains, M2/M3 capability and cross-repo coverage are UNKNOWN until independent measurements exist.

## Statistical interpretation

Counted complete *controlled graph objects* support deterministic integrity claims, conditional on the same SHA and no data omissions. Unit tests and three screens are a deliberately selected finite engineering acceptance set, **not an independently sampled population**. Do not assert a binomial confidence interval, Six Sigma, reliability asymptote, PCA/BT superiority or stable time-series convergence from 10 tests or three rendered viewports.

If (hypothetically) 10 executions were independent Bernoulli trials and all passed, the one-sided 95% lower success-probability bound would be `0.05^(1/10)=0.741`. Those independence/exchangeability assumptions are **not established here**, so the number is a mathematical caution, not accepted programme performance.

## Custody and Stop rule

`COMMITTED_TO_PR` is not `EXACT_HEAD_NATIVE_VERIFIED`. `W1_TECH_DOV` is not `MERGE_ADMISSION`. A queue-only result is PENDING, not an execution or a pass. After source mutations, invalidate old exact-head receipts and measure against the newly pinned head. Do not rerun deterministic source failure without an owned fix. Keep `MERGE_ADMISSION=HOLD` until independently verified. No synthetic issue closure or new root credit.
