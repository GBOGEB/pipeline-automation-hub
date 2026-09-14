#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Only stages with a complete shape contract may be accepted by the generic
# fleet validator. Forward stages remain fail-closed until their separate
# Governor defines and proves the full stage-specific invariants.
SUPPORTED_GM_IV_STATES = {
    "HELD",
    "STAGED_ACTIVE_RECON_2_OF_8",
    "STAGED_ACTIVE_PILOT_2_OF_8",
}
FORWARD_GM_IV_STATES_REQUIRING_GOVERNOR = {
    "STAGED_ACTIVE_RECON_4_OF_8",
    "ACTIVE_8_OF_8",
}


def load(name):
    with (ROOT / name).open("r", encoding="utf-8") as f:
        return json.load(f)


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def canonical_digest(obj):
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    registry = load("GRAND_MISSION_REGISTRY.json")
    roles = load("CREW_ROLE_REGISTRY.json")
    machine = load("CREW_STATE_MACHINE.json")
    genealogy = load("GM_GENEALOGY.json")
    city = load("MISSION_CITY_GRAPH.json")
    bridge = load("CREW_REX_BIDIRECTIONAL_CONTRACT.json")
    telemetry = load("FLEET_TELEMETRY_SCHEMA.json")
    bt = load("FLEET_BT_EVIDENCE_SCHEMA.json")
    ledger = load("CREW_REX_LEDGER.json")
    fixtures = load("VALIDATION_FIXTURES.json")

    checks = []

    def ok(name, condition, detail=""):
        require(condition, f"{name}: {detail}")
        checks.append({"check": name, "result": "PASS", "detail": detail})

    missions = registry["grand_missions"]
    ids = [m["id"] for m in missions]
    ok("01_canonical_gm_registry", ids == ["GM-I", "GM-II", "GM-III", "GM-IV", "GM-V"], str(ids))
    ok("02_scaling_sequence", [m["frontier_count"] for m in missions] == [1, 2, 4, 8, 16], "1-2-4-8-16")

    role_ids = [r["id"] for r in roles["roles"]]
    required_roles = {
        "SCOUT", "READER", "AMBASSADOR", "SCIENTIST", "ENGINEER", "SMOKER",
        "DOCTOR", "DOCKMASTER", "QA", "ANALYST", "PM", "TM", "GOVERNOR",
        "ORCHESTRATOR",
    }
    ok("03_crew_role_registry", set(role_ids) == required_roles and len(role_ids) == len(set(role_ids)), f"roles={len(role_ids)}")

    allowed = {tuple(x) for x in machine["allowed_transitions"]}
    for fixture in fixtures["crew_transitions"]:
        pair = (fixture["from"], fixture["to"])
        observed = "ALLOW" if pair in allowed else "REJECT"
        require(observed == fixture["expected"], f"transition fixture {pair} expected {fixture['expected']} got {observed}")
    for pair in machine["illegal_transitions"]:
        if pair[0] in machine["states"] and pair[1] in machine["states"]:
            require(tuple(pair) not in allowed, f"illegal transition present in allowed list: {pair}")
    ok("04_activation_return_state_machine", True, f"fixtures={len(fixtures['crew_transitions'])}")

    gm = {m["id"]: m for m in missions}
    ok("05_gm_i_genealogy", genealogy["missions"]["GM-I"]["observed_returned_workers"] == ["Scout_1", "Scout_2", "Scout_3", "Reader_1", "Reader_2"], "observed returned crew bound")
    ok("06_gm_ii_two_child_genealogy", len(genealogy["missions"]["GM-II"]["children"]) == 2 and len(gm["GM-II"]["children"]) == 2, "two children")
    ok("07_gm_iii_four_frontier_genealogy", len(genealogy["missions"]["GM-III"]["frontiers"]) == 4 and len(gm["GM-III"]["children"]) == 4, "four frontiers")

    gm_iv = gm["GM-IV"]
    gm_iv_state_ok = gm_iv["state"] in SUPPORTED_GM_IV_STATES
    gm_iv_stage_ok = True
    if gm_iv["state"] == "STAGED_ACTIVE_RECON_2_OF_8":
        gm_iv_stage_ok = (
            gm_iv.get("activation_stage") == "RECON_2_OF_8"
            and gm_iv.get("candidate_frontiers") == ["GM-IV-F01", "GM-IV-F02"]
            and gm_iv.get("unfilled_frontier_slots") == [
                "GM-IV-F03", "GM-IV-F04", "GM-IV-F05", "GM-IV-F06",
                "GM-IV-F07", "GM-IV-F08",
            ]
        )
    elif gm_iv["state"] == "STAGED_ACTIVE_PILOT_2_OF_8":
        gm_iv_stage_ok = (
            gm_iv.get("activation_stage") == "PILOT_2_OF_8"
            and gm_iv.get("candidate_frontiers") == [
                "GM-IV-F01", "GM-IV-F02", "GM-IV-F03", "GM-IV-F04"
            ]
            and gm_iv.get("controlled_pilot_frontiers") == ["GM-IV-F01", "GM-IV-F03"]
            and gm_iv.get("reference_frontiers") == ["GM-IV-F02", "GM-IV-F04"]
            and gm_iv.get("unfilled_frontier_slots") == [
                "GM-IV-F05", "GM-IV-F06", "GM-IV-F07", "GM-IV-F08"
            ]
        )
    ok(
        "08_gm_iv_8_no_fabrication_or_ungoverned_promotion",
        gm_iv_state_ok
        and gm_iv_stage_ok
        and gm_iv["frontier_count"] == 8
        and gm_iv["children"] == [],
        f"state={gm_iv['state']} frontier_count=8 children=0",
    )
    ok("09_gm_v_held_16_no_fabrication", gm["GM-V"]["state"] == "HELD" and gm["GM-V"]["frontier_count"] == 16 and gm["GM-V"]["children"] == [], "HELD/16 children=0")

    city_nodes = {n["id"] for n in city["nodes"]}
    city_state_matches = city.get("mission_states", {}).get("GM-IV") == gm_iv["state"]
    ok("10_mission_city_graph", set(ids).issubset(city_nodes) and {"DOW", "KEB", "QPS", "RUNTIME_DOCK", "MISSION_CONTROL"}.issubset(city_nodes) and city_state_matches, f"nodes={len(city_nodes)} gm_iv_state_sync={city_state_matches}")

    prefixes = registry["namespace"]
    prefix_values = [prefixes["grand_mission_prefix"], prefixes["horizontal_mission_prefix"], prefixes["local_mission_prefix"]]
    ok("11_namespace_disjointness", len(prefix_values) == len(set(prefix_values)) and all(i.startswith("GM-") for i in ids), str(prefix_values))

    routing = {r["first_red"]: r for r in fixtures["routing"]}
    require("DOCKMASTER" in routing["HABITAT"]["expected_roles"] and "DOCTOR" in routing["HABITAT"]["forbidden_roles"], "zero-step routing fixture malformed")
    require("DOCTOR" in routing["APPLICATION"]["expected_roles"] and routing["APPLICATION"]["executed_steps"] > 0, "application routing fixture malformed")
    ok("12_illegal_crew_routing_guard", True, "zero-step=>Dockmaster; application>0=>Doctor+Engineer")

    verbs = set(bridge["verbs"].keys())
    ok("13_bidirectional_rex_contract", {"LEARN", "IMPROVE", "UPDATE", "REPAIR", "ASSIMILATE", "PRUNE", "BRIDGE"}.issubset(verbs) and bridge["authority_transfer"] is False, "learning loop bound")

    events = ledger["events"]
    event_ids = {e["event_id"] for e in events}
    for e in events:
        if e["direction"] == "CREW_TO_MC":
            children = [x for x in events if x.get("causal_parent") == e["event_id"] and x["direction"] == "MC_TO_CREW"]
            require(children, f"crew report lacks Mission Control return: {e['event_id']}")
        if "causal_parent" in e:
            require(e["causal_parent"] in event_ids, f"missing causal parent {e['causal_parent']}")
    ok("14_crew_rex_bidirectional_ledger", True, f"events={len(events)}")

    pca_gate = telemetry["pca_gate"]
    ok("15_measured_fleet_telemetry_schema", pca_gate["evidence_class_required"] == "MEASURED" and pca_gate["minimum_comparable_rows"] >= 3, "future PCA fail-closed")
    bt_gate = bt["bt_gate"]
    ok("16_observed_pairwise_bt_schema", bt_gate["minimum_pairs"] >= 2 and bt_gate["requires_connected_comparison_graph"] and bt_gate["forbid_synthetic_pair_credit"], "future BT fail-closed")

    source_sha = os.environ.get("SOURCE_SHA", os.environ.get("GITHUB_SHA", "LOCAL_UNBOUND"))
    run_id = os.environ.get("GITHUB_RUN_ID", "LOCAL")
    repo = os.environ.get("GITHUB_REPOSITORY", "GBOGEB/pipeline-automation-hub")
    ref = os.environ.get("GITHUB_REF", "LOCAL")

    receipt = {
        "schema": "qps.gm_fleet_02b_runtime_receipt.v1",
        "wave": "GM-FLEET-02B",
        "repo": repo,
        "source_sha": source_sha,
        "ref": ref,
        "run_id": run_id,
        "executed_steps_gt0": True,
        "static_materialisation": "PASS_12_OF_12",
        "validation_check_count": len(checks),
        "validation_checks": checks,
        "crew_rex_bidirectional": "PASS",
        "pca_runtime_gate": "DEFER_NO_COMPARABLE_MEASURED_GM_I_TO_V_ROWS",
        "bt_runtime_gate": "DEFER_NO_CONNECTED_OBSERVED_GM_PAIRWISE_GRAPH",
        "authority_transfer": False,
        "input_digest_sha256": canonical_digest({
            "registry": registry,
            "roles": roles,
            "machine": machine,
            "genealogy": genealogy,
            "city": city,
            "bridge": bridge,
            "telemetry": telemetry,
            "bt": bt,
            "ledger": ledger,
            "fixtures": fixtures,
        }),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result": "PASS_GM_FLEET_02B", "checks": len(checks), "source_sha": source_sha, "pca": receipt["pca_runtime_gate"], "bt": receipt["bt_runtime_gate"]}, sort_keys=True))


if __name__ == "__main__":
    main()
