#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent.parent

def load(path):
    return json.loads((ROOT/path).read_text(encoding="utf-8"))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-sha",required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()

    c=load("GM_FLEET_3PSTAR_MIP_20260919T0738_v4.json")
    d=load("GM_FLEET_DASHBOARD_V11_DATA.json")
    r=load("GRAND_MISSION_REGISTRY.json")
    gm={m["id"]:m for m in r["grand_missions"]}
    g4,g5=gm["GM-IV"],gm["GM-V"]
    html=(ROOT/"dashboard/GM_FLEET_CONTROL_DASHBOARD_v11.html").read_text(encoding="utf-8")

    checks={}
    checks["01_refresh_exact"]=(
        c["three_pr"]["Refresh"]["missioncontrol_master"]=="361910f19a235af00c247059959dfd8bb797befc"
        and c["three_pr"]["Refresh"]["qps_main"]=="c73cff96406d747493fabc650a670b4c3279d05e"
        and c["three_pr"]["Refresh"]["qps_issue_923"]=="OPEN"
    )
    checks["02_probe_zero_step_no_rerun"]=(
        c["three_pr"]["Probe"]["observed_run_id"]==35372609150
        and c["three_pr"]["Probe"]["observed_attempt_jobs"]==[105689855356,105690079257,105690167950]
        and c["three_pr"]["Probe"]["all_attempts_zero_step"] is True
        and c["three_pr"]["Probe"]["qps_probe_was_retriggered"] is False
    )
    checks["03_rank_first_red"]=(
        c["three_pr"]["Rank"]["blocking_surface"]=="GBOGEB/cryoplant-project#923"
        and c["three_pr"]["Rank"]["no_blind_rerun"] is True
    )
    checks["04_mip_sequential"]=(
        c["mip"]["Modernize"]["result"]=="PASS"
        and c["mip"]["Innovate"]["result"]=="PASS_BOUNDED"
        and c["mip"]["Perpetuate"]["result"]=="PASS_REPOSITORY_NATIVE"
    )
    checks["05_active8_no_children"]=(
        g4["state"]=="ACTIVE_8_OF_8"
        and g4["activation_stage"]=="ACTIVE_8_OF_8"
        and g4["children"]==[]
        and d["planes"]["canonical_admission"]["gm_iv_children"]==[]
    )
    checks["06_scout_c_depth_exact"]=(
        [x["frontier"] for x in d["planes"]["reconnaissance"]["scout_c_depth_board"]]
        ==["GM-IV-F05","GM-IV-F06","GM-IV-F07","GM-IV-F08"]
        and all(x["comparative_rank"]=="NOT_COMPUTED" for x in d["planes"]["reconnaissance"]["scout_c_depth_board"])
        and d["planes"]["reconnaissance"]["rank_policy"]=="NO_COMPARATIVE_FRONTIER_RANK_UNTIL_COMPARABLE_MEASURED_EVIDENCE_ECONOMICS_EXISTS"
    )
    checks["07_gmv_held"]=(
        g5["state"]=="HELD" and g5["children"]==[] and g5["crew_posture"]=="UNALLOCATED"
        and d["planes"]["canonical_admission"]["gm_v_state"]=="HELD"
        and d["planes"]["canonical_admission"]["gm_v_children"]==[]
        and d["planes"]["canonical_admission"]["gm_v_launch_authorized"] is False
    )
    checks["08_analytics_nonpromotional"]=(
        d["planes"]["analytics"]["crew_exposure_pca"]["state"]=="CONTROL_READY_MEASURED_REPEAT_SMALL_N"
        and d["planes"]["analytics"]["crew_exposure_pca"]["causal_interpretation_allowed"] is False
        and d["planes"]["analytics"]["crew_exposure_pca"]["competency_promotion_allowed"] is False
        and d["planes"]["analytics"]["frontier_pca"]["state"]=="CONTROL_READY_MEASURED_REPEAT"
        and d["planes"]["analytics"]["bt"]["state"]=="READY_OBSERVED"
        and d["planes"]["analytics"]["bt"]["observed_pairs"]==12
    )
    checks["09_bd_plane"]=(
        d["planes"]["global_bd"]["rank0"]=="GBOGEB/cryoplant-project#923"
        and d["planes"]["global_bd"]["freshest_bound_child_probe"]["workflow_run_id"]==35372609150
        and all(x["steps"]==0 for x in d["planes"]["global_bd"]["freshest_bound_child_probe"]["attempts"])
        and d["planes"]["global_bd"]["application_repair_authorized"] is False
    )
    checks["10_3pc_hold"]=(
        c["three_pc"]["Prepare"]=="PASS_REUSED"
        and c["three_pc"]["Prove"]=="WITHHELD_EXTERNAL_OWNER_ACTION"
        and c["three_pc"]["Commit"]=="HOLD_WAIT_PROVE"
        and c["three_p3"]=="NOT_AUTHORIZED"
    )
    checks["11_authority_zero"]=(
        c["authority_transfer"] is False and d["authority_transfer"] is False and r["authority_transfer"] is False
        and c["formal_credit_delta"]==0 and c["engineering_credit_delta"]==0
    )
    checks["12_html_planes"]=all(x in html for x in [
        "Analytics","Scout-C / F05–F08","Canonical Admission","Global BD",
        "ACTIVE 8/8","GM-V","Comparative rank is deliberately NOT COMPUTED"
    ])
    expected=set(c["mip"]["Perpetuate"]["outputs"])
    checks["13_perpetuate_outputs"]=all((REPO/p).is_file() for p in expected)

    passed=all(checks.values())
    out={
        "schema":"missioncontrol.gm_fleet.3pstar_mip_validation.v4",
        "source_sha":a.source_sha,
        "result":"PASS_GM_FLEET_3PSTAR_MIP_V4" if passed else "FAIL_GM_FLEET_3PSTAR_MIP_V4",
        "check_count":len(checks),
        "checks":checks,
        "gm_iv_state":g4["state"],
        "gm_iv_children":g4["children"],
        "gm_v_state":g5["state"],
        "gm_v_children":g5["children"],
        "rank0":d["planes"]["global_bd"]["rank0"],
        "authority_transfer":False
    }
    Path(a.out).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(out,indent=2,sort_keys=True))
    return 0 if passed else 1

if __name__=="__main__":
    raise SystemExit(main())
