#!/usr/bin/env python3
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "GRAND_MISSION_REGISTRY.json"
CAPACITY = ROOT / "GM_FLEET_03_CAPACITY_CONTRACT.json"
ECONOMICS = ROOT / "GM_IV_EVIDENCE_ECONOMICS.json"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def add(checks, name, passed, detail):
    checks.append({"check": name, "result": "PASS" if passed else "FAIL", "detail": detail})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", required=True)
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--probe-root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    contract = load(args.contract)
    registry = load(REGISTRY)
    capacity = load(CAPACITY)
    economics = load(ECONOMICS)
    gm = {m["id"]: m for m in registry["grand_missions"]}
    gm4 = gm["GM-IV"]
    gm5 = gm["GM-V"]
    checks = []

    expected_current = contract["current_control_shape"]
    add(checks, "01_current_recon4_control_shape", all([
        gm4.get("state") == expected_current["state"],
        gm4.get("activation_stage") == expected_current["activation_stage"],
        gm4.get("candidate_frontiers") == expected_current["candidate_frontiers"],
        gm4.get("controlled_pilot_frontiers") == expected_current["controlled_pilot_frontiers"],
        gm4.get("reference_frontiers") == expected_current["reference_frontiers"],
        gm4.get("unfilled_frontier_slots") == expected_current["unfilled_frontier_slots"],
        gm4.get("children") == [],
    ]), gm4.get("state"))

    stage = next((x for x in capacity["stage_model"] if x["stage"] == "ACTIVE_8_OF_8"), None)
    add(checks, "02_capacity_contract_active8", bool(stage) and stage.get("maximum_bound_frontiers") == 8 and stage.get("authority_transfer") is False, stage)

    frontier_evidence = contract["frontier_evidence"]
    ids = list(frontier_evidence)
    repos = [frontier_evidence[x]["repository"] for x in ids]
    shas = [frontier_evidence[x]["target_sha"] for x in ids]
    add(checks, "03_eight_unique_frontier_ids", ids == [f"GM-IV-F{i:02d}" for i in range(1, 9)], ids)
    add(checks, "04_eight_unique_repositories", len(repos) == 8 and len(set(repos)) == 8, repos)
    add(checks, "05_eight_nonempty_target_shas", len(shas) == 8 and all(isinstance(x, str) and len(x) == 40 for x in shas), shas)

    add(checks, "06_retained_f01_f03_pilot_evidence", all([
        gm4["pilot_2_of_8_evidence"]["F01"]["target_sha"] == frontier_evidence["GM-IV-F01"]["target_sha"],
        gm4["pilot_2_of_8_evidence"]["F03"]["target_sha"] == frontier_evidence["GM-IV-F03"]["target_sha"],
        gm4["pilot_2_of_8_evidence"]["F01"]["disposition"] == "PILOT_CONTROL_READY",
        gm4["pilot_2_of_8_evidence"]["F03"]["disposition"] == "PILOT_CONTROL_READY",
    ]), gm4["pilot_2_of_8_evidence"])

    add(checks, "07_recon4_gate_evidence_retained", gm4.get("recon_4_of_8_evidence", {}).get("decision") == "READY_FOR_SEPARATE_RECON_4_PROMOTION_PR", gm4.get("recon_4_of_8_evidence"))

    probe_root = Path(args.probe_root)
    probe_rows = []
    probe_ok = True
    for fid in ["GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"]:
        item = frontier_evidence[fid]
        p = probe_root / fid
        sha_file = p / "HEAD_SHA"
        count_file = p / "ENTRY_COUNT"
        observed_sha = sha_file.read_text(encoding="utf-8").strip() if sha_file.exists() else "MISSING"
        count = int(count_file.read_text(encoding="utf-8").strip()) if count_file.exists() else 0
        row_ok = observed_sha == item["target_sha"] and count > 0
        probe_ok = probe_ok and row_ok
        probe_rows.append({"frontier": fid, "repository": item["repository"], "expected_sha": item["target_sha"], "observed_sha": observed_sha, "entry_count": count, "result": "PASS" if row_ok else "FAIL"})
    add(checks, "08_f05_f08_exact_sha_gt0_probes", probe_ok, probe_rows)

    add(checks, "09_economics_control_recon4", all([
        economics["fleet_invariant"]["mission_stage"] == "RECON_4_OF_8",
        economics["fleet_invariant"]["canonical_children_bound"] == 0,
        economics["pca_gate"]["state"] == "DEFER",
        economics["bt_gate"]["state"] == "DEFER",
    ]), {"pca": economics["pca_gate"]["state"], "bt": economics["bt_gate"]["state"]})

    add(checks, "10_no_authority_or_child_binding", contract["authority_transfer"] is False and contract["children_bound"] is False and gm4.get("children") == [], gm4.get("children"))
    add(checks, "11_gm_v_held", gm5.get("state") == "HELD" and gm5.get("children") == [], gm5.get("state"))

    validator = ROOT / "validate_gm_fleet.py"
    code = (
        "import copy,importlib.util,json,pathlib;"
        f"p=pathlib.Path(r'{validator}');"
        "s=importlib.util.spec_from_file_location('fleet',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        f"d=json.load(open(r'{REGISTRY}',encoding='utf-8'));g=next(x for x in d['grand_missions'] if x['id']=='GM-IV');"
        "a=copy.deepcopy(g);a['state']='ACTIVE_8_OF_8';a['activation_stage']='ACTIVE_8_OF_8';"
        "a['candidate_frontiers']=['GM-IV-F01','GM-IV-F02','GM-IV-F03','GM-IV-F04','GM-IV-F05','GM-IV-F06','GM-IV-F07','GM-IV-F08'];"
        "a['unfilled_frontier_slots']=[];print('REJECTED' if not m.gm_iv_supported_shape(a) else 'ACCEPTED')"
    )
    proc = subprocess.run(["python", "-c", code], text=True, capture_output=True, check=False)
    rejected = proc.returncode == 0 and proc.stdout.strip().endswith("REJECTED")
    add(checks, "12_active8_still_fail_closed", rejected, {"returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()})

    passed = all(c["result"] == "PASS" for c in checks)
    decision = contract["decision_semantics"]["READY"] if passed else contract["decision_semantics"]["WITHHOLD"]
    receipt = {
        "schema": "qps.gm_iv_active8_governor_receipt.v1",
        "wave": contract["wave"],
        "source_sha": args.source_sha,
        "result": "PASS" if passed else "FAIL",
        "decision": decision,
        "checks": checks,
        "proposed_frontiers": contract["proposed_eight_frontier_shape"]["candidate_frontiers"],
        "children_bound": False,
        "authority_transfer": False,
        "canonical_state_after_gate": gm4.get("state"),
        "gm_v_state": gm5.get("state"),
        "promotion_boundary": contract["promotion_boundary"],
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
