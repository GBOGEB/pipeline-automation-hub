#!/usr/bin/env python3
"""Read-only MissionControl bridge to gg_MATH convergence method/Plotly evidence.

Do not generate a second mathematical kernel, live telemetry SSOT or Pages
publisher. External provider CI and signed artifacts need source-owner readback.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_CONSUMER = "GBOGEB/pipeline-automation-hub"
_PROVIDER = "GBOGEB/gg_MATH"


def valid_sha(value):
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _require(ok, label):
    if not ok:
        raise ValueError("GG_MATH_BRIDGE_HOLD:" + label)


def validate_bridge(config):
    _require(isinstance(config, dict) and config.get("schema") ==
             "missioncontrol.gg_math_convergence_bridge.v1","schema")
    _require(config.get("snapshot_atomic") is False,"cross-repo atomicity")
    _require(config.get("owner")==_CONSUMER,"owner")
    p=config.get("provider",{})
    _require(p.get("repo")==_PROVIDER,"provider repo")
    for field in ("source_head_sha","merge_commit_sha"):
        _require(valid_sha(p.get(field)),"provider identity "+field)
    _require(p.get("math_module")=="kernels/convergence_control.py","canonical method")
    _require(p.get("html_generator")=="mission/federation/convergence_dashboard.py","canonical Plotly")
    _require(type(p.get("merged_pr")) is int and p["merged_pr"]>0,"source PR")
    _require(type(p.get("native_candidate_run")) is int and p["native_candidate_run"]>0,"run")
    _require(p.get("native_conclusion_at_observation") in
             ("QUEUED","IN_PROGRESS","PASS","FAIL","UNKNOWN"),"native state enum")
    _require(p.get("native_terminal_verified") is False,"unverified native proof promotion")
    _require(p.get("native_run_job_attempt_evidence") is None,"external proof not yet bound")
    c=config.get("consumer",{})
    _require(c.get("repo")==_CONSUMER and valid_sha(c.get("branch_baseline")),"consumer identity")
    _require(c.get("existing_kpi_contract")==
             "mission-control/federation-atlas/G3A_MATH_BRIDGE_VIEW_v1.json","registry owner")
    _require(c.get("six_kpi_registry_unchanged") is True,"KPI collision")
    _require(c.get("native_consumer_qa") is None,"consumer qualification cannot self-attest")
    _require(c.get("published_pages_url") is None and
             c.get("hosted_http_verified") is False,"unverified Pages URL")
    method=config.get("method",{})
    _require(method.get("gg_math_receipt_schema")=="gg_math.convergence_receipt.v1","method contract")
    _require(method.get("evidence_class")=="SYNTHETIC_REFERENCE","no live test source")
    _require(type(method.get("live_pulse_receipts_ingested")) is int and
             method["live_pulse_receipts_ingested"]==0,"false live telemetry")
    _require(method.get("forecast_before_actual_input_provenance") is None,"false forecast")
    _require(method.get("canonical_bd_queue")==
             "mission-control/federation-atlas/CODE_PURPLE_BD_QUEUE_v1.json","BD authority")
    for key in ("six_sigma_attested","pca_temporal_certified","bt_stable_certified"):
        _require(method.get(key) is False,"false statistical credential "+key)
    controls=config.get("controls",{})
    _require(controls.get("read_only") is True,"must remain read-only")
    for key in ("new_global_kpi_registry","duplicate_ssot","authority_transfer",
                "qps_acceptance","security_waiver","merge_allowed","raw_telemetry_promoted"):
        _require(controls.get(key) is False,"forbidden promotion "+key)
    _require(controls.get("merge_admission")=="HOLD","independent admission")
    _require(isinstance(config.get("next_owner"),list) and len(config["next_owner"])>0,"owner queue")
    return {
        "schema":"missioncontrol.gg_math_convergence_view.v1",
        "provider_repo":_PROVIDER,"provider_merged_source_sha":p["merge_commit_sha"],
        "provider_head_sha":p["source_head_sha"],
        "provider_run_id":p["native_candidate_run"],
        "provider_source_url":"https://github.com/GBOGEB/gg_MATH/blob/"+p["merge_commit_sha"]+
            "/mission/federation/convergence_dashboard.py",
        "provider_actions_url":"https://github.com/GBOGEB/gg_MATH/actions/runs/"+
            str(p["native_candidate_run"]),
        "plotly_html_status":"GENERATED_BY_PROVIDER_RUN_ONLY_NOT_HOSTED",
        "provider_terminal_status":"UNKNOWN_REFRESH_REQUIRED",
        "math_status":"SYNTHETIC_METHOD_REFERENCE",
        "pca_status":"NOT_ATTESTED","bradley_terry_status":"NOT_ATTESTED",
        "six_sigma_status":"NOT_ATTESTED",
        "capability_vs_coverage_separate":True,
        "gg_math_provider_is_canonical":True,
        "new_kpi_registry_created":False,"live_pulse_receipts_ingested":0,
        "next_owner":config["next_owner"],
        "authority_transfer":False,"qps_acceptance":False,
        "merge_admission":"HOLD",
    }


def render(config):
    outcome=validate_bridge(config)
    output={"consumer":outcome,"bridge_config_sha256":hashlib.sha256(
        json.dumps(config,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()}
    output["receipt_sha256"]=hashlib.sha256(
        json.dumps(output,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return output


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--bridge",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(argv)
    result=render(json.loads(args.bridge.read_text(encoding="utf-8")))
    args.out.parent.mkdir(exist_ok=True,parents=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("GG_MATH_CONVERGENCE_READONLY_PASS",result["receipt_sha256"])


if __name__=="__main__":
    main()
