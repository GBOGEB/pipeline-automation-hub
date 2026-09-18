#!/usr/bin/env python3
"""Fail-closed GM-IV RECON_4_OF_8 qualification assessor.

Qualification is deliberately non-promotional. It accepts bounded F05/F06
reconnaissance receipts while requiring the canonical registry to remain at
PILOT_2_OF_8 with no child or authority transfer.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "GRAND_MISSION_REGISTRY.json"
CONTRACT = HERE / "GM_IV_RECON4_QUALIFICATION_CONTRACT.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(checks, name, condition, detail):
    checks.append({"check": name, "result": "PASS" if condition else "FAIL", "detail": detail})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--f05-receipt", required=True)
    ap.add_argument("--f06-receipt", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    registry = load(REGISTRY)
    contract = load(CONTRACT)
    f05 = load(Path(args.f05_receipt))
    f06 = load(Path(args.f06_receipt))
    source_sha = os.environ.get("SOURCE_SHA", "")
    gm4 = next(x for x in registry["grand_missions"] if x["id"] == "GM-IV")
    gm5 = next(x for x in registry["grand_missions"] if x["id"] == "GM-V")
    checks = []

    require(checks, "01_exact_source_sha", len(source_sha) == 40, source_sha)
    require(
        checks, "02_source_stage_unchanged",
        gm4["state"] == contract["source_stage_required"]
        and gm4["activation_stage"] == "PILOT_2_OF_8",
        f'{gm4["state"]}/{gm4["activation_stage"]}'
    )
    require(
        checks, "03_controlled_baseline_preserved",
        gm4["controlled_pilot_frontiers"] == contract["controlled_baseline"],
        str(gm4["controlled_pilot_frontiers"])
    )
    require(
        checks, "04_reference_baseline_preserved",
        gm4["reference_frontiers"] == contract["reference_baseline"],
        str(gm4["reference_frontiers"])
    )
    require(
        checks, "05_no_child_or_authority_transfer",
        gm4["children"] == [] and registry["authority_transfer"] is False
        and contract["authority_transfer"] is False and contract["children_bound"] is False,
        f'children={gm4["children"]}; authority={registry["authority_transfer"]}'
    )
    require(
        checks, "06_f05_exact_identity",
        f05.get("repository") == contract["selected_recon"]["GM-IV-F05"]["repository"]
        and f05.get("target_sha") == contract["selected_recon"]["GM-IV-F05"]["target_sha"],
        f'{f05.get("repository")}@{f05.get("target_sha")}'
    )
    require(
        checks, "07_f05_habitat_surface",
        f05.get("readme_jupyter_docker_stacks") is True
        and f05.get("dockerfile_count", 0) > 0
        and f05.get("workflow_file_count", 0) > 0
        and f05.get("clean_checkout") is True
        and f05.get("qps_authority_marker_count") == 0,
        json.dumps(f05, sort_keys=True)
    )
    require(
        checks, "08_f06_exact_identity",
        f06.get("repository") == contract["selected_recon"]["GM-IV-F06"]["repository"]
        and f06.get("target_sha") == contract["selected_recon"]["GM-IV-F06"]["target_sha"],
        f'{f06.get("repository")}@{f06.get("target_sha")}'
    )
    require(
        checks, "09_f06_operator_surface",
        f06.get("readme_gitkraken_cli") is True
        and f06.get("readme_mcp_server") is True
        and f06.get("readme_multiple_repos") is True
        and f06.get("clean_checkout") is True
        and f06.get("qps_authority_marker_count") == 0,
        json.dumps(f06, sort_keys=True)
    )
    require(
        checks, "10_f06_reference_bias_explicit",
        f06.get("executable_source_file_count") == 0
        and f06.get("disposition") == "RECON_ACCEPTED_REFERENCE_BIASED",
        f'executable_source_file_count={f06.get("executable_source_file_count")}; disposition={f06.get("disposition")}'
    )
    require(
        checks, "11_gm_v_held",
        gm5["state"] == "HELD" and gm5["children"] == [],
        f'{gm5["state"]}; children={gm5["children"]}'
    )
    require(
        checks, "12_analytics_fail_closed",
        contract["analytics_boundary"]["fleet_pca"].startswith("DEFER_")
        and contract["analytics_boundary"]["fleet_bt"].startswith("DEFER_"),
        json.dumps(contract["analytics_boundary"], sort_keys=True)
    )

    failed = [c for c in checks if c["result"] != "PASS"]
    receipt = {
        "schema": "qps.gm_iv_recon4_qualification_receipt.v1",
        "source_sha": source_sha,
        "result": "PASS" if not failed else "FAIL",
        "current_mission_state": gm4["state"],
        "current_activation_stage": gm4["activation_stage"],
        "qualified_recon_frontiers": ["GM-IV-F05", "GM-IV-F06"] if not failed else [],
        "proposed_next_stage": contract["governor_target_stage"] if not failed else "WITHHELD",
        "mission_promotion": "WITHHELD_FROM_QUALIFICATION",
        "governor_readiness": "READY_FOR_SEPARATE_RECON_4_OF_8_GOVERNOR_GATE" if not failed else "NOT_READY",
        "children_bound": False,
        "authority_transfer": False,
        "gm_v_state": gm5["state"],
        "fleet_pca": contract["analytics_boundary"]["fleet_pca"],
        "fleet_bt": contract["analytics_boundary"]["fleet_bt"],
        "checks": checks,
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "result": receipt["result"],
        "governor_readiness": receipt["governor_readiness"],
        "mission_promotion": receipt["mission_promotion"],
        "source_sha": source_sha
    }, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
