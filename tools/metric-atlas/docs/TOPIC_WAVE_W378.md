# W378-P0: three-topic pilot, graph identity and PR/Issue temporal review

**RFE:** Reuse existing W377 source-bound topic receipts for a small, disjoint, read-only census planning experiment; produce reproducible per-topic decisions and three architectural lenses (dependency DAG, SIPOC, authority SPINE) without constructing a second source of truth.

## Deep-read temporal inputs (28 October 2026)

| Authoritative owner | Source / PR / issue | Observation and constraint |
|---|---|---|
| Cryoplant | #2157 merged 2026-10-27 | Generator geometry changed; its original PR text explicitly says SVG/viewer/checksum release parity remained open |
| Cryoplant | #2162 merged 2026-10-28 at head a012927a | Electrical feeder source reconciler present, but merge alone is not independent engineering acceptance or post-merge binary QA |
| Cryoplant | #2159 / issue #2163 | PUB-R07 exclusively owns 48 phase×lane Object BIOS work items and proposed 05:17 UTC daily cron; issue #2163 owns the checklist and reported M0..M5 |
| Hub | #985 | W377 typed packet/ACK HMAC protocol; W378 derives packet decisions from its module |
| Hub | #942 | Issue-rank N→N+j wave telemetry owns issue/PR stock and qualified flow; no duplicated closure statistics here |
| Hub | #946 | EVERRED causal root grouping and disjoint source-safe recovery frontier; no root claims from workflow labels here |
| Hub | #951 / issue #336 | Independent first-pass closure and ruleset audit; a successful workflow label alone is not non-bypassable protection |
| Hub | #968 | JADE H01-H12 completeness guard; invariant remains a separate admission ratchet |
| Hub | issue #604 | Canonical Golden Graph 3-pulse MissionControl coordination; W378 graph is a bounded consumer projection only |
| Hub | JADE CICD_DAG_POLICY.json | Existing FUNCTION/SHA/OID lenses and same-pulse topological DAG, next-pulse feedback is a distinct edge |

**Source evidence types:** actual GitHub PR/issue metadata, Git blob OIDs, and an explicitly **synthetic** packet/source SHA256 test fixture. This pilot does not claim that the synthetic source digests represent actual owner binary bytes or a live topic recensus.

## What executes

```bash
PYTHONPATH=tools/metric-atlas python -m unittest discover -s tools/metric-atlas/tests -p 'test_topic_wave.py' -q
PYTHONPATH=tools/metric-atlas python -O -m unittest discover -s tools/metric-atlas/tests -p 'test_topic_wave.py' -q
PYTHONPATH=tools/metric-atlas python -m metric_atlas.topic_wave --input tools/metric-atlas/tests/pilot_3topic.json --out /tmp/w378-p0
```

Input: a three-topic declared scenario for `electrical.icd.feeders`, `metrics.census.ack`, and `publishing.r07.oid`. Outputs: `pilot-receipt.json`, self-contained `graph.html`, and nine Mermaid files (three views × FUNCTION/SHA/OID); `manifest.json` hashes all deliverables but not itself. The graph's 14 typed nodes and 14 edges (including one NEXT_PULSE feedback) are the same underlying node IDs for every projection. SIPOC has S, I, P, O and C roles; authority SPINE is a separate lens, not a source-policy write.

- W377 decision `TARGETED_RECENSUS_REQUIRED` applies only to the deliberately changed source in the fixture.
- An unchanged topic without publication is `STAGED_NOT_DELIVERED`; do not invent an ACK.
- An unrelated producer head drift remains `VERIFY_HEAD_BRIDGE_NO_FULL_RECENSUS`; no claimed source rescan.
- Max three topics, two planning reader lanes, zero source writers, zero native jobs dispatched.
- All physical queue p95, worker hours, matched coverage delta, production reuse and BD flow remain `null` until source-bound evidence is supplied.

## Native pilot acceptance

Initial exact-head PR #986, head `5ec68c1462d63a649112ab5c17d6b61673c6b743`: 41 tests PASS per Python 3.11/3.12, optimized `-O` replay PASS, branch-aware new module coverage 96%, 4 observed workflows successful including W378; one purely synthetic 3-topic build and manifest check executed in both CI matrix cells.

Do not infer engineering, external ACK, owner protection, or GitHub merge approval. The PR is draft and stacks on #985. Re-test after any commit to this PR.

## Progressive admission for P1/P2

P0: three topics, two read-only planning lanes, exact-head green.
P1: two disjoint three-topic partitions, capacity still max two physical source-read lanes, no actual dispatch and no overlap; requires validated packet identities and wave barriers.
P2: conditional live six-topic operation only after independently verified producer receipts, native queue p95, controller-attested ACK and path leases. CRON remains existing hub workflows (hourly head delta, 3-hour red trace, daily slowburn, weekly census); no new schedule in P0/P1.

Stop on unverified ACK, changed source SHA, duplicate topic owner, external controlled-binary access, source-lease conflict, same-pulse cycle, unstable denominator, or red exact-head CI. Do not reissue all PRs or recensus the whole federation to repair one topic.
