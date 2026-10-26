#!/usr/bin/env python3
"""Read-only H01-H12 JADE DoV projection; source evidence stays in the existing owners."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_pb = importlib.util.spec_from_file_location("jade_private_boundary", ROOT / "tools" / "private_boundary.py")
PB = importlib.util.module_from_spec(_pb)
_pb.loader.exec_module(PB)
FILES = {
    "actions": "data/GATE12_DOV_ACTIONS.json",
    "focus": "data/FOCUS5_POINT_RELEASE_NPLUS7.json",
    "roster": "data/TOP21_PORTFOLIO.json",
    "dependencies": "data/ROLLING5_POLICY.json",
}
HEAD = re.compile(r"^(?:[0-9a-f]{40}|" + PB.MARK + r")$")  # a private head is PB.MARK (counts only)
STATES = {"PASS", "FAIL", "UNKNOWN"}
COLUMNS = ["rank", "repository", "pillar", "status", "readiness",
           "blocked_by", "owner", "action", "source_sha", "evidence"]


def need(ok: bool, text: str) -> None:
    if not ok:
        raise ValueError("JADE_GATE12_FAIL_CLOSED: " + text)


def read(root: Path, name: str) -> dict:
    return json.loads((root / FILES[name]).read_text(encoding="utf-8"))


def blob_oid(raw: bytes) -> str:
    """Git SHA-1 object identity, not a SHA-256 artifact hash."""
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def canonical(obj: dict, pretty: bool = False) -> bytes:
    args = {"sort_keys": True, "ensure_ascii": True}
    if pretty:
        args["indent"] = 2
    else:
        args["separators"] = (",", ":")
    return (json.dumps(obj, **args) + "\n").encode("utf-8")


def project(root: Path = ROOT) -> dict:
    """The model with private repos projected to counts only (tools/private_boundary.py)."""
    return PB.project(_project(root))


def _project(root: Path = ROOT) -> dict:
    a, f, roster, p = [read(root, name) for name in ("actions", "focus", "roster", "dependencies")]
    need(a.get("schema") == "jade.temple.gate12.actions.v1"
         and a.get("merge_admission") == "HOLD"
         and a.get("formal_release_credit") == 0
         and a.get("security_waiver") is False, "unsafe DoV authority")
    need(f.get("schema") == "jade.temple.focus5.readonly/1.0"
         and p.get("schema") == "jade.temple.rolling5.policy/1.0"
         and roster.get("cohort") == "MISSION_SELECTED_TOP21"
         and roster.get("merge_admission") == "HOLD", "source contract")
    ids = [f"H{i:02d}" for i in range(1, 13)]
    definitions = f["requisites"]
    need([x["id"] for x in definitions] == ids
         and [x["id"] for x in a["pillars"]] == ids
         and set(p["gate_prerequisites"]) == set(ids), "canonical H01-H12 mismatch")
    need(len(a.get("acceptance_ladder", [])) == 9
         and a["acceptance_ladder"][-1] == "OWNER_RELEASE_ACCEPTED", "stage contract")
    members = sorted(roster["repositories"], key=lambda r: r["rank"])
    names = [x["repo"] for x in members]
    need(len(members) == 21 and len(set(names)) == 21
         and len({x["rank"] for x in members}) == 21, "Top21 population drift")
    by_repo = {x["repo"]: x for x in f["rows"]}
    need(len(by_repo) == len(f["rows"]) == 5 and set(by_repo) <= set(names),
         "focus-five population drift")
    counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    for r in f["rows"]:
        need(bool(HEAD.fullmatch(r["source_sha"])), "invalid observed head")
        gs = r["gates"]
        need([g["id"] for g in gs] == ids, "incomplete or reordered gate population")
        for g in gs:
            need(g["status"] in STATES, "invalid evidence state")
            counts[g["status"]] += 1
    need(sum(counts.values()) == 60
         and counts["PASS"] == f["metrics"]["passed"]
         and counts["FAIL"] == f["metrics"]["failed"]
         and counts["UNKNOWN"] == f["metrics"]["unknown"], "misstated evidence totals")
    per_gate = {i: {"PASS": 0, "FAIL": 0, "UNKNOWN": 0} for i in ids}
    for r in f["rows"]:
        for g in r["gates"]:
            per_gate[g["id"]][g["status"]] += 1

    tasks, repo_rows = [], []
    for r in members:
        observed = by_repo.get(r["repo"])
        gate_map = {g["id"]: g for g in observed["gates"]} if observed else {}
        local = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0, "UNOBSERVED": 0}
        for pillar in a["pillars"]:
            gid = pillar["id"]
            gate = gate_map.get(gid)
            state = gate["status"] if gate else "UNOBSERVED"
            local[state] += 1
            upstream = [dep for dep in p["gate_prerequisites"][gid]
                        if not gate_map or gate_map[dep]["status"] != "PASS"]
            readiness = ("COMPLETE" if state == "PASS" else
                         "WAIT_DEPENDENCY" if upstream else
                         "FIRST_RED" if state == "FAIL" else "READY")
            evidence = gate.get("evidence") if gate else None
            if not isinstance(evidence, str) or not evidence.startswith("https://github.com/"):
                evidence = None
            tasks.append({
                "rank": r["rank"], "repository": r["repo"],
                "pillar": gid, "status": state, "readiness": readiness,
                "blocked_by": "|".join(upstream), "owner": pillar["owner"],
                "action": pillar["action"],
                "source_sha": observed["source_sha"] if observed else None,
                "evidence": evidence,
            })
        repo_rows.append({
            "rank": r["rank"], "repository": r["repo"], "observed": bool(observed),
            "source_sha": observed["source_sha"] if observed else None,
            "gate_counts": local,
        })
    task_states = {k: sum(x["readiness"] == k for x in tasks)
                   for k in ("FIRST_RED", "READY", "WAIT_DEPENDENCY", "COMPLETE")}
    pillars = []
    for item, defn in zip(a["pillars"], definitions):
        pillars.append({
            **item, "label": defn["label"], "phase": defn["phase"],
            "prerequisites": p["gate_prerequisites"][item["id"]],
            "observed_counts": per_gate[item["id"]],
            "unassessed_repos": 16,
        })
    return {
        "schema": "jade.temple.gate12.dov_projection.v1",
        "authority": {
            "merge_admission": "HOLD", "formal_release_credit": 0,
            "authority_transfer": False, "current_head_recertified": False,
            "owner_release": "WITHHELD",
        },
        "source": {
            "observed_date": f["source"]["observed_date"],
            "observation": "FROZEN_NONATOMIC_FOCUS5",
            "git_blob_oids": {name: blob_oid((root / path).read_bytes())
                              for name, path in FILES.items()},
            "live_current_head": None,
        },
        "metrics": {
            "observed_repositories": 5,
            "unassessed_repositories": 16,
            "top21_repositories": 21,
            "observed_gate_denominator": 60,
            "portfolio_gate_slots": 252,
            "unassessed_gate_slots": 192,
            "observed_pass": counts["PASS"],
            "observed_fail": counts["FAIL"],
            "observed_unknown": counts["UNKNOWN"],
            "task_readiness": task_states,
        },
        "publication": {
            "source_authored": "REPO_CANDIDATE",
            "static_qa": None, "browser_qa": None,
            "staged_single_publisher": None, "deployed": None,
            "hosted_http_200": None, "served_sha_matches": None,
            "operational_health": None, "rollback_drill": None,
            "owner_release": "HOLD",
            "note": "No hosted, deployment, operational or owner-release proof is inferred from source code.",
        },
        "threshold_policy": a["threshold_policy"],
        "acceptance_ladder": a["acceptance_ladder"],
        "pillars": pillars, "repositories": repo_rows, "queue": tasks,
        "assets": a["assets"],
    }


def outputs(root: Path = ROOT) -> dict[str, bytes]:
    view = project(root)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(COLUMNS)
    for task in view["queue"]:
        writer.writerow([task.get(col) or "" for col in COLUMNS])
    compact = canonical(view).decode("ascii").rstrip("\n")
    return {
        "gate12_data.json": canonical(view, pretty=True),
        "gate12_data.js": ("window.JADE_GATE12=" + compact + ";\n").encode("ascii"),
        "gate12_bd_queue.csv": buf.getvalue().encode("utf-8"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()
    for rel, raw in outputs().items():
        target = ROOT / "site" / rel
        if args.check:
            need(target.is_file() and target.read_bytes() == raw, "generated drift " + rel)
        else:
            target.write_bytes(raw)
    print("JADE_GATE12_" + ("PARITY_OK" if args.check else "WRITTEN"))


if __name__ == "__main__":
    main()
