#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, statistics
from pathlib import Path

def fail(msg: str) -> None:
    raise SystemExit("R3_DMAIC_KPI_FAIL: " + msg)

def close(a: float, b: float, eps: float = 1e-9) -> bool:
    return abs(a-b) <= eps

def compute(doc: dict) -> dict:
    prs = doc["population"]["prs"]
    lead = [int(x["merge_lead_seconds"]) for x in prs]
    primary = [x for x in prs if x["role"] == "PRIMARY"]
    repairs_needed = [x for x in primary if x["required_recursive_repair"]]
    defects = doc["observed_defect_classes"]
    before = doc["outcome_before"]
    current = doc["outcome_current"]
    def reduction(key: str) -> float:
        b, c = before[key], current[key]
        return 0.0 if b == 0 else (b-c)/b
    return {
        "pr_count": len(prs),
        "mean_merge_lead_seconds": statistics.mean(lead),
        "median_merge_lead_seconds": statistics.median(lead),
        "primary_pr_count": len(primary),
        "primary_prs_requiring_recursive_repair": len(repairs_needed),
        "historical_first_pass_closure_rate": 1.0 - len(repairs_needed)/len(primary),
        "defect_classes_observed": len(defects),
        "defect_classes_closed": sum(bool(x["closed"]) for x in defects),
        "repair_closure_yield": sum(bool(x["closed"]) for x in defects)/len(defects),
        "physical_prerequisite_reduction_fraction": reduction("physical_r3_prerequisites_open"),
        "first_red_reduction_fraction": reduction("first_red_cardinality"),
        "exact_environment_admission_delta": current["exact_environment_capsule_admitted"]-before["exact_environment_capsule_admitted"],
        "current_successor_binding_delta": current["active_successor_ingress_contract_bound"]-before["active_successor_ingress_contract_bound"],
        "stale_predecessor_active_delta": current["predecessor_only_target_active_for_current_r3"]-before["predecessor_only_target_active_for_current_r3"],
        "restart_v2_binding_delta": current["current_restart_v2_bound"]-before["current_restart_v2_bound"],
    }

def validate(doc: dict) -> dict:
    if doc.get("authority_transfer") is not False or doc.get("formal_credit_delta") != 0:
        fail("authority/credit guard changed")
    guards = doc["guards"]
    required_guards = {
        "r3_release_production_dov":"WITHHELD",
        "r4":"BLOCKED_NOT_NEXT",
        "issue_923":"RED_OWNER_ACTION",
        "gt_bdq_0":"RED_BLOCKED_ON_923_INFRA_PREEXECUTION",
        "canonical_gt_credit":"NONE",
        "authority_transfer":False,
        "formal_credit_delta":0,
    }
    if guards != required_guards:
        fail(f"guard drift: {guards}")
    got = compute(doc)
    exp = doc["expected_kpis"]
    for key, wanted in exp.items():
        actual = got[key]
        if isinstance(wanted, float):
            if not close(float(actual), wanted):
                fail(f"{key}: expected {wanted}, got {actual}")
        elif actual != wanted:
            fail(f"{key}: expected {wanted}, got {actual}")
    return got

def self_test(doc: dict) -> None:
    bad = copy.deepcopy(doc)
    bad["population"]["prs"][0]["merge_lead_seconds"] += 1
    try:
        validate(bad)
    except SystemExit:
        pass
    else:
        fail("self-test failed to reject KPI drift")
    bad = copy.deepcopy(doc)
    bad["guards"]["r4"] = "PASS"
    try:
        validate(bad)
    except SystemExit:
        pass
    else:
        fail("self-test failed to reject authority/gate drift")

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--contract",required=True)
    ap.add_argument("--out")
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    doc=json.loads(Path(a.contract).read_text(encoding="utf-8"))
    got=validate(doc)
    if a.self_test:
        self_test(doc)
    receipt={
        "schema":"missioncontrol.hm01.r3.dmaic_kpi_receipt.v1",
        "status":"PASS_MEASURED_KPI_CONTRACT",
        "wave":doc["wave"],
        "computed_kpis":got,
        "targets":doc["next_targets"],
        "guards":doc["guards"],
        "authority_transfer":False,
        "formal_credit_delta":0,
        "next":"W278_MIP_I_PREMERGE_INVARIANT_DETECTION",
    }
    payload=json.dumps(receipt,indent=2,sort_keys=True)+"\n"
    if a.out:
        Path(a.out).write_text(payload,encoding="utf-8")
    print(payload,end="")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
