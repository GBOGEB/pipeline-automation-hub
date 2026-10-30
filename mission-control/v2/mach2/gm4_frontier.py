#!/usr/bin/env python3
"""GM-IV EIGHT_FRONTIER_REPEAT_CONTROL_MACH_II: slot map, path leases, return receipts.

Read-only. Slot identities come from the canonical GRAND_MISSION_REGISTRY and the
ACTIVE8 governor contract; nothing here binds a child, authorizes a worker or
records an owner disposition. Lease overlap is decided by the federation-atlas
broker's ``conflicts`` (owner), path safety by gogreen ``_validate_path_lease``.
Anything not observed stays None and is listed under ``not_verified``.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
HUB = "GBOGEB/pipeline-automation-hub"
REGISTRY = "mission-control/grand-missions/GRAND_MISSION_REGISTRY.json"
GOVERNOR = "mission-control/grand-missions/GM_IV_ACTIVE8_GOVERNOR_CONTRACT.json"
RETURNS = "mission-control/v2/mach2/gm4_returns"
SLOT_MAP = "mission-control/v2/mach2/GM4_SLOT_MAP.json"
WAVE_LEASE = "mission-control/v2/mach2"
# Sibling waves declared by the coordinating session; the PR-burndown wave holds
# per-PR file sets, not a path prefix, so it cannot be declared here.
SIBLING_LEASES = {"LAUNCHPAD_WAVE": ["mission-control/launchpad"]}
SLOTS = tuple(f"GM-IV-F{i:02d}" for i in range(1, 9))
SHA = re.compile(r"^[0-9a-f]{40}$")
RECEIPT_SCHEMA = "missioncontrol.mach_ii.gm4.return_receipt.v1"
NULLABLE = ("run_id", "run_attempt", "job_id", "root_id", "owner_disposition")
RECEIPT_KEYS = {
    "schema", "mission_id", "mach2_scope", "slot", "series", "crew_role",
    "source_owner_repo", "hub_head_sha", "hub_registry_blob", "hub_governor_blob",
    "target_sha", "target_sha_fetchable", "default_branch", "head_sha",
    "head_moved_since_pin", "run_id", "run_attempt", "job_id", "root_id",
    "observed_at", "recorded_at", "evidence_class", "MIP_facet", "DoD", "DoV",
    "BD_delta", "REX_action", "source_digest", "owner_disposition",
    "next_guarded_transition", "not_verified", "children_bound",
    "authority_transfer", "dispatch_authorized",
}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_broker = _load("gm4_atlas_broker", BASE / "mission-control/federation-atlas/orchestration/broker.py")
_subtype = _load("gm4_gogreen_subtype", BASE / "mission-control/gogreen/subtype_orchestrator.py")
conflicts = _broker.conflicts
validate_path_lease = _subtype._validate_path_lease


def need(ok: bool, msg: str) -> None:
    if not ok:
        raise ValueError("GM4_FAIL_CLOSED: " + msg)


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def load_sources(base: Path = BASE) -> tuple[dict, dict]:
    reg = json.loads((base / REGISTRY).read_text(encoding="utf-8"))
    gov = json.loads((base / GOVERNOR).read_text(encoding="utf-8"))
    return reg, gov


def slot_lease(slot: str, repo: str) -> dict:
    """Read the frontier repo, write only this slot's return directory in the hub."""
    return {"read_paths": [repo, f"{HUB}/{REGISTRY}", f"{HUB}/{GOVERNOR}"],
            "write_paths": [f"{HUB}/{RETURNS}/{slot}"]}


def build_slot_map(reg: dict, gov: dict) -> dict:
    gm4 = next(m for m in reg["grand_missions"] if m["id"] == "GM-IV")
    gm5 = next(m for m in reg["grand_missions"] if m["id"] == "GM-V")
    need(gm4["state"] == "ACTIVE_8_OF_8", "GM-IV canonical state")
    need(gm4["children"] == [], "GM-IV canonical children must stay empty")
    need(gm5["state"] == "HELD" and gm5["children"] == [], "GM-V must stay HELD")
    need(tuple(gm4["candidate_frontiers"]) == SLOTS, "eight canonical slot ids")
    need(gm4.get("unfilled_frontier_slots") == [], "unfilled slot")
    evidence = gov["frontier_evidence"]
    need(tuple(sorted(evidence)) == SLOTS, "governor contract slot ids")
    role = {s: "CONTROLLED_PILOT" for s in gm4["controlled_pilot_frontiers"]}
    role.update({s: "REFERENCE" for s in gm4["reference_frontiers"]})
    role.update({s: "NEW_CANDIDATE_RECON" for s in gm4["new_candidate_recon_frontiers"]})
    need(set(role) == set(SLOTS), "every slot has exactly one canonical class")
    slots = []
    for s in SLOTS:
        e = evidence[s]
        need(SHA.match(e["target_sha"]) is not None, s + " pinned target sha")
        need(e["repository"].startswith("GBOGEB/"), s + " owner namespace")
        slots.append({
            "slot": s, "candidate_repository": e["repository"], "target_sha": e["target_sha"],
            "canonical_class": role[s], "governor_class": e["class"],
            "observed_surface": e.get("observed_surface"),
            "source_owner": e["repository"], "owner_account": e["repository"].split("/")[0],
            "crew_pool": gov["crew"], "assigned_worker": None,
            "child_binding": None, "lease": slot_lease(s, e["repository"]),
        })
    out = {"schema": "missioncontrol.mach_ii.gm4.slot_map.v1", "mission_id": "GM-IV",
           "source": {"registry": REGISTRY, "governor_contract": GOVERNOR},
           "canonical_state": gm4["state"], "canonical_children": gm4["children"],
           "slots": slots, "wave_lease": WAVE_LEASE, "sibling_leases": SIBLING_LEASES,
           "named_slots": len(slots), "authorized_workers": None,
           "authority_transfer": False, "dispatch_authorized": False,
           "noncompensation": ["8 named slots imply 8 authorized workers",
                               "Backfill historic GM-IV with new child claims"]}
    out["lease_check"] = check_leases(out)
    return out


def check_leases(slot_map: dict) -> dict:
    """Pairwise disjointness of slot leases (broker semantics) and containment in this wave."""
    leases = {x["slot"]: x["lease"] for x in slot_map["slots"]}
    for lease in leases.values():
        for p in lease["read_paths"] + lease["write_paths"]:
            validate_path_lease(p)
    names = sorted(leases)
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]
             if conflicts(leases[a], leases[b]) or conflicts(leases[b], leases[a])]
    need(not pairs, "overlapping slot leases " + repr(pairs))
    wave = f"{HUB}/{slot_map['wave_lease']}"
    for s, lease in leases.items():
        need(all(conflicts({"write_paths": [w], "read_paths": []},
                           {"write_paths": [wave], "read_paths": []}) and
                 w.startswith(wave + "/") for w in lease["write_paths"]),
             s + " writes outside the wave lease")
    siblings = {k: {"write_paths": [f"{HUB}/{p}" for p in v], "read_paths": []}
                for k, v in slot_map["sibling_leases"].items()}
    clash = [(s, k) for s, lease in leases.items() for k, sib in siblings.items()
             if conflicts(lease, sib) or conflicts(sib, lease)]
    need(not clash, "slot lease overlaps a sibling wave " + repr(clash))
    return {"pairs_checked": len(names) * (len(names) - 1) // 2, "overlapping_pairs": 0,
            "sibling_waves_checked": sorted(siblings), "result": "PASS_DISJOINT",
            "semantics": "federation-atlas broker.conflicts: write/write and write/read incl. parents",
            "not_verified": ["PR_BURNDOWN_WAVE_LEASE_NOT_DECLARED_AS_PATHS",
                             "UNDECLARED_WRITES_NOT_DETECTED"]}


def gh_fetch(route: str) -> dict:
    out = subprocess.run(["gh", "api", route, "--jq", "{sha, default_branch}"], check=True,
                         capture_output=True, text=True, encoding="utf-8")
    return json.loads(out.stdout)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_blob_at(sha: str, path: str) -> str:
    return subprocess.run(["git", "-C", str(BASE), "rev-parse", f"{sha}:{path}"],
                          check=True, capture_output=True, text=True).stdout.strip()


def observe_slot(slot: dict, series: str, hub_sha: str, blobs: tuple[str, str],
                 fetch: Callable[[str], dict] = gh_fetch,
                 clock: Callable[[], str] = _now) -> dict:
    repo, target = slot["candidate_repository"], slot["target_sha"]
    meta = fetch(f"repos/{repo}")
    branch = meta["default_branch"]
    head = fetch(f"repos/{repo}/commits/{branch}")["sha"]
    pinned = fetch(f"repos/{repo}/commits/{target}")["sha"]
    observed = clock()
    material = {"repo": repo, "default_branch": branch, "head_sha": head, "pinned": pinned}
    return {
        "schema": RECEIPT_SCHEMA, "mission_id": "GM-IV",
        "mach2_scope": "EIGHT_FRONTIER_REPEAT_CONTROL_MACH_II", "slot": slot["slot"],
        "series": series, "crew_role": "SCOUT", "source_owner_repo": repo,
        "hub_head_sha": hub_sha, "hub_registry_blob": blobs[0], "hub_governor_blob": blobs[1],
        "target_sha": target, "target_sha_fetchable": pinned == target,
        "default_branch": branch, "head_sha": head, "head_moved_since_pin": head != target,
        "run_id": None, "run_attempt": None, "job_id": None, "root_id": None,
        "observed_at": observed, "recorded_at": clock(),
        "evidence_class": "OBSERVED_API_READBACK", "MIP_facet": "perpetuate",
        "DoD": "exact pinned SHA fetchable and current default head recorded",
        "DoV": "NOT_VERIFIED", "BD_delta": 0, "REX_action": "RETURN",
        "source_digest": "sha256:" + hashlib.sha256(
            json.dumps(material, sort_keys=True).encode()).hexdigest(),
        "owner_disposition": None,
        "next_guarded_transition": "GOVERNOR_OWNER_ADMIN_DISPOSITION",
        "not_verified": list(NULLABLE) + ["DoV"],
        "children_bound": False, "authority_transfer": False, "dispatch_authorized": False,
    }


def validate_receipt(r: dict, slot_map: dict) -> dict:
    need(set(r) == RECEIPT_KEYS, "receipt keys " + repr(sorted(set(r) ^ RECEIPT_KEYS)))
    need(r["schema"] == RECEIPT_SCHEMA and r["mission_id"] == "GM-IV", "receipt schema")
    slots = {x["slot"]: x for x in slot_map["slots"]}
    need(r["slot"] in slots, "unknown slot " + str(r["slot"]))
    s = slots[r["slot"]]
    need(r["source_owner_repo"] == s["candidate_repository"], "receipt repo != slot map")
    need(r["target_sha"] == s["target_sha"], "receipt pinned sha != slot map")
    for k in ("hub_head_sha", "hub_registry_blob", "hub_governor_blob", "target_sha", "head_sha"):
        need(isinstance(r[k], str) and SHA.match(r[k]) is not None, k + " not an exact sha")
    need(r["head_moved_since_pin"] == (r["head_sha"] != r["target_sha"]), "head movement flag")
    need(type(r["target_sha_fetchable"]) is bool, "fetchable flag")
    need(r["children_bound"] is False and r["authority_transfer"] is False
         and r["dispatch_authorized"] is False, "receipt claims authority")
    need(r["owner_disposition"] is None, "forged owner disposition")
    for k in NULLABLE:
        need(r[k] is None or k not in r["not_verified"], k + " both set and NOT_VERIFIED")
        need(r[k] is not None or k in r["not_verified"], k + " missing without NOT_VERIFIED")
    need(r["DoV"] == "NOT_VERIFIED" or r["owner_disposition"] is not None, "DoV without owner")
    need(r["observed_at"] <= r["recorded_at"], "recorded before observed")
    need(re.match(r"^sha256:[0-9a-f]{64}$", r["source_digest"]) is not None, "source digest")
    return r


def evaluate_series(receipts: list[dict], slot_map: dict) -> dict:
    for r in receipts:
        validate_receipt(r, slot_map)
    by = {}
    for r in receipts:
        key = (r["series"], r["slot"])
        need(key not in by, "duplicate receipt " + repr(key))
        by[key] = r
    series = sorted({r["series"] for r in receipts})
    complete = [x for x in series if all((x, s) in by for s in SLOTS)]
    heads = {x: {by[(x, s)]["hub_head_sha"] for s in SLOTS} for x in complete}
    need(all(len(h) == 1 for h in heads.values()), "series spans several hub heads")
    hub_heads = [next(iter(heads[x])) for x in complete]
    moved = {s: sorted({by[(x, s)]["head_sha"] for x in complete}) for s in SLOTS}
    return {
        "series": series, "complete_series": complete,
        "distinct_hub_heads": len(set(hub_heads)) == len(hub_heads) and len(hub_heads) >= 2,
        "hub_heads": hub_heads,
        "pinned_fetchable": {s: all(by[(x, s)]["target_sha_fetchable"] for x in complete)
                             for s in SLOTS},
        "frontier_heads_observed": moved,
        "frontier_heads_changed_between_series": sorted(s for s in SLOTS if len(moved[s]) > 1),
        "children_bound": 0, "invented_child_bindings": 0,
    }


def dov(slot_map: dict, rollup: dict | None) -> dict:
    two = rollup is not None and len(rollup["complete_series"]) >= 2 and rollup["distinct_hub_heads"]
    return {
        "eight_named_slot_identities": "PASS" if slot_map["named_slots"] == 8 else "FAIL",
        "zero_invented_canonical_child_bindings":
            "PASS" if slot_map["canonical_children"] == [] and
            (rollup is None or rollup["invented_child_bindings"] == 0) else "FAIL",
        "two_independent_repeat_series_at_pinned_new_heads": {
            "two_series_at_distinct_hub_heads": "OBSERVED" if two else "NOT_VERIFIED",
            "independence": "NOT_VERIFIED",
            "independence_reason": "same operator, session and day; no separate runner or reviewer",
            "frontier_new_heads": "NOT_VERIFIED" if not rollup or
            not rollup["frontier_heads_changed_between_series"] else "PARTIAL"},
        "nondegrading_proof_yield_and_queue_p95": "NOT_VERIFIED",
        "queue_p95_owner": "mission-control/grand-missions/measure_gm_iv_runtime_capacity.py",
        "governor_owner_admin_disposition_before_GM_V": "NOT_VERIFIED",
        "admission": "HOLD",
    }


def read_receipts(root: Path = BASE / RETURNS) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob("GM-IV-F0*/series_*.json"))]


def _dump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("map")
    o = sub.add_parser("observe")
    o.add_argument("--series", required=True, choices=["A", "B", "C", "D"])
    o.add_argument("--hub-sha", required=True)
    sub.add_parser("status")
    args = p.parse_args()
    reg, gov = load_sources()
    slot_map = build_slot_map(reg, gov)
    if args.cmd == "map":
        (BASE / SLOT_MAP).write_text(_dump(slot_map), encoding="utf-8", newline="\n")
    elif args.cmd == "observe":
        need(SHA.match(args.hub_sha) is not None, "hub sha")
        blobs = (git_blob_at(args.hub_sha, REGISTRY), git_blob_at(args.hub_sha, GOVERNOR))
        for s in slot_map["slots"]:
            r = validate_receipt(observe_slot(s, args.series, args.hub_sha, blobs), slot_map)
            out = BASE / RETURNS / s["slot"] / f"series_{args.series}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(_dump(r), encoding="utf-8", newline="\n")
    rollup = evaluate_series(read_receipts(), slot_map) if read_receipts() else None
    print(json.dumps({"slots": slot_map["named_slots"], "lease": slot_map["lease_check"]["result"],
                      "rollup": rollup, "DoV": dov(slot_map, rollup)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
