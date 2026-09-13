#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[4]
CREW = ROOT.parents[1]
sys.path.insert(0, str(ROOT.parent))
from rex_runtime_control import collect_history, evaluate_preflight, summarize_recurrence

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


def counterbalanced_tasks(tasks, habitat, source_sha):
    """Return deterministic pair order with opposite phase per habitat.

    The source-SHA parity changes the phase across source states while the habitat
    xor guarantees both A->B and B->A are observed in every Linux+Windows run.
    Unpaired tasks keep their manifest order and execute after paired tasks.
    """
    groups = OrderedDict()
    unpaired = []
    for task in tasks:
        pair_id = task.get("pair_id")
        if pair_id:
            groups.setdefault(pair_id, []).append(task)
        else:
            unpaired.append(task)
    source_phase = int(source_sha[-1], 16) % 2
    habitat_phase = 0 if habitat == "linux" else 1
    phase = source_phase ^ habitat_phase
    ordered = []
    metadata = {}
    for pair_id, members in groups.items():
        if len(members) != 2 or {m.get("variant") for m in members} != {"A", "B"}:
            raise SystemExit(f"FAIL counterbalance requires A/B pair: {pair_id}")
        members = sorted(members, key=lambda x: x["variant"], reverse=bool(phase))
        direction = "A_THEN_B" if members[0]["variant"] == "A" else "B_THEN_A"
        for position, member in enumerate(members, start=1):
            metadata[member["task_id"]] = {
                "pair_position": position,
                "pair_direction": direction,
                "counterbalance_phase": phase,
                "counterbalance_basis": "SOURCE_SHA_PARITY_XOR_HABITAT",
            }
            ordered.append(member)
    for task in unpaired:
        metadata[task["task_id"]] = {
            "pair_position": None,
            "pair_direction": None,
            "counterbalance_phase": phase,
            "counterbalance_basis": "SOURCE_SHA_PARITY_XOR_HABITAT",
        }
        ordered.append(task)
    return ordered, metadata, phase


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
    rex_history = collect_history([ROOT.parent / "history", out])
    proof_gate_bound = bool(MANIFEST.get("objective")) and bool(MANIFEST.get("comparison_rule")) and MANIFEST.get("promotion_allowed") is False
    ordered_tasks, order_metadata, counterbalance_phase = counterbalanced_tasks(MANIFEST["tasks"], args.habitat, source_sha)

    for execution_index, task in enumerate(ordered_tasks, start=1):
        if task["task_id"] in seen:
            raise SystemExit("FAIL duplicate task")
        seen.add(task["task_id"])
        if task["primary_crew_id"] not in CREW_IDS or any(x not in CREW_IDS for x in task["crew_combination"]):
            raise SystemExit(f"FAIL unknown crew in {task['task_id']}")
        if task["competency_dimension"] not in DIMS:
            raise SystemExit(f"FAIL unknown competency {task['competency_dimension']}")
        if set(task["applicable_rex_ids"]) - REX_IDS:
            raise SystemExit(f"FAIL unknown REX in {task['task_id']}")

        preflight = evaluate_preflight(
            checklist_schema=CHECKLIST["schema"],
            applicable_rex_ids=task["applicable_rex_ids"],
            facts={
                "namespace_registered": True,
                "vocabulary_registered": task["workload"]["kind"] in WORKLOADS,
                "yaml_mutation_planned": False,
                "yaml_lint_prechecked": False,
                "active_assignment_current": True,
                "proof_gate_bound": proof_gate_bound,
                "execution_context_reached": True,
            },
        )

        workload = task["workload"]
        started = datetime.now(timezone.utc).isoformat()
        t0 = time.perf_counter()
        disposition = "ACCEPT"
        error = None
        digest = None
        units = 0
        steps_executed = 0
        if preflight["payload_allowed"]:
            fn = WORKLOADS[workload["kind"]]
            steps_executed = 1
            try:
                digest, units = fn(int(workload["iterations"]), int(workload["workers"]))
            except Exception as exc:
                digest, units = None, 0
                disposition = "REJECT"
                error = repr(exc)
        else:
            disposition = "REJECT"
            error = f"REX_PREFLIGHT_BLOCKED:{','.join(preflight['blocking_rex_ids'])}"
        elapsed = round(time.perf_counter() - t0, 6) if steps_executed else 0.0
        ended = datetime.now(timezone.utc).isoformat()

        observed = list(preflight["triggered_rex_ids"])
        recurrence = summarize_recurrence(observed, rex_history)
        new_rex = sorted(rex_id for rex_id, level in recurrence["by_rex_id"].items() if level == "NEW")
        order = order_metadata[task["task_id"]]

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
            "execution_order": {
                "index": execution_index,
                **order,
            },
            "habitat": {"id": args.habitat, "runner_os": runner_os, "runner_arch": runner_arch, "runner_name": runner_name},
            "source_sha": source_sha,
            "run_id": run_id,
            "started_at": started,
            "ended_at": ended,
            "execute_seconds": elapsed,
            "steps_executed": steps_executed,
            "semantic_digest": digest,
            "disposition": disposition,
            "error": error,
            "promotion_allowed": False,
            "authority_transfer": False,
            "rex_preflight": preflight,
            "rex_postflight": {
                "rex_ids_observed": observed,
                "new_rex_signal": new_rex or None,
                "recurrence_level": recurrence["highest"],
                "recurrence_by_rex_id": recurrence["by_rex_id"],
                "preventive_action_effective": True if "REX-006" in task["applicable_rex_ids"] and disposition == "ACCEPT" else None,
                "ledger_update_required": bool(observed)
            }
        }
        (out / f"{args.habitat}__{task['task_id']}.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        receipts.append(receipt)
        for rex_id in observed:
            rex_history.setdefault("counts", {})[rex_id] = int(rex_history.get("counts", {}).get(rex_id, 0)) + 1
        if "REX-006" in task["applicable_rex_ids"] and disposition == "ACCEPT":
            controls = set(rex_history.get("preventive_controls", []))
            controls.add("REX-006")
            rex_history["preventive_controls"] = sorted(controls)
        print(json.dumps({"task_id": task["task_id"], "habitat": args.habitat, "strategy": task["allocation_strategy"], "execution_index": execution_index, "pair_direction": order["pair_direction"], "seconds": elapsed, "steps_executed": steps_executed, "blocking_rex_ids": preflight["blocking_rex_ids"], "disposition": disposition}, sort_keys=True))
    summary = {
        "schema": "missioncontrol.crew_frontier_run_summary.v1",
        "mission_id": MANIFEST["mission_id"],
        "habitat": args.habitat,
        "source_sha": source_sha,
        "run_id": run_id,
        "task_count": len(receipts),
        "accepted": sum(r["disposition"] == "ACCEPT" for r in receipts),
        "rejected": sum(r["disposition"] == "REJECT" for r in receipts),
        "preflight_blocked": sum(bool(r["rex_preflight"]["blocking_rex_ids"]) for r in receipts),
        "pair_members": sum(r["pair_id"] is not None for r in receipts),
        "counterbalance_phase": counterbalance_phase,
        "counterbalance_basis": "SOURCE_SHA_PARITY_XOR_HABITAT",
        "competency_promotions": 0,
        "authority_transfer": False
    }
    (out / f"{args.habitat}__RUN_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    if summary["rejected"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
