# SIPOC Process Instances — bounded DAG / asyncio pilot

This read-only planner extends the existing Mission Control subtype-workflow
candidate (#561/#563). It does not replace `PROCESS_LANES_v1.json`, the Method
Atlas, GitHub Actions, REX, or independent repo ownership.

## Identity: template is not an instance

A canonical `lane:stage` is a **template**. An instance adds a distinct ID,
incarnation, SIPOC role (S/I/P/O/C), source repository and exact source SHA,
owner issue, mode, declared dependencies, success predicate and optional lease.
The same `DMAIC:ANALYZE` Process template can have several **P incarnations**,
for example CODE_MAROON, Python compatibility, workflow governance and CI
telemetry. They may be disjoint, parallel and marked `ASYNCIO`; none is
launched merely because it is planned.

- **Fan-out:** independent READY instances of a common predecessor may appear
  in one bounded wave, subject to max-parallel and per-repository limits.
- **Fan-in:** a successor is not planned until every declared predecessor is
  included in an earlier wave. A pending/blocked parent propagates HOLD.
- **Lease safety:** mutating *proposals* with the same root or overlapping
  parent/child path in one repo cannot share a wave. No filesystem writes occur.
- **Feedback:** next-pulse observations use separate `NEXT_PULSE` edges,
  never same-wave cycles. Cycles, unknown sources and duplicate incarnations
  fail closed.
- **Asyncio:** an optional bounded, zero-I/O synthetic replay validates wave
  barriers and fault propagation; it is NOT authenticated worker execution,
  a fleet capacity measurement or independent statistical trial.

## Reproduce

From the repository checkout (Python stdlib only):

```bash
python -m unittest discover -s mission-control/gogreen/tests \
  -p 'test_sipoc_instances.py' -v
python mission-control/gogreen/sipoc_instances.py \
  --input mission-control/gogreen/samples/sipoc_instance_wave_20261016.json \
  --atlas mission-control/federation-atlas/PROCESS_LANES_v1.json \
  --out /tmp/cbd-sipoc --synthetic-replay
```

The producer writes an input-byte and canonical-atlas SHA-256 bound JSON
receipt plus digest and a separately labeled synthetic replay record.
The sample references historical exact heads; it is a **declared scenario**,
not a current live census, dispatched Crew flight, accepted root closure or
project admission. A changed source requires a new observation and rerun.

## Required subsequent adaptation

For an actual P execution, assign the appropriate owner and backend to a
separate authorized producer. Native execution shall provide run ID, attempt,
job/step identities, artifact bytes, pass/fail and resource timing. Join outputs
only once their exact source identities match. A scheduled proposal is never a
verified proof, and N+1 forecasts never overwrite the N checkpoint.
