#!/usr/bin/env python3
import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate_timestamp(value, event_id):
    if not isinstance(value, str) or not value:
        raise SystemExit(f"FAIL {event_id}: timestamp must be a non-empty string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"FAIL {event_id}: timestamp is not ISO-8601: {value}") from exc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    contract = load("CREW_REX_BIDIRECTIONAL_CONTRACT.json")
    ledger = load("CREW_REX_LEDGER.json")
    events = ledger["events"]

    required_fields = contract.get("report_required_fields", [])
    if not required_fields:
        raise SystemExit("FAIL CREW_REX report_required_fields contract is empty")
    seen_event_ids = set()
    for event in events:
        event_id = event.get("event_id", "<missing>")
        missing = sorted(set(required_fields) - set(event))
        if missing:
            raise SystemExit(f"FAIL {event_id}: missing report_required_fields {missing}")
        if event_id in seen_event_ids:
            raise SystemExit(f"FAIL duplicate event_id: {event_id}")
        seen_event_ids.add(event_id)
        validate_timestamp(event["timestamp"], event_id)

    by_mission = defaultdict(list)
    for event in events:
        by_mission[event["mission_id"]].append(event)

    requested = Counter(e["requested_action"] for e in events)
    all_verbs = list(contract["verbs"].keys())
    observed_verbs = sorted(v for v in all_verbs if v in requested)
    dormant_verbs = sorted(v for v in all_verbs if v not in requested)

    crew_reports = [e for e in events if e["direction"] == "CREW_TO_MC"]
    returned = {e.get("causal_parent") for e in events if e["direction"] == "MC_TO_CREW" and e.get("causal_parent")}
    unmatched = sorted(e["event_id"] for e in crew_reports if e["event_id"] not in returned)
    if unmatched:
        raise SystemExit("FAIL unmatched crew reports: " + ",".join(unmatched))

    mission_reports = {}
    for mission_id, rows in sorted(by_mission.items()):
        mission_reports[mission_id] = {
            "events": len(rows),
            "crew_to_mc": sum(1 for r in rows if r["direction"] == "CREW_TO_MC"),
            "mc_to_crew": sum(1 for r in rows if r["direction"] == "MC_TO_CREW"),
            "requested_actions": sorted({r["requested_action"] for r in rows}),
            "latest_observations": [r["observation"] for r in rows[-2:]],
            "recorded_at_min": min(r["timestamp"] for r in rows),
            "recorded_at_max": max(r["timestamp"] for r in rows),
        }

    lessons = [
        {"id":"REX-GMF-001","learning":"zero-step execution is habitat evidence, not application defect evidence","assimilation":"route to Dockmaster; suppress Doctor/Engineer patching until >0 steps"},
        {"id":"REX-GMF-002","learning":"mature federation should contract generalists after repeated control","assimilation":"keep recurrence cells and return reusable crew to fleet"},
        {"id":"REX-GMF-003","learning":"reconnaissance value includes explicit ADAPT/EXTRACT/REFERENCE/PARK dispositions","assimilation":"return broad recon crew after classification; retain only named specialists"},
        {"id":"REX-GMF-004","learning":"planned topology is not an instantiated mission","assimilation":"GM-IV/GM-V remain HELD with zero fabricated children and zero operational surge"}
    ]

    report = {
        "schema":"qps.crew_rex_runtime_report.v1",
        "wave":"GM-FLEET-02B",
        "repo":os.environ.get("GITHUB_REPOSITORY","GBOGEB/pipeline-automation-hub"),
        "source_sha":os.environ.get("GITHUB_SHA",os.environ.get("SOURCE_SHA","LOCAL_UNBOUND")),
        "run_id":os.environ.get("GITHUB_RUN_ID","LOCAL"),
        "bidirectional_round_trip":"PASS",
        "report_required_fields_validated": required_fields,
        "crew_report_count":len(crew_reports),
        "unmatched_crew_reports":unmatched,
        "mission_reports":mission_reports,
        "operation_capability":all_verbs,
        "operations_observed_in_seed_ledger":observed_verbs,
        "operations_dormant_until_evidence":dormant_verbs,
        "lessons":lessons,
        "prune_rule":"replacement_proof_or_explicit_zero_value_required",
        "repair_rule":"observed_defect_required_and_Doctor_requires_gt0_steps",
        "bridge_rule":"preserve_source_identity_and_authority_boundary",
        "authority_transfer":False
    }
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"result":"PASS_CREW_REX_BIDIRECTIONAL","crew_reports":len(crew_reports),"missions":len(mission_reports),"required_fields":len(required_fields),"dormant":dormant_verbs}, sort_keys=True))

if __name__ == "__main__":
    main()
