#!/usr/bin/env python3
"""Validate QPS TRIAGE fleet receipts without transferring engineering authority."""
from __future__ import annotations
import argparse, copy, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTRACT = json.loads((ROOT / "receipt_contract.json").read_text(encoding="utf-8"))
GATE = json.loads((ROOT / "federation_gate.json").read_text(encoding="utf-8"))
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def structural_errors():
    errors = []
    if CONTRACT.get("receipt_schema") != "qps-fleet-receipt/v1":
        errors.append("receipt_schema")
    if GATE.get("mode") != "ALL_REQUIRED":
        errors.append("gate_mode")
    if GATE.get("authority_transfer") is not False:
        errors.append("authority_transfer")
    nodes = GATE.get("required_nodes", {})
    for name in ("ULTRA", "M02A", "M02B"):
        if name not in nodes:
            errors.append(f"missing_node:{name}")
    return errors


def receipt_errors(receipt, node_name):
    errors = []
    node = GATE["required_nodes"][node_name]
    for key in CONTRACT["required_top_level"]:
        if key not in receipt:
            errors.append(f"missing:{key}")
    execution = receipt.get("execution", {})
    for key in CONTRACT["required_execution"]:
        if key not in execution:
            errors.append(f"missing:execution.{key}")
    if receipt.get("schema") != CONTRACT["receipt_schema"]:
        errors.append("schema")
    if receipt.get("mission_id") != node_name:
        errors.append("mission_id")
    if receipt.get("repo") != node.get("repo"):
        errors.append("repo")
    sha = receipt.get("source_sha", "")
    if not SHA40.fullmatch(sha):
        errors.append("source_sha_format")
    target = node.get("target_head_sha")
    if target and sha != target:
        errors.append("source_sha_target_mismatch")
    if receipt.get("authority_transfer") is not False:
        errors.append("authority_transfer")
    if receipt.get("engineering_acceptance") is not False:
        errors.append("engineering_acceptance")
    if execution.get("steps_gt0") is not True:
        errors.append("steps_gt0")
    if execution.get("outcome") not in CONTRACT["allowed_outcomes"]:
        errors.append("outcome")
    return errors


def self_test():
    node = GATE["required_nodes"]["M02A"]
    good = {
        "schema": "qps-fleet-receipt/v1",
        "mission_id": "M02A",
        "repo": node["repo"],
        "source_sha": node["target_head_sha"],
        "observed_at": "FIXTURE",
        "execution": {
            "kernel": "fixture",
            "outcome": "SUCCESS",
            "steps_gt0": True,
            "workflow_run_id": "fixture",
            "workflow_run_attempt": "1"
        },
        "evidence_class": "SYNTHETIC_FIXTURE",
        "authority_transfer": False,
        "engineering_acceptance": False
    }
    if receipt_errors(good, "M02A"):
        return False
    bad = copy.deepcopy(good)
    bad["authority_transfer"] = True
    return "authority_transfer" in receipt_errors(bad, "M02A")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--structure-only", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--receipt", action="append", default=[], help="NODE=path")
    args = ap.parse_args()

    se = structural_errors()
    if se:
        print(json.dumps({"status": "FAIL_STRUCTURE", "errors": se}, indent=2))
        return 1
    if args.structure_only:
        print(json.dumps({"status": "PASS_STRUCTURE_ONLY", "gate": GATE["gate_id"], "is_project_dov": False}, indent=2))
        return 0
    if args.self_test:
        ok = self_test()
        print(json.dumps({"status": "PASS_TESTABLE_ENGINE" if ok else "FAIL_SELF_TEST", "fixture_is_project_evidence": False}, indent=2))
        return 0 if ok else 1

    supplied = {}
    for item in args.receipt:
        name, sep, path = item.partition("=")
        if not sep:
            print(json.dumps({"status": "FAIL_ARGUMENT", "item": item}))
            return 1
        supplied[name] = json.loads(Path(path).read_text(encoding="utf-8"))
    required = set(GATE["required_nodes"])
    missing = sorted(required - set(supplied))
    if missing:
        print(json.dumps({"status": "DEFER_MISSING_RECEIPTS", "missing": missing, "is_project_dov": False}, indent=2))
        return 0

    errors = {}
    for name in sorted(required):
        e = receipt_errors(supplied[name], name)
        required_outcome = GATE["required_nodes"][name]["required_outcome"]
        if supplied[name].get("execution", {}).get("outcome") != required_outcome:
            e.append("required_outcome_not_met")
        if e:
            errors[name] = sorted(set(e))
    if errors:
        print(json.dumps({"status": "FAIL_FEDERATION_GATE", "errors": errors, "is_project_dov": False}, indent=2))
        return 1
    print(json.dumps({"status": "PASS_FEDERATION_GATE", "gate": GATE["gate_id"], "is_project_dov": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
