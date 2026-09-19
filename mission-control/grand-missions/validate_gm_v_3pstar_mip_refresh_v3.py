#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--out", required=True)
    a=ap.parse_args()

    c=load("GM_V_3PSTAR_MIP_REFRESH_20260918T1656_v3.json")
    r=load("GRAND_MISSION_REGISTRY.json")
    gm={m["id"]:m for m in r["grand_missions"]}
    g4,g5=gm["GM-IV"],gm["GM-V"]
    jobs=c["three_pr"]["Probe"]["observed_release_runner_probe"]["jobs"]

    checks={}
    checks["01_source_refresh_exact"]=(
        c["source_authority"]["missioncontrol_master_at_refresh"]=="6980c60fae211f956e4ad3068f76882fa02139a3"
        and c["source_authority"]["qps_main_at_refresh"]=="31a2e7bce6409d496fe6e04755cbc3315b5880d3"
        and c["source_authority"]["qps_runtime_gate_state"]=="OPEN"
    )
    checks["02_3pr_sequential_pass"]=(
        c["three_pr"]["Refresh"]["result"]=="PASS"
        and c["three_pr"]["Probe"]["result"]=="PASS_BLOCK_CONFIRMED_NO_RERUN"
        and c["three_pr"]["Rank"]["result"]=="PASS"
    )
    checks["03_zero_step_observation"]=(
        c["three_pr"]["Probe"]["observed_release_runner_probe"]["run_id"]==35359227263
        and len(jobs)==3
        and all(j["status"]=="completed" and j["runner_id"]==0 and j["executed_steps"]==0 for j in jobs)
        and c["three_pr"]["Probe"]["qps_probe_was_retriggered"] is False
    )
    checks["04_rank_external_first_red"]=(
        c["three_pr"]["Rank"]["blocking_surface"]=="GBOGEB/cryoplant-project#923"
        and c["three_pr"]["Rank"]["next_legal_trigger"]=="OWNER_SIDE_ACTIONS_ADMISSION_CHANGE"
        and c["three_pr"]["Rank"]["no_blind_rerun"] is True
    )
    checks["05_mip_sequential_pass"]=(
        c["mip"]["Modernize"]["result"]=="PASS"
        and c["mip"]["Innovate"]["result"]=="PASS_BOUNDED"
        and c["mip"]["Perpetuate"]["result"]=="PASS_REPOSITORY_NATIVE_V3"
    )
    checks["06_gmiv_active8_no_children"]=(
        g4["state"]=="ACTIVE_8_OF_8"
        and g4["activation_stage"]=="ACTIVE_8_OF_8"
        and g4["children"]==[]
        and c["state_planes"]["canonical_admission"]["gm_iv_children"]==[]
    )
    checks["07_recon_plane_exact"]=(
        c["state_planes"]["reconnaissance"]["named_frontiers"]==[
            "GM-IV-F01","GM-IV-F02","GM-IV-F03","GM-IV-F04",
            "GM-IV-F05","GM-IV-F06","GM-IV-F07","GM-IV-F08"
        ]
        and c["state_planes"]["reconnaissance"]["controlled_pilots"]==["GM-IV-F01","GM-IV-F03"]
        and c["state_planes"]["reconnaissance"]["references"]==["GM-IV-F02","GM-IV-F04"]
    )
    checks["08_gmv_held_unallocated"]=(
        g5["state"]=="HELD" and g5["children"]==[] and g5["crew_posture"]=="UNALLOCATED"
        and c["state_planes"]["canonical_admission"]["gm_v_state"]=="HELD"
        and c["state_planes"]["canonical_admission"]["gm_v_children"]==[]
        and c["state_planes"]["canonical_admission"]["launch_authorized"] is False
    )
    checks["09_analytics_nonpromotional"]=(
        c["state_planes"]["analytics"]["crew_row_pca"]=="READY_MEASURED_SMALL_N_CONTROL_REPEAT"
        and c["state_planes"]["analytics"]["frontier_pca"]=="CONTROL_READY_MEASURED_REPEAT"
        and c["state_planes"]["canonical_admission"]["gm_v_children"]==[]
    )
    checks["10_3pc_hold"]=(
        c["three_pc"]["Prepare"]["result"]=="PASS_REUSED_CONTROL_PREPARED"
        and c["three_pc"]["Prove"]["result"]=="WITHHELD_EXTERNAL_OWNER_ACTION"
        and c["three_pc"]["Commit"]["result"]=="HOLD_WAIT_PROVE"
        and c["three_p3"]["authorized"] is False
    )
    checks["11_authority_credit_zero"]=(
        c["authority_transfer"] is False and c["formal_credit_delta"]==0 and c["engineering_credit_delta"]==0
        and r["authority_transfer"] is False
    )
    expected=set(c["mip"]["Perpetuate"]["outputs"])
    repo_root=ROOT.parent.parent
    checks["12_perpetuate_outputs_exist"]=all((repo_root/p).is_file() for p in expected)

    passed=all(checks.values())
    receipt={
        "schema":"missioncontrol.gm_v.3pstar_mip_refresh_validation.v3",
        "source_sha":a.source_sha,
        "result":"PASS_GM_V_3PSTAR_MIP_REFRESH_V3" if passed else "FAIL_GM_V_3PSTAR_MIP_REFRESH_V3",
        "check_count":len(checks),
        "checks":checks,
        "rank0":c["three_pr"]["Rank"]["blocking_surface"],
        "gm_iv_state":g4["state"],
        "gm_v_state":g5["state"],
        "gm_v_launch_authorized":False,
        "authority_transfer":False
    }
    Path(a.out).write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(receipt,indent=2,sort_keys=True))
    return 0 if passed else 1

if __name__=="__main__":
    raise SystemExit(main())
