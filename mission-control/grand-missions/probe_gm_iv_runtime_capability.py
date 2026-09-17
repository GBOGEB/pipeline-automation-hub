#!/usr/bin/env python3
import argparse
import json
import os
import py_compile
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CREW = ROOT.parent / "qps-triage-ultra" / "crew"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def current_head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def run_python(path: Path, *args):
    proc = subprocess.run(["python", str(path), *args], text=True, capture_output=True)
    require(proc.returncode == 0, f"{path.name} exit={proc.returncode} stderr={proc.stderr[-500:]}")
    return (proc.stdout or "").strip()


def probe_command():
    launch = load(ROOT / "GM_FLEET_IMMINENT_LAUNCH_CONTROL_v1.json")
    registry = load(ROOT / "GRAND_MISSION_REGISTRY.json")
    orders = [x["order"] for x in launch["launch_order"]]
    require(orders == sorted(orders) and len(orders) == len(set(orders)), "launch order must be unique and monotonic")
    gm = {m["id"]: m for m in registry["grand_missions"]}
    require(gm["GM-IV"]["state"] == "ACTIVE_8_OF_8", "GM-IV must be ACTIVE_8_OF_8")
    require(gm["GM-V"]["state"] == "HELD", "GM-V must remain HELD")
    require(launch["authority_transfer"] is False, "launch control authority transfer must remain false")
    return {"launch_entries": len(orders), "gm_iv_state": gm["GM-IV"]["state"], "gm_v_state": gm["GM-V"]["state"]}


def probe_technical_boundary():
    registry = load(ROOT / "GRAND_MISSION_REGISTRY.json")
    promotion = load(ROOT / "GM_IV_ACTIVE8_PROMOTION_CONTRACT.json")
    gm = {m["id"]: m for m in registry["grand_missions"]}
    gm4 = gm["GM-IV"]
    require(registry["authority_transfer"] is False, "fleet authority_transfer must be false")
    require(gm4["children"] == [], "GM-IV canonical children must remain empty")
    require(gm["GM-V"]["children"] == [], "GM-V children must remain empty")
    forbidden = " | ".join(promotion["forbidden_mutations"])
    require("transfer engineering authority" in forbidden, "engineering authority boundary missing")
    require("promote GM-V from HELD" in forbidden, "GM-V boundary missing")
    require(gm4.get("active_8_of_8_evidence", {}).get("result") == "PASS", "ACTIVE8 accepted evidence missing")
    return {"gm_iv_children": 0, "gm_v_children": 0, "active8_evidence": "PASS"}


def probe_recon():
    governor = load(ROOT / "GM_IV_ACTIVE8_GOVERNOR_CONTRACT.json")
    evidence = governor["frontier_evidence"]
    expected = [f"GM-IV-F{i:02d}" for i in range(1, 9)]
    require(sorted(evidence) == expected, f"frontier evidence keys mismatch: {sorted(evidence)}")
    repos = []
    shas = []
    for fid in expected:
        row = evidence[fid]
        repo = row.get("repository", "")
        sha = row.get("target_sha", "")
        require(repo.startswith("GBOGEB/"), f"{fid} repository not governed")
        require(len(sha) == 40 and all(c in "0123456789abcdef" for c in sha.lower()), f"{fid} invalid target SHA")
        require(bool(row.get("class")), f"{fid} missing evidence class")
        repos.append(repo)
        shas.append(sha)
    require(len(set(repos)) == 8, "frontier repositories must be unique")
    require(len(set(shas)) == 8, "frontier SHAs must be unique")
    return {"frontiers": 8, "unique_repositories": len(set(repos)), "unique_shas": len(set(shas))}


def probe_analysis():
    stdout = run_python(ROOT / "validate_gm_iv_evidence_economics.py")
    return {"validator": "validate_gm_iv_evidence_economics.py", "stdout_tail": stdout[-240:]}


def probe_runtime():
    expected = os.environ.get("MC_SOURCE_SHA", "")
    base = os.environ.get("MC_BASE_SHA", "")
    actual = current_head()
    require(len(expected) == 40, "MC_SOURCE_SHA must be exact 40-char SHA")
    require(len(base) == 40, "MC_BASE_SHA must be exact 40-char SHA")
    require(actual == expected, f"runtime exact head mismatch expected={expected} actual={actual}")
    require(subprocess.run(["git", "merge-base", "--is-ancestor", base, actual]).returncode == 0, "runtime event-base ancestry mismatch")
    repeat = load(ROOT / "GM_IV_POST_ACTIVE8_REPEAT_CONTROL_CONTRACT.json")
    require(repeat["success_semantics"]["repeat_control"] == "PASS_POST_ACTIVE8_REPEAT_CONTROL", "repeat CONTROL contract missing")
    require(repeat["success_semantics"]["gm_v"] == "HELD", "repeat CONTROL must preserve GM-V hold")
    return {"exact_source_sha": actual, "event_base_sha": base, "repeat_control_contract": "BOUND"}


def probe_qa():
    stdout = run_python(CREW / "validate_crew_system.py")
    require("PASS_CREW_SYSTEM" in stdout, "crew-system QA marker missing")
    return {"validator": "validate_crew_system.py", "marker": "PASS_CREW_SYSTEM"}


def probe_build_repair_reserve():
    targets = [
        ROOT / "validate_gm_fleet.py",
        ROOT / "assess_gm_fleet_03.py",
        ROOT / "validate_gm_iv_post_active8_repeat_control.py",
        ROOT / "probe_gm_iv_runtime_capability.py",
        ROOT / "measure_gm_iv_runtime_capacity.py",
    ]
    for target in targets:
        py_compile.compile(str(target), doraise=True)
    return {"compiled_scripts": [p.name for p in targets], "count": len(targets)}


def probe_governance():
    registry = load(ROOT / "GRAND_MISSION_REGISTRY.json")
    capacity = load(ROOT / "GM_FLEET_03_CAPACITY_CONTRACT.json")
    launch = load(ROOT / "GM_FLEET_IMMINENT_LAUNCH_CONTROL_v1.json")
    gm = {m["id"]: m for m in registry["grand_missions"]}
    require(registry["authority_transfer"] is False, "registry authority transfer must be false")
    require(capacity["authority_transfer"] is False, "capacity authority transfer must be false")
    require("NO_UNRESOLVED_NONCOMPENSATING_VETO" in capacity["release_invariants"], "noncompensating veto release invariant missing")
    require(gm["GM-V"]["state"] == "HELD" and gm["GM-V"]["children"] == [], "GM-V governance hold broken")
    gm_v_entry = next(x for x in launch["launch_order"] if x["id"] == "GM-V-HOLD")
    require(gm_v_entry["state"] == "HELD", "launch-control GM-V hold broken")
    require("SEPARATE_GOVERNOR_LAUNCH" in gm_v_entry["launch_gate"], "separate Governor launch gate missing")
    return {"gm_v_state": "HELD", "noncompensating_veto_guard": True, "separate_governor_launch": True}


PROBES = {
    "COMMAND": probe_command,
    "TECHNICAL_BOUNDARY": probe_technical_boundary,
    "RECON": probe_recon,
    "ANALYSIS": probe_analysis,
    "RUNTIME": probe_runtime,
    "QA": probe_qa,
    "BUILD_REPAIR_RESERVE": probe_build_repair_reserve,
    "GOVERNANCE": probe_governance,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capability", required=True, choices=sorted(PROBES))
    args = ap.parse_args()
    detail = PROBES[args.capability]()
    marker = f"PASS_GM_IV_RUNTIME_CAPABILITY_{args.capability}"
    print(json.dumps({"result": marker, "capability": args.capability, "detail": detail}, sort_keys=True))
    print(marker)


if __name__ == "__main__":
    main()
