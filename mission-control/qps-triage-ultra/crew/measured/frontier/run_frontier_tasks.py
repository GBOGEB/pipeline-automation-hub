#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
CREW = ROOT.parents[1]
MANIFEST = json.loads((ROOT / "FRONTIER_TASK_MANIFEST_v1.json").read_text(encoding="utf-8"))
CHECKLIST = json.loads((ROOT.parent / "REX_REUSE_CHECKLIST_v1.json").read_text(encoding="utf-8"))
REGISTRY = json.loads((CREW / "CREW_REGISTRY_v1.json").read_text(encoding="utf-8"))
COMP = json.loads((CREW / "COMPETENCY_MATRIX_v1.json").read_text(encoding="utf-8"))
CREW_IDS = {x["crew_id"] for x in REGISTRY["crew"]}
REX_IDS = {x["rex_id"] for x in CHECKLIST["checklist"]}
DIMS = set(COMP["dimensions"])


def sha(value):
    return hashlib.sha256(value).hexdigest()


def json_files():
    return sorted(p for p in CREW.rglob("*.json") if "receipts" not in p.parts and "aggregate" not in p.parts)


def json_census(iterations, workers):
    paths = json_files()
    def one(p):
        raw = p.read_bytes()
        json.loads(raw.decode("utf-8"))
        return str(p.relative_to(REPO)), hashlib.sha256(raw).hexdigest(), len(raw)
    records = None
    for _ in range(iterations):
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                records = list(ex.map(one, paths))
        else:
            records = [one(p) for p in paths]
    payload = "\n".join(f"{a}|{b}|{c}" for a,b,c in sorted(records)).encode()
    return sha(payload), len(paths) * iterations


def validation_bundle(iterations, workers):
    commands = [
        [sys.executable, str(CREW / "validate_crew_system.py")],
        [sys.executable, str(CREW / "validate_crew_telemetry.py")],
        [sys.executable, str(ROOT.parent / "validate_rex_reuse.py")],
        [sys.executable, str(ROOT.parent / "validate_evidence_returns.py")],
    ]
    def one(cmd):
        p = subprocess.run(cmd, cwd=REPO, text=True, capture_output=True)
        if p.returncode != 0:
            raise RuntimeError(f"validation failed: {' '.join(cmd)}\n{p.stdout}\n{p.stderr}")
        lines = [x for x in p.stdout.splitlines() if x.strip()]
        marker = lines[-1] if lines else "PASS_EMPTY"
        try:
            obj = json.loads(marker)
            marker = str(obj.get("status", marker))
        except Exception:
            pass
        return Path(cmd[-1]).name, marker
    results = []
    for _ in range(iterations):
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                results = list(ex.map(one, commands))
        else:
            results = [one(c) for c in commands]
    payload = "\n".join(f"{a}|{b}" for a,b in sorted(results)).encode()
    return sha(payload), len(commands) * iterations


def analytics_sweep(iterations, workers):
    ranges = []
    step = (iterations + workers - 1) // workers
    for start in range(0, iterations, step):
        ranges.append((start, min(iterations, start + step)))
    def calc(bounds):
        a,b = bounds
        total = 0
        for i in range(a,b):
            total += ((i * 2654435761) ^ (i >> 3)) % 1000003
        return total
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            total = sum(ex.map(calc, ranges))
    else:
        total = sum(calc(r) for r in ranges)
    return sha(str(total).encode()), iterations


def rex_surface_scan(iterations, workers):
    files = sorted(p for p in (REPO / "mission-control").rglob("*") if p.is_file() and p.suffix.lower() in {".json", ".yaml", ".yml", ".md", ".py"})
    counts = None
    for _ in range(iterations):
        counts = {f"REX-{i:03d}": 0 for i in range(1,7)}
        for p in files:
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for rid in counts:
                counts[rid] += text.count(rid)
    payload = json.dumps(counts, sort_keys=True, separators=(",", ":")).encode()
    return sha(payload), len(files) * iterations


def topology_crosswalk(iterations, workers):
    targets = [
        REPO / "mission-control/qps-triage-ultra/architecture.yaml",
        CREW / "CREW_REGISTRY_v1.json",
        CREW / "COMPETENCY_MATRIX_v1.json",
        CREW / "ROLE_DEVELOPMENT_POLICY_v1.json",
    ]
    facts = []
    for _ in range(iterations):
        facts = []
        for p in targets:
            raw = p.read_bytes()
            facts.append((str(p.relative_to(REPO)), len(raw), hashlib.sha256(raw).hexdigest()))
    payload = "\n".join(f"{a}|{b}|{c}" for a,b,c in sorted(facts)).encode()
    return sha(payload), len(targets) * iterations


WORKLOADS = {
    "json_census": json_census,
    "validation_bundle": validation_bundle,
    "analytics_sweep": analytics_sweep,
    "rex_surface_scan": rex_surface_scan,
    "topology_crosswalk": topology_crosswalk,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--habitat", required=True, choices=["linux", "windows"])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    source_sha = os.environ.get("MC_SOURCE_SHA", "")
    checkout_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    if len(source_sha) != 40 or source_sha != checkout_sha:
        raise SystemExit(f"FAIL exact SHA: source={source_sha} checkout={checkout_sha}")
    run_id = str(os.environ.get("GITHUB_RUN_ID", "LOCAL_UNBOUND"))
    runner_name = os.environ.get("RUNNER_NAME", "LOCAL_UNBOUND")
    runner_os = os.environ.get("RUNNER_OS", args.habitat)
    runner_arch = os.environ.get("RUNNER_ARCH", "UNKNOWN")
    seen = set()
    receipts = []
    for task in MANIFEST["tasks"]:
        if task["task_id"] in seen:
            raise SystemExit("FAIL duplicate task")
        seen.add(task["task_id"])
        if task["primary_crew_id"] not in CREW_IDS or any(x not in CREW_IDS for x in task["crew_combination"]):
            raise SystemExit(f"FAIL unknown crew in {task['task_id']}")
        if task["competency_dimension"] not in DIMS:
            raise SystemExit(f"FAIL unknown competency {task['competency_dimension']}")
        if set(task["applicable_rex_ids"]) - REX_IDS:
            raise SystemExit(f"FAIL unknown REX in {task['task_id']}")
        workload = task["workload"]
        fn = WORKLOADS[workload["kind"]]
        started = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()
        disposition = "ACCEPT"
        error = None
        try:
            digest, units = fn(int(workload["iterations"]), int(workload["workers"]))
        except Exception as exc:
            digest, units = None, 0
            disposition = "REJECT"
            error = repr(exc)
        elapsed = round(time.perf_counter() - t0, 6)
        ended = datetime.now(timezone.utc).isoformat()
        observed = []
        if disposition == "REJECT" and "REX-006" in task["applicable_rex_ids"]:
            observed.append("REX-006")
        receipt = {
            "schema": "missioncontrol.crew_frontier_runtime_receipt.v1",
            "mission_id": MANIFEST["mission_id"],
            "assignment_id": task["assignment_id"],
            "task_id": task["task_id"],
            "pair_id": task["pair_id"],
            "variant": task["variant"],
            "allocation_strategy": task["allocation_strategy"],
            "primary_crew_id": task["primary_crew_id"],
            "crew_combination": task["crew_combination"],
            "competency_dimension": task["competency_dimension"],
            "predeclared_task_level": task["predeclared_task_level"],
            "workload": workload,
            "workload_units": units,
            "habitat": {"id": args.habitat, "runner_os": runner_os, "runner_arch": runner_arch, "runner_name": runner_name},
            "source_sha": source_sha,
            "run_id": run_id,
            "started_at": started,
            "ended_at": ended,
            "execute_seconds": elapsed,
            "steps_executed": 1,
            "semantic_digest": digest,
            "disposition": disposition,
            "error": error,
            "promotion_allowed": False,
            "authority_transfer": False,
            "rex_preflight": {
                "checklist_version": CHECKLIST["schema"],
                "rex_ids_checked": task["applicable_rex_ids"],
                "blocking_rex_ids": [],
                "manual_checklist_items": "NOT_ASSESSED_BY_RUNTIME_WRAPPER"
            },
            "rex_postflight": {
                "rex_ids_observed": observed,
                "recurrence_level": "NEW" if observed else None,
                "preventive_action_effective": True if "REX-006" in task["applicable_rex_ids"] and disposition == "ACCEPT" else None,
                "ledger_update_required": bool(observed)
            }
        }
        (out / f"{args.habitat}__{task['task_id']}.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        receipts.append(receipt)
        print(json.dumps({"task_id": task["task_id"], "habitat": args.habitat, "strategy": task["allocation_strategy"], "seconds": elapsed, "disposition": disposition}, sort_keys=True))
    summary = {
        "schema": "missioncontrol.crew_frontier_run_summary.v1",
        "mission_id": MANIFEST["mission_id"],
        "habitat": args.habitat,
        "source_sha": source_sha,
        "run_id": run_id,
        "task_count": len(receipts),
        "accepted": sum(r["disposition"] == "ACCEPT" for r in receipts),
        "rejected": sum(r["disposition"] == "REJECT" for r in receipts),
        "pair_members": sum(r["pair_id"] is not None for r in receipts),
        "competency_promotions": 0,
        "authority_transfer": False
    }
    (out / f"{args.habitat}__RUN_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    if summary["rejected"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
