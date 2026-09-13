#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTROL = ROOT / "history" / "CREW_EXPOSURE_CONTROL_RETURN_v1.json"
POLICY = ROOT / "CREW_EXPOSURE_FEATURE_POLICY_v1.json"
ALLOCATION = ROOT / "MEASURED_ALLOCATION_RECEIPT.json"

control = json.loads(CONTROL.read_text(encoding="utf-8"))
policy = json.loads(POLICY.read_text(encoding="utf-8"))
allocation = json.loads(ALLOCATION.read_text(encoding="utf-8"))

gate = control["repeat_gate"]
assert control["schema"] == "missioncontrol.crew_exposure_control_return.v1"
assert control["status"] == policy["eligibility_gate"]["status_required"]
assert gate["observed_distinct_runs"] >= policy["eligibility_gate"]["minimum_distinct_runs"]
assert gate["observed_distinct_source_shas"] >= policy["eligibility_gate"]["minimum_distinct_source_shas"]
assert gate["all_assignments_predeclared"] is True
assert gate["all_assignments_accepted"] is True
assert gate["all_exposure_identities_valid"] is True
assert gate["no_canary_rows"] is True
assert gate["no_estimated_or_post_hoc_time"] is True
assert control["authority_transfer"] is False
assert control["child_binding"] is False
assert control["frontier_binding"] is False
assert control["competency_promotions"] == 0

by_crew: dict[str, list[dict]] = defaultdict(list)
run_ids = set()
source_shas = set()
for run in control["evidence_runs"]:
    run_ids.add(str(run["run_id"]))
    source_shas.add(run["source_sha"])
    for observation in run["assignments"]:
        assert observation["outcome"] == "ACCEPT"
        by_crew[observation["crew_id"]].append(observation)

feature_names = policy["allocation_features"]
for row in allocation["rows"]:
    obs = by_crew.get(row["crew_id"], [])
    if not obs:
        row["exposure_control_eligible"] = False
        continue
    values = {
        "mean_waiting_seconds": statistics.mean(o["waiting_seconds"] for o in obs),
        "mean_active_seconds": statistics.mean(o["active_seconds"] for o in obs),
        "mean_release_seconds": statistics.mean(o["release_seconds"] for o in obs),
        "mean_exposure_seconds": statistics.mean(o["exposure_seconds"] for o in obs),
    }
    row.update(values)
    row["exposure_control_eligible"] = True
    row["exposure_distinct_runs"] = len(run_ids)
    row["exposure_distinct_source_shas"] = len(source_shas)
    row["exposure_evidence_class"] = "CONTROLLED_MEASURED_REPEAT"

controlled_rows = [r for r in allocation["rows"] if r.get("exposure_control_eligible")]
varying = []
for feature in feature_names:
    vals = [r[feature] for r in controlled_rows if r.get(feature) is not None]
    if len(vals) >= 2 and len(set(vals)) > 1:
        varying.append(feature)

allocation["exposure_control"] = {
    "status": "CONTROLLED_OPTIONAL_FEATURES",
    "source_control_return": CONTROL.name,
    "controlled_rows": len(controlled_rows),
    "distinct_runs": len(run_ids),
    "distinct_source_shas": len(source_shas),
    "allocation_features": feature_names,
    "varying_features": varying,
    "pca_feature_ingest_status": "DEFER_PENDING_THIRD_DISTINCT_SHA_PULSE",
    "bt_status": "NO_CHANGE_EXISTING_BT_OUTCOME_GATE",
    "competency_promotions": 0,
    "authority_transfer": False,
}

ALLOCATION.write_text(json.dumps(allocation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(allocation["exposure_control"], sort_keys=True))
