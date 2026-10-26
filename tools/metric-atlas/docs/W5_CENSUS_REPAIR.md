# CBD W5: bounded census integrity repair

Source owner: existing Metric Atlas census. Coordination: Mission Control #604.
This is a repair candidate, not a second source of truth, dispatcher or publisher.

## Reproduced defects

1. Reducing max_fanout to one dropped two known-head deferred lanes from rollup.
2. A lane with no receipts exposed route_failure=false instead of UNKNOWN/null.
3. Python bool True was accepted as an integer fanout budget.
4. Generated DAG linked output I to same-pulse input A, creating a cycle.

## Repairs and interface

Retain all three eligible lanes; explicitly mark DEFERRED_FANOUT_LIMIT, expose
represented_repos/deferred_repos, and keep unreceived failure state null. Reject
non-integer fanout and invalid head mappings. Expose --max-fanout on the existing
request CLI. Feedback targets a distinct N+1 node; planning is labeled not
dispatched. Missing input files return controlled CENSUS_HOLD exit 2.

## Measured local proof (2026-10-20)

Baseline source git blob ac4e398689e40d799794949e1fa2dcdec96f39e7 was byte verified.
Original 12 tests pass. Four added regressions fail on A, pass on B, and fail again
when returning to unchanged A. This is a local A-B-A experiment, not native CI.

Candidate source SHA256:
cb11c6e23bae11687f1fba7977cfc50dc5d49ef11c7e692c3972845ac9af9223

The same candidate source progresses from 106/155 statements and 51/74 branches
to 155/155 and 74/74, without exclusions. Final focused suite: 90 tests, including
24 budget/availability combinations, native receipt/attempt controls and CLI
negative cases. The new tests use only unittest and the standard library, and
are discovered by the existing qps-metric-census-federation.yml workflow.

Run from repository root:

```sh
PYTHONPATH=tools/metric-atlas python -m unittest discover -s tools/metric-atlas/tests -p 'test_census*.py' -v
PYTHONPATH=tools/metric-atlas python -m metric_atlas.census request --wave W5 --heads qps-receiver-heads.json --max-fanout 1 --output qps-metric-run/requests.json
```

## Admission and remaining proof

Native full Metric Atlas regression, exact-head artifacts, compatibility of all
consumers, independent review/security and effective branch rules remain required.
Local coverage is one module, not whole-repository or fleet coverage. No root is
formally closed, no source-owner gate bypassed, no dispatch activated, and no merge
authorized by these measurements. MERGE_ADMISSION=HOLD.
