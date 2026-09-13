#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTROL = ROOT / "history" / "CREW_EXPOSURE_PCA_CONTROL_RETURN_v1.json"
REGISTRY = ROOT.parents[2] / "grand-missions" / "GRAND_MISSION_REGISTRY.json"

control = json.loads(CONTROL.read_text(encoding="utf-8"))
registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


require(control["schema"] == "missioncontrol.crew_exposure_pca_control_return.v1", "schema")
require(control["status"] == "CONTROL_READY_MEASURED_REPEAT_SMALL_N", "control status")
require(control["authority_transfer"] is False, "authority transfer")
require(control["competency_promotions"] == 0, "competency promotion")
require(control["causal_interpretation_allowed"] is False, "causal interpretation")
require(control["sample_rank_cap"] <= 3, "small-n rank cap")
require(control["repeat_gate"]["exact_head_pass"] is True, "exact head pass")
require(control["repeat_gate"]["merged_master_pass"] is True, "merged master pass")
require(control["repeat_gate"]["bt_observed_pairs"] == 12, "BT observed pairs")
require(control["repeat_gate"]["bt_single_cell_wins"] == 8.0, "BT single wins")
require(control["repeat_gate"]["bt_paired_cell_wins"] == 4.0, "BT paired wins")
require(len(control["evidence_runs"]) == 2, "two control evidence runs")
require(len(set(r["source_sha"] for r in control["evidence_runs"])) == 2, "distinct control SHAs")
require(all(len(r["source_sha"]) == 40 for r in control["evidence_runs"]), "40-char SHAs")
require(all(len(r["components"]) == 3 for r in control["evidence_runs"]), "three components each")

by_pc = []
for idx in range(3):
    vals = [r["components"][idx]["explained_variance_ratio"] for r in control["evidence_runs"]]
    by_pc.append(max(vals) - min(vals))
require(max(by_pc) < 0.01, "PCA explained-variance repeat drift below 0.01")

# The PCA return is historical evidence captured while GM-IV was at RECON_2_OF_8.
# Its measured PCA/BT evidence remains immutable even after a separately governed
# mission-stage promotion. Current topology is checked independently below.
historical_stage = "STAGED_ACTIVE_RECON_2_OF_8"
historical_candidates = ["GM-IV-F01", "GM-IV-F02"]
historical_unfilled = [
    "GM-IV-F03", "GM-IV-F04", "GM-IV-F05",
    "GM-IV-F06", "GM-IV-F07", "GM-IV-F08",
]

by_id = {m["id"]: m for m in registry["grand_missions"]}
gm4 = by_id["GM-IV"]
gm5 = by_id["GM-V"]
current_state = gm4["state"]
allowed_states = {
    "STAGED_ACTIVE_RECON_2_OF_8",
    "STAGED_ACTIVE_PILOT_2_OF_8",
    "STAGED_ACTIVE_RECON_4_OF_8",
    "ACTIVE_8_OF_8",
}
require(current_state in allowed_states, "GM-IV non-regressing controlled stage")
require(gm4["children"] == [], "GM-IV zero children")

if current_state == "STAGED_ACTIVE_RECON_2_OF_8":
    require(gm4["candidate_frontiers"] == historical_candidates, "GM-IV F01/F02 recon candidates")
    require(gm4["unfilled_frontier_slots"] == historical_unfilled, "GM-IV historical unfilled frontier shape")
elif current_state == "STAGED_ACTIVE_PILOT_2_OF_8":
    require(gm4["controlled_pilot_frontiers"] == ["GM-IV-F01", "GM-IV-F03"], "GM-IV controlled pilot pair")
    require(gm4["reference_frontiers"] == ["GM-IV-F02", "GM-IV-F04"], "GM-IV reference pair")
    require(
        gm4["unfilled_frontier_slots"] == ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"],
        "GM-IV F05-F08 unfilled",
    )
require(gm5["state"] == "HELD", "GM-V held")
require(gm5["children"] == [], "GM-V zero children")

result = {
    "schema": "missioncontrol.crew_exposure_pca_control_validation.v1",
    "status": "PASS" if not errors else "FAIL",
    "errors": errors,
    "max_explained_variance_repeat_delta": max(by_pc),
    "sample_rank_cap": control["sample_rank_cap"],
    "bt_observed_pairs": control["repeat_gate"]["bt_observed_pairs"],
    "authority_transfer": False,
    "competency_promotions": 0,
    "historical_evidence_stage": historical_stage,
    "historical_candidate_frontiers": historical_candidates,
    "historical_unfilled_frontier_slots": historical_unfilled,
    "current_mission_state": current_state,
    "gm_iv_children": 0,
    "gm_v": "HELD",
}
print(json.dumps(result, indent=2, sort_keys=True))
raise SystemExit(0 if not errors else 1)
