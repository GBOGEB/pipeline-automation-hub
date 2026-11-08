# ISO week-year schedule adapter (JADE owner, plan-only)

This additive adapter **reuses** `mission-control/jade_temple/devops/lifecycle.py::topo_layers` for Kahn dependency waves. It does not invent another DAG executor, change the fleet census, or assume a GitHub Action or manual sign-off has actually completed.

## Contract

- `tools/iso_schedule.py`: `jade.iso-schedule.v1`.
- A `w##DDD` label is **never sufficient alone**. Supply `iso_year`; e.g. `(2026, w01MON)` is **2025-12-29**, while `(2026, w53SUN)` is **2027-01-03**.
- `planning_quarter` is a **13-week planning bucket** (2026 PQ4 contains w40–w53). It must not be confused with a Gregorian calendar quarter, a financial-quarter authority, or a 4-4-5 month pattern.
- `tasks` have `id`, `title`, `start`, `end`, optional `depends_on`, and optional `kind: milestone`. A task's `end` is its declared last date. Finish-to-start dependencies require successor start **after** predecessor end. Same-day event ordering requires another explicit clock/contract and is rejected here.
- All outputs are `DECLARED_PLAN_ONLY` and `authority_transfer=false`. There is **no** inference of completed code, vendor sign-off, RED recovery, or merge eligibility.
- `mermaid_dag` and `mermaid_gantt` are projections. Gantt date anchors use the inclusive declared end (converted to Mermaid's exclusive end); they do not apply holiday exclusions or infer working-day durations; use an independently qualified calendar engine for this.
- Reuse the existing JADE SIPOC / CI-DAG projection owner rather than cloning its definitions. The generic Drive BridgeFlow package remains a candidate **consumer/adapter**, not a second operator.

## Example (synthetic)

```python
from datetime import date
import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path('mission-control/jade_temple/tools').resolve()))\nimport iso_schedule

plan = {
    "schema": "jade.iso-schedule.v1",
    "iso_year": 2026,
    "tasks": [
        {"id": "CHECK", "title": "Schema check", "start": "w46MON", "end": "w46TUE"},
        {"id": "GATE", "title": "Review request", "start": "w48FRI", "end": "w48FRI",
         "kind": "milestone", "depends_on": ["CHECK"]},
    ],
}
validated = iso_schedule.validate_schedule(plan)
print(iso_schedule.mermaid_dag(validated))
print(iso_schedule.mermaid_gantt(validated))
```

Run this example from the Hub repository root. The adapter imports the canonical JADE lifecycle owner via an exact file path.

## Qualification

```bash
python -m unittest discover -s mission-control/jade_temple/tests -p test_iso_schedule.py -v
python -m unittest discover -s mission-control/jade_temple/tests -p 'test_*.py'
python mission-control/jade_temple/tools/regen.py
```

The existing JADE read-only QA workflow matches `mission-control/jade_temple/**`, so this addition is expected to enter exact-PR-head native CI. Existing K-typed binary QA, review protections and RED canaries are independent requirements.

## Follow-up bridge

`GEMINI` consumes a typed, hashed schedule receipt as handover evidence, while `Hub` remains scheduling-plan owner. Cross-repository promotion requires matching `source_repository`, `source_path`, `source_sha`, `schema_version`, `generation_method`, `source_visibility`, `validation_status` and `owner_disposition`. Keep QPS bidder prices and controlled documents in private QPS, not this public repository.
