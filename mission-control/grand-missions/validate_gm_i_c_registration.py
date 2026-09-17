#!/usr/bin/env python3
"""Fail-closed registration validator for GM-I-C cross-agent Drive federation."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
MISSION_CONTROL = ROOT / "GM-I-C_CROSS_AGENT_DRIVE_FEDERATION_CONTROL_v0.1.yaml"
CREW = ROOT / "GM-I-C_CREW_ALLOCATION_v0.1.yaml"
OFFICIAL = ROOT.parent / "OFFICIAL_MISSION_REGISTER_v1.yaml"
CANONICAL = ROOT / "GRAND_MISSION_REGISTRY.json"
CANONICAL_GM_IDS = ["GM-I", "GM-II", "GM-III", "GM-IV", "GM-V"]
PR9_MERGE = "f9ea9f45942ce50b5f2fcad626ba8b59fa97ac71"
PR10_HEAD = "1d831a66a258bcd1b13d432805e8c60b52f6c7ad"
PR10_MERGE = "2d3b82443ae90b00971e3c71433a9c8ad47072a8"
PR11_HEAD = "8b6d0db501db93fdf42a4c06a7ba9e7094470b21"
EXPECTED_CONTROL = "mission-control/grand-missions/GM-I-C_CROSS_AGENT_DRIVE_FEDERATION_CONTROL_v0.1.yaml"
EXPECTED_CREW = "mission-control/grand-missions/GM-I-C_CREW_ALLOCATION_v0.1.yaml"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> None:
    control = load_yaml(MISSION_CONTROL)
    crew = load_yaml(CREW)
    official = load_yaml(OFFICIAL)
    canonical_registry = load_json(CANONICAL)

    canonical = [row["id"] for row in official["canonical_grand_missions"]]
    require(canonical == CANONICAL_GM_IDS, f"canonical GM namespace changed: {canonical}")
    canonical_ids = [row["id"] for row in canonical_registry["grand_missions"]]
    require(canonical_ids == CANONICAL_GM_IDS, f"canonical JSON GM namespace changed: {canonical_ids}")

    variants = {row["id"]: row for row in official.get("variants", [])}
    require("GM-I-B" in variants, "GM-I-B disappeared")
    require("GM-I-C" in variants, "GM-I-C is not registered")
    gm_ic = variants["GM-I-C"]

    gm_i = next(row for row in canonical_registry["grand_missions"] if row["id"] == "GM-I")
    canonical_variants = {row["id"]: row for row in gm_i.get("variants", [])}
    require(set(canonical_variants) == {"GM-I-A", "GM-I-B", "GM-I-C"}, f"canonical GM-I variants invalid: {sorted(canonical_variants)}")
    canonical_ic = canonical_variants["GM-I-C"]

    require(gm_ic["parent"] == "GM-I", "GM-I-C parent must remain GM-I")
    require(gm_ic["number"] == "1-C", "GM-I-C number must remain 1-C")
    require(gm_ic["type"] == "GRAND_MISSION_VARIANT", "GM-I-C must remain a governed variant")
    require(gm_ic["provider"] == "GBOGEB/GEMINI", "official provider drift")
    require(gm_ic["authority_transfer"] is False, "GM-I-C authority transfer must remain false")
    require(gm_ic["formal_credit_delta"] == 0, "GM-I-C formal credit delta must remain zero")
    require(gm_ic["official_control"] == EXPECTED_CONTROL, "official control path drift")
    require(gm_ic["crew_allocation"] == EXPECTED_CREW, "official crew path drift")
    require("WITHHELD" in gm_ic["implementation_evidence"]["hosted_drive_pass"], "hosted Drive PASS must remain withheld until observed")
    require(gm_ic["first_red"] == "IC3_AUTH_REAL_HOSTED_GT0_STEP_DRIVE_INGRESS_PASS", "unexpected first red")

    evidence = gm_ic["implementation_evidence"]
    require(evidence["gemini_hooks_pr"] == 9, "Gemini hooks PR binding drift")
    require(evidence["gemini_hooks_merge_sha"] == PR9_MERGE, "Gemini hooks merge drift")
    require(evidence["drive_ingress_pr"] == 10, "Drive ingress PR binding drift")
    require(evidence["drive_ingress_head_sha"] == PR10_HEAD, "Drive ingress PR10 head drift")
    require(evidence["drive_ingress_merge_sha"] == PR10_MERGE, "Drive ingress PR10 merge drift")
    require(evidence["drive_ingress_hardening_pr"] == 11, "IC3 hardening PR binding drift")
    require(evidence["drive_ingress_hardening_head_sha"] == PR11_HEAD, "IC3 hardening head drift")

    require(canonical_ic["repository"] == gm_ic["provider"], "official/canonical provider mismatch")
    require(canonical_ic["state"] == gm_ic["state"], "official/canonical GM-I-C state mismatch")
    require(canonical_ic["provider_pr"] == evidence["gemini_hooks_pr"], "canonical provider PR mismatch")
    require(canonical_ic["provider_merge_sha"] == evidence["gemini_hooks_merge_sha"], "canonical provider merge mismatch")
    require(canonical_ic["drive_ingress_pr"] == evidence["drive_ingress_pr"], "canonical PR10 number mismatch")
    require(canonical_ic["drive_ingress_exact_head_sha"] == evidence["drive_ingress_head_sha"], "canonical PR10 head mismatch")
    require(canonical_ic["drive_ingress_merge_sha"] == evidence["drive_ingress_merge_sha"], "canonical PR10 merge mismatch")
    require(canonical_ic["drive_ingress_hardening_pr"] == evidence["drive_ingress_hardening_pr"], "canonical PR11 number mismatch")
    require(canonical_ic["drive_ingress_hardening_exact_head_sha"] == evidence["drive_ingress_hardening_head_sha"], "canonical PR11 head mismatch")
    require(canonical_ic["hosted_drive_pass"] == evidence["hosted_drive_pass"], "canonical hosted-pass state mismatch")
    require(canonical_ic["official_control"] == gm_ic["official_control"] == EXPECTED_CONTROL, "canonical control path mismatch")
    require(canonical_ic["crew_allocation"] == gm_ic["crew_allocation"] == EXPECTED_CREW, "canonical crew path mismatch")
    require(canonical_ic["authority_transfer"] is False, "canonical GM-I-C authority transfer weakened")
    require(canonical_ic["formal_credit_delta"] == 0, "canonical GM-I-C formal credit weakened")
    require(canonical_ic["first_red"] == gm_ic["first_red"], "official/canonical GM-I-C first-red mismatch")

    gm_iii = next(row for row in canonical_registry["grand_missions"] if row["id"] == "GM-III")
    require("GBOGEB/GEMINI" in gm_iii.get("children", []), "GM-III GEMINI frontier history must remain preserved")

    require(control["mission_id"] == "GM-I-C", "control mission ID mismatch")
    require(control["parent"] == "GM-I", "control parent mismatch")
    require(control["authority_transfer"] is False, "control authority transfer weakened")
    require(control["formal_credit_delta"] == 0, "control formal credit weakened")
    require(control["first_red"]["gate"] == "IC3_AUTH", "control first-red gate mismatch")
    require(control["first_red"]["owner"] == "S03_DOCKMASTER", "IC3 owner must remain Dockmaster")

    cp = control["provider_evidence"]
    require(cp["gemini_hooks_pr"]["pr"] == evidence["gemini_hooks_pr"], "control PR9 number mismatch")
    require(cp["gemini_hooks_pr"]["merge_sha"] == evidence["gemini_hooks_merge_sha"], "control PR9 merge mismatch")
    require(cp["drive_ingress_pr"]["pr"] == evidence["drive_ingress_pr"], "control PR10 number mismatch")
    require(cp["drive_ingress_pr"]["exact_head_sha"] == evidence["drive_ingress_head_sha"], "control PR10 head mismatch")
    require(cp["drive_ingress_pr"]["merge_sha"] == evidence["drive_ingress_merge_sha"], "control PR10 merge mismatch")
    require(cp["drive_ingress_hardening_pr"]["pr"] == evidence["drive_ingress_hardening_pr"], "control PR11 number mismatch")
    require(cp["drive_ingress_hardening_pr"]["exact_head_sha"] == evidence["drive_ingress_hardening_head_sha"], "control PR11 head mismatch")

    gates = {row["id"]: row for row in control["mission_gates"]}
    require(list(gates) == [f"IC{i}_{name}" for i, name in enumerate([
        "REGISTER", "PROVIDER", "BRIDGE", "AUTH", "CONSUMER_A",
        "CONSUMER_B", "PARITY", "ROUNDTRIP", "ADVERSARIAL", "CONTROL",
    ])], "IC0..IC9 gate order changed")
    require(gates["IC3_AUTH"]["current"] == "FIRST_RED", "IC3 must remain first red before runtime proof")
    require(gates["IC5_CONSUMER_B"]["current"] == "NOT_STARTED", "second consumer must not be fabricated")
    require(gates["IC9_CONTROL"]["current"] == "NOT_STARTED", "CONTROL cannot be pre-credited")

    active_ids = {row["crew_id"] for row in crew["active_crew"]}
    require(active_ids == {"U01", "U02", "U04", "U06", "U08", "S01", "S03", "S06"}, f"unexpected active crew: {sorted(active_ids)}")
    require(crew["first_red_routing"]["zero_step_or_no_runner"]["owner"] == "S03", "zero-step must route to Dockmaster")
    forbidden = set(crew["first_red_routing"]["zero_step_or_no_runner"]["forbidden_initial_roles"])
    require(forbidden == {"S02", "S05"}, "Doctor/Engineer zero-step guard weakened")

    conceptual = {row["crew_id"]: row for row in crew["scout_reader_policy"]["conceptual_roles"]}
    require(conceptual["C01"]["control_eligible"] is False, "conceptual Scout cannot be CONTROL eligible")
    require(conceptual["C02"]["control_eligible"] is False, "conceptual Reader cannot be CONTROL eligible")

    workers = {row["id"]: row for row in crew["runtime_workers"]}
    for worker_id in ["GOOGLE_WIF_PRINCIPAL", "GOOGLE_DRIVE_BRIDGE", "GITHUB_HOSTED_RUNNER", "CHATGPT_DRIVE_CONSUMER", "SECOND_EXTERNAL_CONSUMER"]:
        require(workers[worker_id]["is_crew"] is False, f"{worker_id} must not be treated as crew")

    result = {
        "result": "PASS_GM_I_C_REGISTRATION",
        "canonical_grand_missions": canonical,
        "variant": "GM-I-C",
        "canonical_registry_bound": True,
        "exact_evidence_and_paths_bound": True,
        "gm_iii_gemini_history_preserved": True,
        "drive_ingress_pr10_merge_bound": PR10_MERGE,
        "ic3_hardening_pr11_head_bound": PR11_HEAD,
        "gate_count": len(gates),
        "active_crew_count": len(active_ids),
        "first_red": gm_ic["first_red"],
        "hosted_drive_pass": evidence["hosted_drive_pass"],
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
