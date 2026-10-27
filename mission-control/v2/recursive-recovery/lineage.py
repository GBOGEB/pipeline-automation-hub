#!/usr/bin/env python3
"""N12 additive Mission Control recovery projection.

Reads canonical in-repo Git blobs at their recorded identities; never edits canonical
Grand Mission, crew, Golden Thread, QPS or CODEX authority. Source graph is allowed
reference cycles; the execution and lineage subgraphs must be acyclic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SCHEMA = "missioncontrol.recursive_recovery.projection.v1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()


def validate_successor(spec, frozen_raw):
    """Reject historical-identity rewriting or unauthorized source substitutions."""
    predecessor = spec.get("successor_of", {})
    if (predecessor.get("file") != "N12_SOURCE_ATLAS.json"
            or predecessor.get("preserved_unchanged") is not True
            or git_blob(frozen_raw) != predecessor.get("blob_sha")):
        raise ValueError("FROZEN_ATLAS_IDENTITY_DRIFT")
    frozen = json.loads(frozen_raw)
    old = {row["id"]: row for row in frozen["internal"]}
    new = {row["id"]: row for row in spec["internal"]}
    if len(old) != len(new) or set(old) != set(new):
        raise ValueError("FROZEN_ATLAS_SOURCE_SET_DRIFT")
    for source_id, current in new.items():
        baseline = old[source_id]
        if source_id == "breadth":
            if (current.get("previous_frozen_blob_sha") != baseline["blob_sha"]
                    or current.get("path") != baseline["path"]
                    or current.get("authority") != baseline["authority"]
                    or current.get("blob_sha") != spec["source_refresh_evidence"]["new_blob_sha"]
                    or baseline["blob_sha"] != spec["source_refresh_evidence"]["old_blob_sha"]):
                raise ValueError("FROZEN_BREADTH_SUCCESSOR_INVALID")
        elif current != baseline:
            raise ValueError("UNAUTHORIZED_FROZEN_SOURCE_REWRITE: " + source_id)
    if spec.get("source_refresh_evidence", {}).get("changed_internal_blobs") != 1:
        raise ValueError("SOURCE_REFRESH_DENOMINATOR_DRIFT")


def load_canonical():
    frozen_raw = (HERE / "N12_SOURCE_ATLAS.json").read_bytes()
    spec = json.loads((HERE / "N12_SOURCE_ATLAS_20261026.json").read_text(encoding="utf-8"))
    validate_successor(spec, frozen_raw)
    if spec.get("controller", {}).get("authority_transfer") is not False:
        raise ValueError("source controller authority may not transfer")
    content = {}
    for item in spec["internal"]:
        path = ROOT / item["path"]
        raw = path.read_bytes()
        actual = git_blob(raw)
        if not SHA40.fullmatch(item["blob_sha"]) or actual != item["blob_sha"]:
            raise ValueError("FROZEN_SOURCE_BLOB_DRIFT: " + item["id"])
        content[item["id"]] = json.loads(raw) if item["path"].endswith(".json") else raw.decode("utf-8")
    return spec, content


def yaml_mission(text, category, mission_id):
    start = text.find(category + ":")
    if start < 0:
        raise ValueError("official mission namespace missing: " + category)
    next_category = min((p for p in [text.find("\nlocal_missions:", start + 1),
                                      text.find("\ninvariants:", start + 1)]
                         if p >= 0), default=len(text))
    scope = text[start:next_category]
    match = re.search(r"(?m)^  - id: " + re.escape(mission_id) + r"\s*$", scope)
    if not match:
        raise ValueError("official mission ID missing: " + mission_id)
    tail = scope[match.end():]
    nxt = re.search(r"(?m)^  - id: ", tail)
    segment = tail[:nxt.start()] if nxt else tail
    fields = {}
    for key in ["type", "name", "state", "home", "provider", "parent_issue", "orchestration_issue"]:
        m = re.search(r"(?m)^    " + re.escape(key) + r":\s*(.+?)\s*$", segment)
        fields[key] = m.group(1).strip("'\"") if m else None
    return {"id": mission_id, "type": fields["type"], "name": fields["name"],
            "archival_state": fields["state"], "home": fields["home"],
            "provider": fields["provider"], "parent_issue": fields["parent_issue"],
            "orchestration_issue": fields["orchestration_issue"],
            "evidence_class": "FROZEN_OFFICIAL_YAML_FIELDS", "authority_transfer": False}


def is_dag(edges):
    deps = {}
    for edge in edges:
        if edge["kind"] not in ("LINEAGE_PARENT", "EXECUTION_DEPENDENCY"):
            continue
        deps.setdefault(edge["from"], set()).add(edge["to"])
        deps.setdefault(edge["to"], set())
    active, done = set(), set()
    def visit(n):
        if n in active:
            raise ValueError("CYCLIC_EXECUTION_OR_LINEAGE_DAG: " + n)
        if n in done:
            return
        active.add(n)
        for dst in sorted(deps.get(n, ())):
            visit(dst)
        active.remove(n)
        done.add(n)
    for n in sorted(deps):
        visit(n)
    return True


def build(spec, d):
    registry, genealogy, crew, rex = (
        d["gm_registry"], d["gm_genealogy"], d["crew_roster"], d["rex_ledger"]
    )
    gm = registry["grand_missions"]
    ids = [x["id"] for x in gm]
    if ids != ["GM-I", "GM-II", "GM-III", "GM-IV", "GM-V"]:
        raise ValueError("canonical GM 1..5 identity changed")
    if [m["frontier_count"] for m in gm] != [1, 2, 4, 8, 16]:
        raise ValueError("canonical scaling ladder altered")
    g4, g5 = gm[3], gm[4]
    if g4["state"] != "ACTIVE_8_OF_8" or g4["children"]:
        raise ValueError("GM-IV activation must not invent canonical children")
    if g5["state"] != "HELD" or g5["children"]:
        raise ValueError("GM-V may not be launched by recovery")
    if registry["authority_transfer"] is not False or crew["authority_transfer"] is not False:
        raise ValueError("canonical authority transfer")
    official = d["official_missions"]
    local = [yaml_mission(official, "local_missions", x) for x in ("LM-10", "LM-11")]
    horizontal = [yaml_mission(official, "horizontal_missions", "HM-01")]
    crew_rows = crew["crew"]
    crew_ids = [x["crew_id"] for x in crew_rows]
    if len(crew_ids) != len(set(crew_ids)):
        raise ValueError("duplicate crew ID")
    conceptual = [x for x in crew_rows if x.get("maturity") == "CONCEPTUAL"]
    for person in conceptual:
        if person.get("authority", {}).get("promote") not in (False, None):
            raise ValueError("conceptual crew cannot promote")
    event_rows = rex["events"]
    eid = {e["event_id"] for e in event_rows}
    if len(eid) != len(event_rows):
        raise ValueError("duplicate REX event")
    for e in event_rows:
        if e.get("causal_parent") and e["causal_parent"] not in eid:
            raise ValueError("dangling REX predecessor: " + e["event_id"])
    roles = d["crew_roles"]["roles"]
    top7 = d["top7"]["selection"]["repositories"]
    if len(top7) != 7 or len(set(top7)) != 7:
        raise ValueError("historical Top7 scope corrupted")

    nodes, edges, seen, ek = [], [], set(), set()
    def node(identifier, kind, **kwargs):
        if identifier in seen:
            return
        seen.add(identifier)
        nodes.append({"id": identifier, "kind": kind, **kwargs})
    def edge(source, target, kind, evidence="SOURCE_DECLARED"):
        sig = (source, target, kind)
        if sig in ek:
            return
        ek.add(sig)
        edges.append({"from": source, "to": target, "kind": kind,
                      "evidence_class": evidence, "authority_transfer": False})

    node("control:MissionControl", "CONTROL", label="Mission Control v2", admission="HOLD")
    node("control:GoldenThread", "CONTROL", label="Golden Thread replay", authority="FEDERATION_ONLY")
    node("control:Mycelium", "BRIDGE", label="CODEX Mycelium", status="READ_ONLY")
    node("control:QPS", "AUTHORITY", label="QPS engineering / release", authority="EXTERNAL_OWNER")
    node("gate:Gov", "GATE", label="Noncompensating admission", status="HOLD")
    edge("control:MissionControl", "control:GoldenThread", "USES_NONAUTHORITATIVE", "EXISTING_CONTROL")
    edge("control:MissionControl", "control:Mycelium", "BRIDGE_READ_ONLY", "EXTERNAL_SOURCE_REFERENCE")
    edge("control:GoldenThread", "control:QPS", "SOURCE_BOUND_CONSUMER", "NO_QPS_AUTHORITY_TRANSFER")
    edge("control:MissionControl", "gate:Gov", "CONTROL_GATE", "OWNER_DECISION_REQUIRED")

    mission_rows = []
    for m in gm:
        mid = "mission:" + m["id"]
        node(mid, "GRAND_MISSION", label=m["name"], state=m["state"], target_frontiers=m["frontier_count"],
             observed=m.get("observed"), children_bound=len(m.get("children", [])))
        edge("control:MissionControl", mid, "GOVERNS_NAMESPACE", "CANONICAL_REGISTRY")
        mission_rows.append({"id": m["id"], "type": "GRAND_MISSION", "name": m["name"],
                             "statement": m.get("objective"), "state": m["state"],
                             "frontiers": m["frontier_count"], "children": m.get("children", []),
                             "candidate_frontiers": m.get("candidate_frontiers", []),
                             "crew_posture": m.get("crew_posture"), "source_id": "gm_registry",
                             "authority_transfer": False})
        for rr in m.get("children", []):
            rid = "repo:" + rr
            node(rid, "REPOSITORY", label=rr)
            edge(mid, rid, "HISTORICAL_FRONTIER", "REGISTERED_SOURCE")
        for var in m.get("variants", []):
            vid = "mission:" + var["id"]
            node(vid, "GM_VARIANT", label=var.get("name", var["id"]), state=var.get("state"))
            edge(vid, mid, "LINEAGE_PARENT", "CANONICAL_VARIANT")
            mission_rows.append({"id": var["id"], "type": "GRAND_MISSION_VARIANT",
                                 "name": var.get("name"), "state": var.get("state"),
                                 "parent": m["id"], "repository": var.get("repository"),
                                 "source_id": "gm_registry", "authority_transfer": False})
            if var.get("repository"):
                rid = "repo:" + var["repository"]
                node(rid, "REPOSITORY", label=var["repository"])
                edge(vid, rid, "SOURCE_FRONTIER", "SOURCE_REFERENCED")
    for other in horizontal + local:
        mid = "mission:" + other["id"]
        node(mid, other["type"] or "NON_GRAND_MISSION", label=other["name"], state=other["archival_state"])
        edge("control:MissionControl", mid, "OFFICIALLY_REGISTERED", "CANONICAL_OFFICIAL_MISSION_INDEX")
        mission_rows.append({"id": other["id"], "type": other["type"],
                             "name": other["name"], "state": other["archival_state"],
                             "statement": None, "source_id": "official_missions",
                             "authority_transfer": False})
        for key in ("home", "provider"):
            if other.get(key):
                rid = "repo:" + other[key]
                node(rid, "REPOSITORY", label=other[key])
                edge(mid, rid, "MISSION_PROVIDER", "OFFICIAL_INDEX")
        for key in ("parent_issue", "orchestration_issue"):
            if other.get(key):
                iid = "issue:" + other[key]
                node(iid, "ISSUE", label=other[key], state="CURRENT_RECHECK_REQUIRED")
                edge(mid, iid, "ISSUE_HOOK", "HISTORICAL_REGISTER")
    node("mission:TOP7-D3", "OPERATIONAL_MISSION", label="Top7 depth-three first-red",
         state="HISTORICAL_MISSION_CONTRACT")
    edge("control:MissionControl", "mission:TOP7-D3", "GOVERNS_BOUNDED_WORK", "HISTORICAL")
    for r in top7:
        rid = "repo:" + r
        node(rid, "REPOSITORY", label=r)
        edge("mission:TOP7-D3", rid, "SOURCE_COHORT", "HISTORICAL_TOP7")
    node("cohort:N11-TOP21", "SOURCE_COHORT", label="21 exact-Git-tree repositories", scope="FILES")
    node("cohort:PR-FLEET-90", "SOURCE_COHORT", label="90 historical PR repositories", scope="PR_GENEALOGY")
    edge("control:MissionControl", "cohort:N11-TOP21", "INVENTORY", "COMPLETE_21_AT_FROZEN_SHAS")
    edge("control:MissionControl", "cohort:PR-FLEET-90", "INVENTORY", "HISTORICAL_FROZEN_90_REPOS")
    for r in crew_rows:
        cid = "crew:" + r["crew_id"]
        node(cid, "CREW", label=r["name"], maturity=r["maturity"],
             home=r["home_base"], secondment=r.get("secondment"),
             capability_basis=r.get("competency_vector", {}).get("basis"), operational_capacity="UNKNOWN")
        edge("control:MissionControl", cid, "HAS_REGISTERED_CREW", "CANDIDATE_REGISTRY")
    for role in roles:
        rid = "role:" + role["id"]
        node(rid, "CREW_ROLE", label=role["id"], home=role.get("home_base"))
        edge("control:MissionControl", rid, "HAS_ROLE", "ROLE_REGISTRY")
    for e in event_rows:
        rid = "rex:" + e["event_id"]
        node(rid, "REX_EVENT", label=e["event_type"], mission=e["mission_id"],
             evidence=e["evidence_class"], action=e.get("requested_action"))
        mission_ref = "mission:" + e["mission_id"]
        if mission_ref not in seen:
            raise ValueError("REX refers to unknown mission: " + e["mission_id"])
        edge(mission_ref, rid, "REX_HISTORY", "RECORDED_AT_NOT_EVENT_OCCURRENCE")
        actor_role = "role:" + e["crew_role"]
        if actor_role in seen:
            edge(actor_role, rid, "REX_ROLE_REPORT", "HISTORICAL_ROLE_NOT_CURRENT_PERSON")
        if e.get("causal_parent"):
            edge("rex:" + e["causal_parent"], rid, "LINEAGE_PARENT", "RECORDED_CAUSAL_CHAIN")
    for item in spec["internal"]:
        sid = "source:" + item["id"]
        node(sid, "FROZEN_SOURCE", label=item["path"], blob_sha=item["blob_sha"])
        edge("control:MissionControl", sid, "READS_CANONICAL", "GIT_BLOB_VERIFIED")
    for item in spec["external"]:
        sid = "external:" + item["id"]
        node(sid, "EXTERNAL_BOUNDARY", label=item.get("repo"), state=item["class"])
        edge("control:MissionControl", sid, "REFERENCES_EXTERNAL", "NO_AUTHORITY_TRANSFER")
    for e in edges:
        if e["from"] not in seen or e["to"] not in seen:
            raise ValueError("dangling graph edge")
    is_dag(edges)

    prior = genealogy["missions"].get("GM-IV", {})
    contrast = {"mission": "GM-IV", "archival_source": "gm_genealogy",
                "archival_state": prior.get("state"), "current_source": "gm_registry",
                "current_state": g4["state"], "decision": "PRESERVE_HISTORICAL; CANONICAL_REGISTRY_PRECEDES"}
    telemetry = d["v2"]
    recovery = {"schema": SCHEMA, "source_anchor": spec["controller"],
                "authority_transfer": False, "formal_credit_delta": 0,
                "engineering_credit_delta": 0, "merge_admission": "HOLD",
                "source_class": "FROZEN_EXACT_GIT_BLOBS_NOT_LIVE_RUNTIME",
                "missions": mission_rows,
                "historical_conflicts": [contrast] + spec.get("special_cases", [])[1:],
                "crew": [{"id": c["crew_id"], "name": c["name"], "home": c["home_base"],
                          "roles": c["roles"], "maturity": c["maturity"],
                          "secondment": c.get("secondment"), "current_load_archival": c.get("current_load"),
                          "capability_basis": c.get("competency_vector", {}).get("basis"),
                          "registered_runtime_receipts": len(c.get("runtime_receipts", [])),
                          "live_worker_status": None, "promotion_proof": None}
                         for c in crew_rows],
                "rex": [{"id": e["event_id"], "mission_id": e["mission_id"], "event_type": e["event_type"],
                         "crew_role": e["crew_role"], "observation": e["observation"],
                         "requested_action": e.get("requested_action"),
                         "recorded_at": e["timestamp"], "time_basis": e.get("timestamp_basis"),
                         "parent": e.get("causal_parent"), "evidence_class": e["evidence_class"]}
                        for e in event_rows],
                "source_links": [{"id": z["id"], "url": "https://github.com/GBOGEB/pipeline-automation-hub/blob/" +
                                  spec["controller"]["commit_sha"] + "/" + z["path"],
                                  "blob_sha": z["blob_sha"], "authority": z["authority"]}
                                 for z in spec["internal"]],
                "external_links": spec["external"],
                "graph": {"nodes": nodes, "edges": edges,
                          "lineage_dag_acyclic": True,
                          "general_reference_graph_may_cycle": True},
                "metrics": {
                    "grand_missions": 5, "grand_frontier_ladder": [1, 2, 4, 8, 16],
                    "registered_variants": len([m for m in mission_rows if m["type"] == "GRAND_MISSION_VARIANT"]),
                    "horizontal_missions": len(horizontal), "local_missions": len(local),
                    "crew_registered": len(crew_rows), "crew_conceptual": len(conceptual),
                    "crew_runtime_proven_current": None, "rex_historical_events": len(event_rows),
                    "top7_repos_historical": 7,
                    "top21_file_repos": d["n11"]["totals"]["repositories"],
                    "top21_file_atoms": d["n11"]["totals"]["files"],
                    "historical_pr_fleet_repos": d["pr_fleet"]["structural_backfill"]["repositories"],
                    "historical_pr_nodes": d["pr_fleet"]["structural_backfill"]["pr_nodes"],
                    "live_pr_jobs_proven": None,
                    "source_blob_verification": len(spec["internal"]),
                    "nodes": len(nodes), "edges": len(edges),
                    "pca_eligible": False, "bt_eligible": False,
                    "cohort_denominators_not_additive": True},
                "temporal_contract": {"semantic_generation_k": "ONLY_AUTHORITATIVE_ACCEPTED_DELTA",
                                     "event_sequence_e": "APPEND_ANY_ACCEPT_REJECT_DEFER_OR_CONTROL_EVENT",
                                     "occurred_at_ne_recorded_at": True,
                                     "source": "golden_temporal"},
                "no_auto_dispatch": True,
                "telemetry_contract": telemetry["schema"],
                "stop_rules": registry["stop_rules"]}
    recovery["semantic_sha256"] = digest(recovery)
    return recovery


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    spec, data = load_canonical()
    projection = build(spec, data)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"schema": SCHEMA, "sha256": projection["semantic_sha256"],
                      "missions": len(projection["missions"]),
                      "crew": projection["metrics"]["crew_registered"],
                      "rex": projection["metrics"]["rex_historical_events"],
                      "nodes": projection["metrics"]["nodes"],
                      "edges": projection["metrics"]["edges"],
                      "authority_transfer": False, "admission": "HOLD"}))


if __name__ == "__main__":
    main()
