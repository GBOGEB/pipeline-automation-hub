#!/usr/bin/env python3
"""Render the CODE PURPLE control page (code-purple.html + code-purple.json) from repo files.

Read-only projection: beams DAG, BD queue, ordinal metric series, promotion gate ledger,
Top7 pulses, Top21 rows, triggers and SIPOC candidates. Nothing here promotes, merges or
writes outside --out.

  python mission-control/federation-atlas/build_code_purple.py --out /tmp/code-purple
  python mission-control/federation-atlas/build_code_purple.py --out /tmp/cp --fragment   # body-only page
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import code_purple_series as cps

TEMPLATE = HERE / "code_purple_template.html"
COMPLETE = cps.COMPLETE


def _repo_evaluator(contract: dict) -> dict:
    p = ROOT / "mission-control" / "grand-missions" / "gm_dmaic_evolution_metrics.py"
    spec = importlib.util.spec_from_file_location("gm_eval_for_atlas", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.evaluate(contract)


def _head_sha() -> str | None:
    env = os.environ.get("GITHUB_SHA")
    if env:
        return env
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def beam_metrics(beams: dict, items: list[dict], ledger: dict) -> dict:
    out = {}
    for b in beams["beams"]:
        mine = [i for i in items if i["beam"] == b["id"]]
        states = [i["now"]["state"] for i in mine]
        flows = [i["now"]["flow"] for i in mine]
        if mine:
            done = sum(s in COMPLETE for s in states)
            progress = {"num": done, "den": len(mine), "basis": "BD items complete"}
        elif b["id"] == "B5":
            rows = ledger["top7_to_top14"]
            progress = {"num": sum(r["state"] == "PASS" for r in rows), "den": len(rows), "basis": "Top14 predicates passing"}
        else:
            progress = {"num": None, "den": None, "basis": "no items"}
        out[b["id"]] = {
            "progress": progress,
            "done": sum(s in COMPLETE for s in states),
            "active": states.count("ACTIVE"),
            "todo": states.count("TODO"),
            "reader": states.count("UNKNOWN_NEEDS_READER"),
            "ready": flows.count("READY"),
            "in_pr": flows.count("IN_PR"),
            "blocked": flows.count("BLOCKED") + flows.count("HOLD") + flows.count("RETURN_OWNER"),
            "linked": flows.count("LINKED"),
            "critical": any(i["critical_path"] and i["now"]["state"] in ("TODO", "ACTIVE", "UNKNOWN_NEEDS_READER") for i in mine) or b["id"] in beams["critical_path"]["path"],
            "items": [i["id"] for i in mine],
            "links": sorted({link for i in mine for link in i["links"] if "/issues/" in link or "/pull/" in link}),
        }
    return out


def lanes(beams: dict) -> dict:
    ff = [(e["from"], e["to"]) for e in beams["edges"] if e["type"] == "FEEDFORWARD"]
    depth = {b["id"]: 0 for b in beams["beams"]}
    for _ in range(len(depth)):
        changed = False
        for a, b in ff:
            if depth[b] < depth[a] + 1:
                depth[b] = depth[a] + 1
                changed = True
        if not changed:
            return depth
    raise ValueError("FEEDFORWARD edges contain a cycle")


def build_payload() -> dict:
    queue = cps.load_json(cps.QUEUE)
    series = cps.load_json(cps.SERIES)
    beams = cps.load_json(cps.BEAMS)
    pulses = cps.load_json(cps.PULSES)
    contract = cps.load_json(ROOT / cps.CONTRACT)
    coverage = cps.load_json(ROOT / cps.COVERAGE)
    topology = cps.load_json(ROOT / cps.TOPOLOGY)
    status = cps.load_json(ROOT / "mission-control/v2/MC_MISSION_STATUS_CURRENT_v1.json")
    latest = series["entries"][-1]["key"]
    items = []
    for i in queue["items"]:
        now = cps.item_at(i, latest)
        if now is not None:
            items.append({**i, "now": now})
    ledger = cps.gate_ledger(contract)
    repo_eval = _repo_evaluator(contract)
    page_ready = {k: all(r["state"] == "PASS" for r in v) for k, v in ledger.items()}
    import yaml
    graph = yaml.safe_load((HERE / "ATLAS_GRAPH_v1.yaml").read_text(encoding="utf-8"))
    cohorts = contract["cohorts"]
    cov_by_repo = {r["repo"]: r for r in coverage["rows"]}
    p1 = {r["repo"]: r for r in pulses["pulses"][-1]["rows"]}
    repos = []
    for tier, names in (("TOP7", cohorts["top7"]), ("TOP14", cohorts["top14_extension"]), ("TOP21", cohorts["top21_extension"])):
        for name in names:
            c = cov_by_repo.get(name, {})
            repos.append({
                "repo": name, "tier": tier,
                "pulse_class": p1.get(name, {}).get("class"),
                "pulse_head": p1.get(name, {}).get("head"),
                "pulse_note": p1.get(name, {}).get("note"),
                "coverage_state": c.get("state"),
                "coverage_pct": (c.get("coverage") or {}).get("pct"),
                "coverage_gate": (c.get("coverage") or {}).get("gate_pct"),
                "baseline_sha": contract["exact_head_baseline"].get(name),
                "bd_items": [i["id"] for i in items if name in i["repos"]],
            })
    return {
        "schema": "missioncontrol.code_purple.page.v1",
        "authority_transfer": False,
        "build_sha": _head_sha(),
        "series_key": latest,
        "sources": [
            {"name": "DMAIC cohort contract", "path": cps.CONTRACT, "as_of": contract["mission_id"][-8:-4] + "-" + contract["mission_id"][-4:-2] + "-" + contract["mission_id"][-2:], "as_of_basis": "mission_id suffix"},
            {"name": "Top7 census pulse 1", "path": "mission-control/federation-atlas/TOP7_CENSUS_PULSES_v1.json", "as_of": pulses["pulses"][-1]["observed_on"], "as_of_basis": "observed_on"},
            {"name": "Coverage telemetry", "path": cps.COVERAGE, "as_of": coverage["captured_at"], "as_of_basis": "captured_at"},
            {"name": "Mission status snapshot", "path": "mission-control/v2/MC_MISSION_STATUS_CURRENT_v1.json", "as_of": status["snapshot_at"], "as_of_basis": "snapshot_at"},
            {"name": "GM-I-A federation topology", "path": cps.TOPOLOGY, "as_of": None, "as_of_basis": "no date in file"},
            {"name": "BD queue + series", "path": "mission-control/federation-atlas/CODE_PURPLE_ITERATION_SERIES_v1.json", "as_of": None, "as_of_basis": "ordinal " + latest},
        ],
        "cohort_states": {"top7": contract["current"]["top7_state"], "top14": contract["current"]["top14_state"], "top21": contract["current"]["top21_state"]},
        "evolution": {"level": contract["iteration_evolution"]["current_level"],
                      "active": contract["iteration_evolution"]["active_iteration"]["iteration_id"],
                      "active_outcome": contract["iteration_evolution"]["active_iteration"]["control_outcome"]},
        "ledger": ledger,
        "parity": {"top14": {"page": page_ready["top7_to_top14"], "repo": repo_eval["top14_promotion_ready"]},
                   "top21": {"page": page_ready["top14_to_top21"], "repo": repo_eval["top21_promotion_ready"]}},
        "queue": {"rules": queue["rules"], "items": items, "open_states": queue["open_states"]},
        "series": series["entries"],
        "beams": beams["beams"], "edges": beams["edges"], "critical_path": beams["critical_path"],
        "beam_metrics": beam_metrics(beams, items, ledger), "lanes": lanes(beams),
        "candidates": beams["candidates"], "triggers": beams["triggers"],
        "pulses": pulses, "repos": repos,
        "coverage_summary": coverage["fleet_summary"],
        "topology_edges": topology["edges"], "topology_provider": topology["provider"],
        "graph_edges": graph["edges"],
    }


def render(payload: dict, fragment: bool) -> str:
    body = TEMPLATE.read_text(encoding="utf-8")
    data = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    body = body.replace("/*__PAYLOAD__*/", data)
    if fragment:
        return body
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            '</head>\n<body>\n' + body + '\n</body>\n</html>\n')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--fragment", action="store_true", help="emit body content only (artifact hosts add the skeleton)")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    (out / "code-purple.html").write_text(render(payload, args.fragment), encoding="utf-8")
    (out / "code-purple.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"CODE_PURPLE_PAGE written={out / 'code-purple.html'} series={payload['series_key']} items={len(payload['queue']['items'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
