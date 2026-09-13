#!/usr/bin/env python3
"""Governor assessment for GM-IV RECON_2_OF_8 -> PILOT_2_OF_8."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name: str):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def digest(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    contract = load("GM_IV_PILOT2_GOVERNOR_CONTRACT.json")
    registry = load("GRAND_MISSION_REGISTRY.json")
    city = load("MISSION_CITY_GRAPH.json")
    economics = load("GM_IV_EVIDENCE_ECONOMICS.json")
    by_id = {m["id"]: m for m in registry["grand_missions"]}
    gm4 = by_id["GM-IV"]
    gm5 = by_id["GM-V"]

    checks = []

    def add(name: str, passed: bool, detail) -> None:
        checks.append({"check": name, "result": "PASS" if passed else "FAIL", "detail": detail})

    pilots = contract["controlled_pilots"]
    refs = contract["reference_frontiers"]
    add("01_contract_transition", contract["from_state"] == "STAGED_ACTIVE_RECON_2_OF_8" and contract["to_state"] == "STAGED_ACTIVE_PILOT_2_OF_8", [contract["from_state"], contract["to_state"]])
    add("02_two_independent_controlled_pilots", list(pilots) == ["GM-IV-F01", "GM-IV-F03"] and all(v["disposition"] == "PILOT_CONTROL_READY" for v in pilots.values()), list(pilots))
    add("03_f01_master_control_bound", pilots["GM-IV-F01"]["master_source_sha"] == "2cb9de6b07ec7228578da29dd3d7b5804499ba7c" and pilots["GM-IV-F01"]["workflow_run_id"] == 34768296758 and pilots["GM-IV-F01"]["artifact_digest"] == "sha256:74f7566e41112ece5cc8f014ca6574170854e23ec718993f0384aae6fe24cffa", pilots["GM-IV-F01"])
    add("04_f03_master_control_bound", pilots["GM-IV-F03"]["master_source_sha"] == "6dd4d5b375859dabd5e94aac26b8acc61a757ad7" and pilots["GM-IV-F03"]["workflow_run_id"] == 34772053427 and pilots["GM-IV-F03"]["artifact_digest"] == "sha256:24fc6d6122077bee933d2c5b752a9159fa10ed34ea83c4bfebb3ebdfb0cca38c", pilots["GM-IV-F03"])
    add("05_reference_pair_bounded", list(refs) == ["GM-IV-F02", "GM-IV-F04"] and all(v["disposition"] == "REFERENCE" for v in refs.values()), list(refs))
    add("06_registry_pilot_shape", gm4["state"] == contract["to_state"] and gm4["activation_stage"] == "PILOT_2_OF_8" and gm4["controlled_pilot_frontiers"] == ["GM-IV-F01", "GM-IV-F03"] and gm4["reference_frontiers"] == ["GM-IV-F02", "GM-IV-F04"] and gm4["unfilled_frontier_slots"] == ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"], gm4["state"])
    add("07_zero_children", gm4["children"] == [] and contract["children_bound"] is False, gm4["children"])
    add("08_no_authority_transfer", registry["authority_transfer"] is False and contract["authority_transfer"] is False and economics["authority_transfer"] is False, False)
    add("09_mission_city_sync", city["mission_states"]["GM-IV"] == gm4["state"], city["mission_states"]["GM-IV"])
    add("10_evidence_economics_sync", economics["fleet_invariant"]["mission_stage"] == "PILOT_2_OF_8" and economics["fleet_invariant"]["controlled_pilot_frontiers"] == ["GM-IV-F01", "GM-IV-F03"], economics["fleet_invariant"]["mission_stage"])
    add("11_local_pca_bt_fail_closed", economics["pca_gate"]["state"] == "DEFER" and economics["bt_gate"]["state"] == "DEFER", [economics["pca_gate"]["state"], economics["bt_gate"]["state"]])
    add("12_gm_v_held", gm5["state"] == "HELD" and gm5["children"] == [], gm5["state"])
    add("13_next_stage_withheld", "DOES_NOT_AUTHORIZE_RECON_4_OF_8" in contract["next_stage_boundary"], contract["next_stage_boundary"])

    failed = [c for c in checks if c["result"] != "PASS"]
    result = "PASS" if not failed else "FAIL"
    receipt = {
        "schema": "qps.gm_iv_pilot2_governor_receipt.v1",
        "wave": contract["wave"],
        "source_sha": os.environ.get("SOURCE_SHA", os.environ.get("GITHUB_SHA", "LOCAL")),
        "result": result,
        "checks": checks,
        "promotion_decision": "PROMOTE_PILOT_2_OF_8" if result == "PASS" else "WITHHOLD_PILOT_2_OF_8",
        "mission_state": gm4["state"],
        "controlled_pilot_frontiers": gm4.get("controlled_pilot_frontiers", []),
        "reference_frontiers": gm4.get("reference_frontiers", []),
        "unfilled_frontier_slots": gm4.get("unfilled_frontier_slots", []),
        "children_bound": False,
        "authority_transfer": False,
        "gm_v_state": gm5["state"],
        "next_stage": "WITHHELD_PENDING_SEPARATE_RECON_4_OF_8_GOVERNOR_GATE",
        "input_digest_sha256": digest({"contract": contract, "registry": registry, "city": city, "economics": economics}),
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": result, "promotion_decision": receipt["promotion_decision"], "source_sha": receipt["source_sha"], "next_stage": receipt["next_stage"]}, sort_keys=True))
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
