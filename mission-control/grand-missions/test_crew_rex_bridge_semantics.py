#!/usr/bin/env python3
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "crew_rex_bridge.py"

with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "crew_rex.json"
    subprocess.run(
        ["python3", str(SCRIPT), "--out", str(out)],
        cwd=ROOT,
        check=True,
    )
    report = json.loads(out.read_text(encoding="utf-8"))

requested = set(report["operations_requested_in_seed_ledger"])
observed = set(report["operations_observed_in_seed_ledger"])

assert {"ASSIMILATE", "PRUNE", "BRIDGE"} <= requested
assert {"ASSIMILATE", "PRUNE", "BRIDGE"}.isdisjoint(observed)
assert observed == set(report["operations_completed_by_mc_disposition"])
assert set(report["operations_dormant_until_completed_disposition"]) == set(report["operation_capability"]) - observed

print(json.dumps({
    "status": "PASS_HIST_BD_001_REX_SEMANTICS",
    "requested": sorted(requested),
    "observed": sorted(observed),
}, sort_keys=True))
