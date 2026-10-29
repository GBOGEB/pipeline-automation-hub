# N+8 CI Spine → Mission Control W4/JADE viewer bridge (candidate)

**Owner:** W4 `mission-control/v2/spine_w4/spine_control.py` supplies the validated control DAG/SIPOC, SVG and HTML layout. The additive `ci_spine_consumer.py` calls its `validate()`, `svg()` and `html_view()` rather than copying the graph renderer or introducing a new canonical metric. JADE `mission-control/jade_temple/tools/cicd_dag.py` and `mission-control/jade_temple/devops/actions_metrics.py` remain the DAG and timing owners. This PR only adds a section to a locally generated review view.

## Source-to-view data flow / SIPOC

| Supplier | Input | Process | Output | Consumer |
|---|---|---|---|---|
| #996 CI authority index | `jade.devops.ci-spine.index.v1`, exact source SHA, static anchor bindings | Validate identity, never promote `HOLD` | Anchor table and source SHA | W4 review viewer |
| #1006 source delta owner | `jade.devops.ci-spine.source-delta.v1` | Check current-source join; show safety-attention values as declared | Two-pulse change register or mismatch flag | W4 review viewer |
| JADE Actions metrics owner | `jade.devops.actions-metrics.v1`, observation date, Hub cohort | Display *unchanged* provider values; flag stale head and job sample | Historical timing/coverage table | Operators, not merge gate |
| #1001 wave policy | `jade.devops.ci-spine.waves.v1` | Present stage/lane/task declarations only | Worker matrix `NOT_EXECUTED` | Mission Control worker planners |
| Existing W4 SPINE owner | `control_view.json` and `spine_control.py` | Existing static typed graph, six SIPOC rows, SVG/HTML | One source-bound HTML plus SHA-256 manifest | Human review |

## Controlled offline generation

Prerequisite: #996's source index is independently admitted as a reusable input. Until then, this is **synthetic/local consumer testflight** and MUST NOT be published or merged on that basis.

```bash
python -m unittest tests/test_ci_spine_consumer.py -v
python scripts/ci_spine_index.py --check --source-sha "$(git rev-parse HEAD)" --out /tmp/ci-spine-index.json
python mission-control/v2/spine_w4/ci_spine_consumer.py \
  --index /tmp/ci-spine-index.json \
  --control mission-control/v2/spine_w4/control_view.json \
  --metrics mission-control/jade_temple/data/ACTIONS_METRICS_FOCUS5.json \
  --expected-head "$(git rev-parse HEAD)" \
  --out /tmp/ci-spine-review.html
```

Optional `--delta` and `--wave` consume the existing owner schemas; the output does not manufacture missing snapshots. Output has `ci-spine-review.html` and `ci-spine-review.manifest.json`, retaining exact input-byte SHA-256s. HTML is deterministic and every external field is escaped; no scripts, network, DOM reinterpretation, built-in browser publishing or user-supplied URL injection.

The committed Actions metrics source is observed **2026-10-26 11:35:37 UTC** for the period 1–26 Oct. Its Hub head is NOT the 29 Oct CI spine PR source and the census `same_pulse` flag may be false. Therefore display `HISTORICAL_UNMATCHED_SOURCE`, not a current comparative p95 or evidence of 3→4 worker nonregression. Job sample coverage and run-tier denominators stay as emitted by the owner. No new CI metric owner is established. Re-fresh the canonical Actions owner and re-pulse exact identity before drawing real comparisons.

### Admission / DoV (all noncompensating)

- [x] Read-only addendum to existing W4 owner view; no modification to generated JADE artifacts
- [x] Eight synthetic tests for source drift, escaped HTML, W4 HOLD, same-source joins and manifest parity
- [ ] New script and eight tests run at exact source head with terminal GitHub receipts
- [ ] Input authority #996 and delta/policy owner #1006/#1001 independently qualified
- [ ] Real provider pulse with same-cohort p95/job-minute data and a negative regression check
- [ ] W4 owner review and visual browser QA at 1440×1000 / 1280×800 / 390×844
- [ ] Authorized publication via existing single CODEX/Pages publisher, **never** from this script alone

**Merge admission = HOLD**; **runtime nonregression = NOT_PROVEN**; **dispatch authorization = false**; **source authority transfer = false**; N+9 branch hygiene is a separate owner lane.
