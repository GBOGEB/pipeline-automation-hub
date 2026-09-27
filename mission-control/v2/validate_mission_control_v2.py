#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "mission-control" / "v2"

FILES = {
    "current": V2 / "MISSION_CONTROL_CURRENT_v2.json",
    "glossary": V2 / "MC_GLOSSARY_TAXONOMY_v2.json",
    "methods": V2 / "MC_METHOD_PROFILE_REGISTRY_v1.json",
    "contract": V2 / "MC_MISSION_TELEMETRY_CONTRACT_v1.json",
    "status": V2 / "MC_MISSION_STATUS_CURRENT_v1.json",
    "plan": V2 / "MC_DMAIC_EVOLUTION_PLAN_v1.json",
}

def load(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def validate_bundle(bundle):
    errors = []
    g = bundle["glossary"]
    m = bundle["methods"]
    c = bundle["contract"]
    s = bundle["status"]
    p = bundle["plan"]
    cur = bundle["current"]

    def req(ok, msg):
        if not ok:
            errors.append(msg)

    req(g["reservations"]["MC"]["canonical_meaning"] == "MISSION_CONTROL", "MC must be reserved for Mission Control")
    req(g["reservations"]["MONTE_CARLO"]["forbidden_new_token"] == "MC", "Monte Carlo bare MC must be forbidden")
    req(set(g["reservations"]["MONTE_CARLO"]["permitted_machine_tokens"]) == {"MONTE_CARLO", "MC_SIM"}, "Monte Carlo tokens drift")
    req(g["reservations"]["COV"]["canonical_status"].startswith("DEPRECATED"), "bare COV must be deprecated")
    req(list(g["coverage_maturity"].keys()) == [f"MCOV-{i}" for i in range(6)], "MCOV levels must be exactly MCOV-0..MCOV-5")
    req(g["reservations"]["CONTROL"]["lifecycle_token"] == "CONTROLLED", "lifecycle CONTROL token must be CONTROLLED")
    req(g["reservations"]["MIP"]["canonical_meaning"] == "MODERNIZE_INNOVATE_PERPETUATE_IN_MISSION_CONTROL", "MIP control-plane meaning drift")
    req("CONFIDENCE_INTERVAL" in g["reservations"]["CI"]["collision"], "CI confidence-interval collision missing")
    req("COVARIANCE" in g["reservations"]["COV"]["collision"], "COV covariance collision missing")
    req(g["reservations"]["GM"]["canonical_meaning"] == "GRAND_MISSION_IN_MISSION_CONTROL", "GM control-plane meaning drift")
    matrix_tokens = {row.get("token") for row in g.get("cross_domain_collision_matrix", [])}
    req({"MC","MIP","COV","CI","PR","GM","PC1"}.issubset(matrix_tokens), "cross-domain collision matrix incomplete")
    req(g["identity_grammar"]["pull_request"] == "owner/name::PR<number>", "pull-request identity must be repository-qualified")
    req("mission_id" in g["identity_grammar"]["wave"], "wave identity must be mission-qualified")
    req("PULSE-" in g["identity_grammar"]["pulse"], "pulse identity must not rely on bare P1/P2/P3")

    req(m["supervisor"]["phases"] == ["DEFINE","MEASURE","ANALYZE","IMPROVE","CONTROL"], "DMAIC phase order drift")
    req(m["profiles"]["3PR"]["phases"] == ["REFRESH","PROBE","RANK"], "3PR drift")
    req(m["profiles"]["3PC"]["phases"] == ["PREPARE","PROVE","COMMIT"], "3PC drift")
    req(m["mip"]["admission"] == "CONDITIONAL", "MIP must remain conditional")
    req(m["historical_compatibility"]["no_bulk_rewrite"] is True, "historical rewrite forbidden")

    required_dims = {"status","progress","health","coverage","metrics","crew","runners","lifecycle","todo"}
    req(set(c["required_dimensions"]) == required_dims, "telemetry dimensions drift")
    req(c["execution_hierarchy"]["order"] == ["MISSION","SPRINT","WAVE","PULSE","RUN"], "execution hierarchy drift")

    ids = []
    for row in s["missions"]:
        ids.append(row.get("mission_id"))
        missing = required_dims - set(row)
        req(not missing, f"{row.get('mission_id')}: missing dimensions {sorted(missing)}")
        req(row.get("coverage", {}).get("maturity") in {f"MCOV-{i}" for i in range(6)}, f"{row.get('mission_id')}: invalid MCOV")
        pv = row.get("progress", {}).get("value")
        req(pv is None or (isinstance(pv, (int,float)) and 0 <= pv <= 1), f"{row.get('mission_id')}: progress outside 0..1")
        req(row.get("health", {}).get("signal") in {"GREEN","AMBER","RED","GREY"}, f"{row.get('mission_id')}: health invalid")
        req(row.get("lifecycle", {}).get("state") in set(c["lifecycle"]["states"]), f"{row.get('mission_id')}: lifecycle invalid")
        req(row.get("authority_transfer") is False, f"{row.get('mission_id')}: unexpected authority transfer")
    req(len(ids) == len(set(ids)), "duplicate mission_id in current census")
    scope = s.get("census_scope") or {}
    expected_ids = scope.get("expected_mission_ids") or []
    req(scope.get("normalized_rows") == len(ids), "census normalized_rows mismatch")
    req(set(expected_ids) == set(ids), "census expected_mission_ids mismatch")
    for required_id in ("M01","M02A","M02B","M03","M04","CLOUD16"):
        req(required_id in ids, f"legacy mission missing from normalized census: {required_id}")

    req(p["dmaic"]["DEFINE"]["state"] == "PASS", "DMAIC DEFINE not frozen")
    req(p["dmaic"]["MEASURE"]["state"] == "PASS_BASELINE", "DMAIC MEASURE baseline missing")
    req(p["dmaic"]["ANALYZE"]["state"] == "PASS", "DMAIC ANALYZE missing")
    req(p["dmaic"]["CONTROL"]["state"].startswith("CONTROL_LOOP_"), "DMAIC CONTROL loop state invalid")

    canonical = cur["canonical"]
    for key, rel in canonical.items():
        if key == "workflow":
            path = ROOT / rel
        else:
            path = ROOT / rel
        req(path.exists(), f"CURRENT pointer missing target: {rel}")

    return errors

def self_test(bundle):
    import copy
    bad = copy.deepcopy(bundle)
    bad["glossary"]["reservations"]["MC"]["canonical_meaning"] = "MONTE_CARLO"
    assert validate_bundle(bad), "self-test failed to detect MC collision"
    bad = copy.deepcopy(bundle)
    bad["status"]["missions"][0].pop("health")
    assert validate_bundle(bad), "self-test failed to detect missing mission dimension"
    bad = copy.deepcopy(bundle)
    bad["methods"]["mip"]["admission"] = "MANDATORY"
    assert validate_bundle(bad), "self-test failed to detect mandatory MIP regression"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit-receipt")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    bundle = {k: load(v) for k, v in FILES.items()}
    errors = validate_bundle(bundle)
    if args.self_test:
        self_test(bundle)

    receipt = {
        "schema": "missioncontrol.v2.validation_receipt.v1",
        "source_sha": os.environ.get("MC_SOURCE_SHA") or os.environ.get("GITHUB_SHA"),
        "result": "PASS" if not errors else "FAIL",
        "checks": {
            "namespace_MC": "PASS" if not any("MC must" in e for e in errors) else "FAIL",
            "monte_carlo_tokens": "PASS" if not any("Monte Carlo" in e for e in errors) else "FAIL",
            "mcov_levels": "PASS" if not any("MCOV" in e for e in errors) else "FAIL",
            "method_profiles": "PASS" if not any(x in e for e in errors for x in ["3PR","3PC","MIP","DMAIC"]) else "FAIL",
            "mission_dimensions": "PASS" if not any("dimensions" in e for e in errors) else "FAIL",
            "current_pointer": "PASS" if not any("CURRENT pointer" in e for e in errors) else "FAIL",
        },
        "mission_rows": len(bundle["status"]["missions"]),
        "errors": errors,
        "authority_transfer": False,
        "formal_credit_delta": 0,
        "engineering_credit_delta": 0,
    }

    print(json.dumps(receipt, indent=2, sort_keys=True))
    if args.emit_receipt:
        Path(args.emit_receipt).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raise SystemExit(0 if not errors else 1)

if __name__ == "__main__":
    main()
