# ISO week-year schedule adapter (JADE owner, plan-only)

This additive adapter **reuses** `mission-control/jade_temple/devops/lifecycle.py::topo_layers` for Kahn dependency waves. It does not invent another DAG executor, change the fleet census, or assume a GitHub Action or manual sign-off has actually completed.

## Contract

- `tools/iso_schedule.py`: `jade.iso-schedule.v1`.
- A `w##DDD` label is **never sufficient alone**. Supply `iso_year`; e.g. `(2026, w01MON)` is **2025-12-29**, while `(2026, w53SUN)` is **2027-01-03**.
- `planning_quarter` is a **13-week planning bucket** (2026 PQ4 contains w40–w53). It must not be confused with a Gregorian calendar quarter, a financial-quarter authority, or a 4-4-5 month pattern.
- `tasks` have `id`, `title`, `start`, `end`, optional `depends_on`, and optional `kind: milestone`. A task's `end` is its declared last date. Finish-to-start dependencies require successor start **after** predecessor end. Same-day event ordering requires another explicit clock/contract and is rejected here.
- All outputs are `DECLARED_PLAN_ONLY` and `authority_transfer=false`. There is **no** inference of completed code, vendor sign-off, RED recovery, or merge eligibility.
- `portable_receipt(plan)` runs the existing validator and exports a JSON-native record with `canonicalization: JADE_CANONICAL_UTF8_JSON_V1`. Its `receipt_sha256` covers exactly the unsigned canonical UTF-8 bytes, excluding the digest field. The SHA-256 is **integrity only**, not Git/Drive provenance, source authentication, independent review or execution evidence.
- `mermaid_dag` and `mermaid_gantt` are projections. Gantt date anchors include the declared final day through an explicit duration, avoiding date overflow at year 9999; they do not apply holiday exclusions or infer working-day durations; use an independently qualified calendar engine for this.
- Reuse the existing JADE SIPOC / CI-DAG projection owner rather than cloning its definitions. The generic Drive BridgeFlow package remains a candidate **consumer/adapter**, not a second operator.

## Example (synthetic)

```python
from datetime import date
import sys
from pathlib import Path
sys.path.insert(0, str(Path('mission-control/jade_temple/tools').resolve()))
import iso_schedule

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
print(iso_schedule.portable_receipt(plan))
```

Run this example from the Hub repository root. The adapter imports the canonical JADE lifecycle owner via an exact file path.

## Canonical wire contract and independent verifier vector

The portable handover contract is deliberately a **restricted JSON profile**, not a claim of RFC 8785/JCS equivalence. To verify `receipt_sha256` across Python, Node, Drive or another runtime:

1. Require `canonicalization == "JADE_CANONICAL_UTF8_JSON_V1"`. Exclude only `receipt_sha256` before hashing; reject an embedded digest in the unsigned payload.
2. Recursively sort **ASCII object-property keys** in ascending lexical order. All keys in this schema (including task IDs) are ASCII. Preserve array order.
3. Use compact JSON: no insignificant spaces, no BOM, no trailing newline. Serialize strings as Unicode scalar values in **raw UTF-8**, with standard JSON escapes for controls, quotation marks and backslashes; do not normalize Unicode. A lone surrogate is invalid. Only integer numbers, booleans, strings, null, objects and arrays are allowed; floats and non-ASCII keys are invalid.
4. Hash these exact bytes with SHA-256 and compare a lower-case 64-hex `receipt_sha256`. A matching hash means **byte parity only**, never that the plan ran or is approved.

The following is an independently reproduced **Python + Node.js** vector. The synthetic plan has one task `CAFE`, title `Café 🔬/∆` (precomposed é, mathematical increment sign), ISO year 2026, start and end `w46MON`, no predecessors. Expected digest (excluding `receipt_sha256`):

```text
bb7d5953a763eed0e7b9d0cd7741f7ae2c128d5305677884d44fbd8038b80c17
```

Node verifier for a `portable_receipt()` JSON result:

```javascript
const { createHash } = require("node:crypto");

function sortAsciiKeys(v) {
  if (Array.isArray(v)) return v.map(sortAsciiKeys);
  if (v !== null && typeof v === "object") {
    const keys = Object.keys(v);
    if (keys.some(k => /[^\\x00-\\x7f]/.test(k))) throw Error("NON_ASCII_KEY");
    return Object.fromEntries(keys.sort().map(k => [k, sortAsciiKeys(v[k])]));
  }
  if (typeof v === "number" && !Number.isSafeInteger(v)) throw Error("NOT_SAFE_INTEGER");
  return v;
}

function verify(receipt) {
  if (receipt.canonicalization !== "JADE_CANONICAL_UTF8_JSON_V1") return false;
  const { receipt_sha256, ...unsigned } = receipt;
  const canonical = JSON.stringify(sortAsciiKeys(unsigned));
  const digest = createHash("sha256").update(Buffer.from(canonical, "utf8")).digest("hex");
  return digest === receipt_sha256;
}
```

Consumers must also validate the schema/field types, Unicode well-formedness, trusted source commit, receipt source binding and permitted data visibility separately. `JSON.stringify` is not itself proof of Unicode scalar validity; do not use this example as a general-purpose arbitrary JSON canonicalizer.

## Qualification

```bash
python -m unittest discover -s mission-control/jade_temple/tests -p test_iso_schedule.py -v
python -m unittest discover -s mission-control/jade_temple/tests -p 'test_*.py'
python mission-control/jade_temple/tools/regen.py
```

The existing JADE read-only QA workflow matches `mission-control/jade_temple/**`, so this addition is expected to enter exact-PR-head native CI. Existing K-typed binary QA, review protections and RED canaries are independent requirements.

## Follow-up bridge

`GEMINI` consumes a typed, hashed schedule receipt as handover evidence, while `Hub` remains scheduling-plan owner. Cross-repository promotion requires matching `source_repository`, `source_path`, `source_sha`, `schema_version`, `generation_method`, `source_visibility`, `validation_status` and `owner_disposition`. Keep QPS bidder prices and controlled documents in private QPS, not this public repository.
