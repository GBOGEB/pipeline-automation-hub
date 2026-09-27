#!/usr/bin/env python3
import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "mission-control" / "v2"
OFFICIAL_REGISTER = ROOT / "mission-control" / "OFFICIAL_MISSION_REGISTER_v1.yaml"
LEGACY_REGISTER = ROOT / "mission-control" / "qps-triage-ultra" / "mission_registry.yaml"

OFFICIAL_REGISTER_SECTIONS = {
    "canonical_grand_missions",
    "variants",
    "horizontal_missions",
    "local_missions",
}
LEGACY_REGISTER_SECTIONS = {"active_missions", "expansion"}
EXPLICIT_CONTROL_MISSION_IDS = {
    "GM-DMAIC-EVOLUTION-T7-T14-T21-20260926",
    "MC-EVO-02",
}
EXPECTED_COLLISION_MATRIX = {
    "MC": {
        "control_plane": "MISSION_CONTROL",
        "other_domain": "MONTE_CARLO",
        "canonical_other": ["MONTE_CARLO", "MC_SIM"],
        "bare_new_use": "FORBIDDEN_FOR_OTHER_DOMAIN",
    },
    "MIP": {
        "control_plane": "MODERNIZE_INNOVATE_PERPETUATE",
        "other_domain": "MIXED_INTEGER_PROGRAMMING",
        "canonical_other": ["MIXED_INTEGER_PROGRAMMING", "MILP", "MIP_OPT"],
        "bare_new_use": "FORBIDDEN_FOR_OTHER_DOMAIN",
    },
    "COV": {
        "control_plane": "DEPRECATED_AMBIGUOUS",
        "other_domain": "COVARIANCE_OR_CODE_COVERAGE",
        "canonical_other": ["MCOV", "CODE_COVERAGE", "COVARIANCE", "COV_MAT"],
        "bare_new_use": "FORBIDDEN",
    },
    "CI": {
        "control_plane": "CONTEXTUAL_LEGACY",
        "other_domain": "CONFIDENCE_INTERVAL_OR_CONTINUOUS_INTEGRATION",
        "canonical_other": ["CI_PIPELINE", "CONTINUOUS_INTEGRATION", "CONFIDENCE_INTERVAL", "CI_STAT"],
        "bare_new_use": "QUALIFY",
    },
    "PR": {
        "control_plane": "PULL_REQUEST",
        "other_domain": "PRECISION_RECALL",
        "canonical_other": ["PRECISION_RECALL", "PR_CURVE"],
        "bare_new_use": "PR_RESERVED_FOR_PULL_REQUEST_IN_CONTROL_PLANE",
    },
    "GM": {
        "control_plane": "GRAND_MISSION",
        "other_domain": "GEOMETRIC_MEAN",
        "canonical_other": ["GEOMETRIC_MEAN", "GM_STAT"],
        "bare_new_use": "GM_RESERVED_FOR_GRAND_MISSION_IN_CONTROL_PLANE",
    },
    "PC1": {
        "control_plane": "PCA_PRINCIPAL_COMPONENT_1",
        "other_domain": "3PC_METHOD_TOKEN",
        "canonical_other": ["3PC"],
        "bare_new_use": "NO_COLLISION_WHEN_3PC_REMAINS_ATOMIC_TOKEN",
    },
}

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

def _clean_yaml_scalar(value):
    return value.strip().strip(",}").strip().strip("'").strip('"')

def yaml_list_ids(path, sections):
    """Extract two-space list-item ids from selected dependency-free YAML sections."""
    ids = set()
    section = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent == 0:
            section = stripped[:-1] if stripped.endswith(":") else None
            continue
        if section not in sections or indent != 2 or not stripped.startswith("- "):
            continue
        body = stripped[2:].strip()
        if body.startswith("{"):
            body = body[1:].lstrip()
        if not body.startswith("id:"):
            continue
        value = body[3:].split(",", 1)[0]
        mission_id = _clean_yaml_scalar(value)
        if mission_id:
            ids.add(mission_id)
    return ids

def yaml_mapping_keys(path, sections):
    """Extract two-space mapping keys from selected dependency-free YAML sections."""
    ids = set()
    section = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent == 0:
            section = stripped[:-1] if stripped.endswith(":") else None
            continue
        if section not in sections or indent != 2 or ":" not in stripped:
            continue
        key = stripped.split(":", 1)[0].strip()
        if key and all(ch.isalnum() or ch in "._-" for ch in key):
            ids.add(key)
    return ids

def source_mission_ids():
    return (
        yaml_list_ids(OFFICIAL_REGISTER, OFFICIAL_REGISTER_SECTIONS)
        | yaml_mapping_keys(LEGACY_REGISTER, LEGACY_REGISTER_SECTIONS)
        | EXPLICIT_CONTROL_MISSION_IDS
    )

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
    matrix_rows = g.get("cross_domain_collision_matrix", [])
    matrix_tokens = [row.get("token") for row in matrix_rows]
    req(len(matrix_tokens) == len(set(matrix_tokens)), "cross-domain collision matrix contains duplicate token rows")
    req(set(matrix_tokens) == set(EXPECTED_COLLISION_MATRIX), "cross-domain collision matrix token set drift")
    for token, expected in EXPECTED_COLLISION_MATRIX.items():
        matches = [row for row in matrix_rows if row.get("token") == token]
        if len(matches) != 1:
            continue
        actual = dict(matches[0])
        actual.pop("token", None)
        req(actual == expected, f"cross-domain collision matrix mapping drift: {token}")
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
    required_core = set(c["metrics"]["required_core"])
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
        metrics = row.get("metrics", {})
        core = metrics.get("core")
        req(isinstance(core, dict), f"{row.get('mission_id')}: metrics.core must be an object")
        if isinstance(core, dict):
            missing_core = required_core - set(core)
            extra_core = set(core) - required_core
            req(not missing_core, f"{row.get('mission_id')}: missing required core metrics {sorted(missing_core)}")
            req(not extra_core, f"{row.get('mission_id')}: mission-specific metrics must live under metrics.custom {sorted(extra_core)}")
        req(isinstance(metrics.get("custom", {}), dict), f"{row.get('mission_id')}: metrics.custom must be an object")
        req(row.get("authority_transfer") is False, f"{row.get('mission_id')}: unexpected authority transfer")
    req(len(ids) == len(set(ids)), "duplicate mission_id in current census")
    scope = s.get("census_scope") or {}
    expected_ids = scope.get("expected_mission_ids") or []
    req(scope.get("normalized_rows") == len(ids), "census normalized_rows mismatch")
    req(set(expected_ids) == set(ids), "census expected_mission_ids mismatch")
    bound_ids = source_mission_ids()
    req(set(ids) == bound_ids, f"census mission IDs drift from bound registries: missing={sorted(bound_ids - set(ids))} extra={sorted(set(ids) - bound_ids)}")
    req(set(expected_ids) == bound_ids, "census expected_mission_ids drift from bound registries")
    scope_sources = set(scope.get("sources") or [])
    req("mission-control/OFFICIAL_MISSION_REGISTER_v1.yaml" in scope_sources, "official mission register missing from census sources")
    req("mission-control/qps-triage-ultra/mission_registry.yaml" in scope_sources, "legacy mission registry missing from census sources")

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
    bad = copy.deepcopy(bundle)
    bad["glossary"]["cross_domain_collision_matrix"][0]["canonical_other"] = ["UNRELATED_TOKEN"]
    assert validate_bundle(bad), "self-test failed to detect collision mapping corruption"
    bad = copy.deepcopy(bundle)
    bad["glossary"]["cross_domain_collision_matrix"].append(copy.deepcopy(bad["glossary"]["cross_domain_collision_matrix"][0]))
    assert validate_bundle(bad), "self-test failed to detect duplicate collision token"
    bad = copy.deepcopy(bundle)
    bad["status"]["missions"] = [row for row in bad["status"]["missions"] if row.get("mission_id") != "GM-I"]
    bad["status"]["census_scope"]["expected_mission_ids"] = [mid for mid in bad["status"]["census_scope"]["expected_mission_ids"] if mid != "GM-I"]
    bad["status"]["census_scope"]["normalized_rows"] -= 1
    assert validate_bundle(bad), "self-test failed to detect source-registry census omission"
    bad = copy.deepcopy(bundle)
    bad["status"]["missions"][0]["metrics"]["core"].pop(next(iter(required_metric for required_metric in bundle["contract"]["metrics"]["required_core"])))
    assert validate_bundle(bad), "self-test failed to detect missing core metric"

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
            "mission_core_metrics": "PASS" if not any("core metric" in e or "metrics.core" in e for e in errors) else "FAIL",
            "census_source_binding": "PASS" if not any("bound registr" in e or "census sources" in e for e in errors) else "FAIL",
            "collision_matrix": "PASS" if not any("collision matrix" in e for e in errors) else "FAIL",
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
