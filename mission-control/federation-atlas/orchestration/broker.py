"""Bounded local generator adapter and fail-closed remote *advisory* planner.

Handlers are trusted zero-argument synchronous callables. They normally launch
registered generators in separate subprocesses. Limits and declared path leases
apply to this invocation only: they do not coordinate other processes or hosts,
detect undeclared writes, kill hung callables, or authorize GitHub dispatch.

Contracts may carry metadata; ``required_paths`` checks literal paths relative
to ``root`` and output ``required_result_keys`` checks JSON object keys. Optional
validators supply generator-specific semantics. A false return or an exception
fails a contract. None from a validator means the check passed.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import copy
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import re
import threading
import time
from typing import Callable


HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "atlas_broker_gogreen_regime", HERE.parents[1] / "gogreen" / "regime_controller.py"
)
_regime = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_regime)
REGIMES = _regime.REGIMES
SHA = _regime.SHA
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_TERMINAL = {"succeeded", "failed", "blocked"}


def _integer(value, name, low=0, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        raise ValueError(f"{name}: integer outside permitted bounds")
    return value


def _utc(value):
    return _regime._utc(value)


def _path(value):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("paths must be nonempty literal relative paths")
    normalized = value.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if normalized.startswith("/") or ".." in parts or ":" in normalized:
        raise ValueError("paths must remain relative to the repository root")
    if any(mark in normalized for mark in ("*", "?", "[", "]")):
        raise ValueError("path leases require literal paths, not glob patterns")
    return str(PurePosixPath(normalized))


def _paths(values):
    if not isinstance(values, list):
        raise ValueError("paths must be a list")
    return sorted(set(_path(value) for value in values))


def _contract(value):
    if not isinstance(value, dict):
        raise ValueError("input_contract and output_contract must be objects")
    try:
        result = json.loads(json.dumps(value, allow_nan=False))
    except (ValueError, TypeError) as exc:
        raise ValueError("contracts must be JSON serializable") from exc
    if "required_paths" in result:
        result["required_paths"] = _paths(result["required_paths"])
    if "required_result_keys" in result:
        keys = result["required_result_keys"]
        if not isinstance(keys, list) or any(not isinstance(k, str) or not k for k in keys):
            raise ValueError("required_result_keys must contain nonempty strings")
    return result


def load_policy(policy=None):
    result = json.loads((HERE / "BROKER_POLICY_v1.json").read_text(encoding="utf-8"))
    if policy is not None:
        if not isinstance(policy, dict):
            raise ValueError("policy must be an object")
        result.update(policy)
    if result.get("schema") != "atlas.local-broker.policy.v1":
        raise ValueError("policy schema")
    for name in ("max_workers", "max_pending", "max_tasks", "default_workers", "default_max_pending"):
        _integer(result.get(name), name, 1)
    if result["default_workers"] > result["max_workers"]:
        raise ValueError("default_workers exceeds max_workers")
    if result["default_max_pending"] > result["max_pending"]:
        raise ValueError("default_max_pending exceeds max_pending")
    for name in ("snapshot_max_age_seconds", "cooldown_seconds"):
        _integer(result.get(name), name)
    caps = result.get("advisory_caps")
    if not isinstance(caps, dict) or set(caps) != set(REGIMES):
        raise ValueError("advisory_caps must preserve canonical GOGREEN regimes")
    for name, cap in caps.items():
        _integer(cap, f"advisory cap {name}")
    for name in ("dispatch_authorized", "merge_authorized", "authority_transfer"):
        if result.get(name) is not False:
            raise ValueError("local broker policy cannot grant remote authority")
    cohort = result.get("cohort")
    if cohort is not None:
        if not isinstance(cohort, dict) or not isinstance(cohort.get("repo"), str) or not cohort["repo"]:
            raise ValueError("policy cohort repo")
        if not isinstance(cohort.get("source_sha"), str) or not SHA.fullmatch(cohort["source_sha"]):
            raise ValueError("policy cohort source_sha")
    return result


def _tasks(tasks, policy):
    if not isinstance(tasks, list) or len(tasks) > policy["max_tasks"]:
        raise ValueError("tasks must be a bounded list")
    result = {}
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("id"), str) or not _ID.fullmatch(task["id"]):
            raise ValueError("task id")
        key = task["id"]
        if key in result:
            raise ValueError(f"duplicate task id: {key}")
        if not isinstance(task.get("repo"), str) or not task["repo"]:
            raise ValueError(f"task {key}: repo required")
        needs = task.get("needs")
        if not isinstance(needs, list) or any(not isinstance(n, str) for n in needs) or len(needs) != len(set(needs)):
            raise ValueError(f"task {key}: needs must be unique task ids")
        estimate = task.get("estimated_seconds")
        if estimate is not None and (type(estimate) not in (int, float) or not math.isfinite(estimate) or estimate < 0):
            raise ValueError(f"task {key}: invalid estimated_seconds")
        result[key] = {
            "id": key, "repo": task["repo"], "needs": sorted(needs),
            "read_paths": _paths(task.get("read_paths")),
            "write_paths": _paths(task.get("write_paths")),
            "estimated_seconds": estimate,
            "input_contract": _contract(task.get("input_contract")),
            "output_contract": _contract(task.get("output_contract")),
        }
    for key, task in result.items():
        missing = set(task["needs"]) - result.keys()
        if missing:
            raise ValueError(f"task {key}: unknown dependencies {sorted(missing)}")
    remaining, complete, stages = set(result), set(), []
    while remaining:
        stage = sorted(key for key in remaining if set(result[key]["needs"]) <= complete)
        if not stage:
            raise ValueError("task graph contains a cycle")
        stages.append(stage)
        remaining.difference_update(stage)
        complete.update(stage)
    return result, stages


def _overlap(left, right):
    a, b = PurePosixPath(left).parts, PurePosixPath(right).parts
    return a[:len(b)] == b or b[:len(a)] == a


def conflicts(left, right):
    """Declared same-root write/write or write/read overlap, including parents."""
    return any(_overlap(a, b) for a in left["write_paths"] for b in right["write_paths"] + right["read_paths"]) or any(
        _overlap(a, b) for a in left["read_paths"] for b in right["write_paths"]
    )


def _fair_order(keys, tasks, last_repo=None):
    groups = {}
    for key in sorted(keys):
        groups.setdefault(tasks[key]["repo"], []).append(key)
    repos = sorted(groups)
    if last_repo in repos:
        split = repos.index(last_repo) + 1
        repos = repos[split:] + repos[:split]
    order = []
    while any(groups.values()):
        for repo in repos:
            if groups[repo]:
                order.append(groups[repo].pop(0))
    return order


def _remote(snapshot, policy, tasks, now):
    result = {
        "status": "UNKNOWN", "reasons": [], "capacity_known": False,
        "observed_at": None, "age_seconds": None, "cohort": None,
        "queued": None, "running": None, "worker_slots": None,
        "reserved_capacity": None, "available_slots": None, "regime": None,
        "advisory_dispatch_slots": 0, "cooldown_remaining_seconds": None,
        "dispatch_authorized": False, "regime_authority": policy["regime_controller"],
    }
    if snapshot is None:
        result["reasons"] = ["no remote observation supplied"]
        return result
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be an object or None")
    for name in ("queued", "running", "worker_slots", "reserved_capacity"):
        if name in snapshot and snapshot[name] is not None:
            _integer(snapshot[name], name)
    regime = snapshot.get("regime")
    if regime is not None and regime not in REGIMES:
        raise ValueError("snapshot regime must come from the canonical GOGREEN vocabulary")
    if "complete_scope" in snapshot and type(snapshot["complete_scope"]) is not bool:
        raise ValueError("complete_scope must be a boolean")
    observed = snapshot.get("observed_at")
    if observed is None:
        result["reasons"] = ["missing observation timestamp"]
        return result
    when = _utc(observed)
    age = (now - when).total_seconds()
    result.update(observed_at=observed, age_seconds=age)
    if age < 0:
        result["reasons"] = ["observation is in the future"]
        return result
    if age > policy["snapshot_max_age_seconds"]:
        result.update(status="STALE", reasons=["observation exceeds freshness bound"])
        return result
    if snapshot.get("complete_scope") is not True:
        result.update(status="INCOMPLETE", reasons=["complete pool scope not established"])
        return result
    expected = policy.get("cohort")
    if expected is None:
        result.update(status="UNQUALIFIED", reasons=["expected repo/source_sha cohort not configured"])
        return result
    actual = {"repo": snapshot.get("repo"), "source_sha": snapshot.get("source_sha", snapshot.get("sha"))}
    repos = {task["repo"] for task in tasks.values()}
    if actual != expected or (repos and repos != {expected["repo"]}):
        result.update(status="COHORT_MISMATCH", reasons=["observation does not match the configured task cohort"])
        return result
    result["cohort"] = dict(expected)
    if any(snapshot.get(name) is None for name in ("queued", "running", "worker_slots", "reserved_capacity")):
        result["reasons"] = ["incomplete worker-slot counts"]
        return result
    total, occupied, reserved = (snapshot[name] for name in ("worker_slots", "running", "reserved_capacity"))
    if occupied + reserved > total:
        raise ValueError("occupied and reserved worker slots exceed the declared pool")
    cooldown = 0.0
    if snapshot.get("last_dispatch_at") is not None:
        since = (now - _utc(snapshot["last_dispatch_at"])).total_seconds()
        if since < 0:
            raise ValueError("last dispatch is in the future")
        cooldown = max(0.0, policy["cooldown_seconds"] - since)
    result.update(
        status="OBSERVED", capacity_known=True, queued=snapshot["queued"], running=occupied,
        worker_slots=total, reserved_capacity=reserved, available_slots=total-occupied-reserved,
        regime=regime, cooldown_remaining_seconds=cooldown,
        advisory_dispatch_slots=0 if cooldown or regime is None else min(total-occupied-reserved, policy["advisory_caps"][regime]),
    )
    if regime is None:
        result["reasons"].append("no canonical regime receipt supplied; advisory dispatch held")
    if cooldown:
        result["reasons"].append("configured advisory cooldown is active")
    return result


def plan(tasks, snapshot=None, policy=None, *, now=None):
    """Return a serializable local DAG plan; remote metrics remain advisory."""
    configured = load_policy(policy)
    checked, stages = _tasks(tasks, configured)
    clock = datetime.now(timezone.utc) if now is None else _utc(now)
    pairs = [[a, b] for i, a in enumerate(sorted(checked)) for b in sorted(checked)[i+1:] if conflicts(checked[a], checked[b])]
    return {
        "schema": "atlas.local-broker.plan.v1", "generated_at": clock.isoformat(),
        "task_count": len(checked), "stages": stages,
        "initial_eligible_order": _fair_order(stages[0], checked) if stages else [],
        "tasks": [checked[key] for key in sorted(checked)], "conflict_pairs": pairs,
        "local_bounds": {"workers": configured["default_workers"], "max_pending": configured["default_max_pending"]},
        "remote": _remote(snapshot, configured, checked, clock),
        "provisional_policy": configured["provisional"],
        "dispatch_authorized": False, "merge_authorized": False, "authority_transfer": False,
    }



def plan_slow_burn(tasks, snapshot=None, policy=None, *, now=None,
                   max_waves=8, max_per_wave=3, queue_limit=12):
    """Stage long-horizon disjoint local scouts, never remote jobs or mutations.

    This is a *projection* using the canonical broker's DAG, path-conflict and
    GOGREEN regime contracts. A later stage requires separately verified
    predecessor completion; mere inclusion in an earlier stage is not proof.
    """
    _integer(max_waves, "max_waves", 1, 12)
    _integer(max_per_wave, "max_per_wave", 1, 4)
    _integer(queue_limit, "queue_limit", 0, 100)
    base = plan(tasks, snapshot, policy, now=now)
    rows = {x["id"]: x for x in base["tasks"]}
    remote = base["remote"]
    # Unknown/partial, congested, stale or overloaded runner evidence
    # cannot be translated into remote slots, even if a local DAG exists.
    qualified = (remote["status"] == "OBSERVED"
                 and remote["regime"] in ("RECOVERING", "STABLE")
                 and remote["queued"] <= queue_limit
                 and remote["advisory_dispatch_slots"] > 0)
    advisory_remote = min(remote["advisory_dispatch_slots"], max_per_wave) if qualified else 0
    remaining = set(rows)
    projected = set()
    waves = []
    holds = {}
    for ordinal in range(1, max_waves + 1):
        eligible = {key for key in remaining
                    if set(rows[key]["needs"]) <= projected}
        if not eligible:
            break
        selected = []
        for key in _fair_order(eligible, rows):
            row = rows[key]
            if row["write_paths"]:
                holds[key] = "WRITE_REQUIRES_SOURCE_OWNER_AND_PATH_LEASE"
                continue
            if any(conflicts(row, rows[other]) for other in selected):
                holds[key] = "PATH_CONFLICT_WITH_SCOUT"
                continue
            if len(selected) == max_per_wave:
                break
            selected.append(key)
        if not selected:
            break
        waves.append({
            "index": ordinal,
            "task_ids": selected,
            "status": "STAGED_NOT_LAUNCHED" if ordinal == 1 else "CONDITIONAL_PREDECESSOR_PROOF",
            "required_before_run": [
                "EXACT_HEAD_SOURCE_AND_NEGATIVE_TESTS",
                "INDEPENDENT_PREDECESSOR_RECEIPTS" if ordinal > 1 else "SOURCE_READ_PERMISSION",
                "CAPACITY_AND_QUEUE_RECHECK",
            ],
            "remote_dispatch_slots_advisory_only": advisory_remote if ordinal == 1 else 0,
        })
        projected.update(selected)
        remaining.difference_update(selected)
    for key in sorted(remaining):
        if key not in holds:
            holds[key] = ("DEPENDENCY_NOT_PROVEN" if rows[key]["needs"]
                          else "WAVE_BUDGET_EXHAUSTED")
    return {
        "schema": "atlas.local-broker.slow-burn-plan.v1",
        "source": "mission-control/federation-atlas/orchestration/broker.py",
        "generated_at": base["generated_at"],
        "requested_waves": max_waves,
        "waves": waves,
        "packet_count": sum(len(w["task_ids"]) for w in waves),
        "held": [{"task_id": k, "reason": holds[k]} for k in sorted(holds)],
        "remote_observation_status": remote["status"],
        "remote_queue_depth": remote["queued"],
        "remote_advisory_slots": advisory_remote,
        "launches": 0,
        "verified_root_closures": None,
        "matched_coverage_delta_pp": None,
        "dispatch_authorized": False,
        "merge_authorized": False,
        "authority_transfer": False,
        "feedback_triggers": [
            "TERMINAL_FIRST_RED_OR_GOVERNANCE_FAILURE",
            "QUEUE_THRESHOLD_OR_AGE_REGRESSION",
            "SOURCE_SHA_OR_DENOMINATOR_DRIFT",
            "PREDECESSOR_RECEIPT_OR_PATH_LEASE_RETURN",
            "ELIGIBLE_INDEPENDENT_REVIEW_RETURN",
        ],
        "mip_dmaic": {
            "DEFINE": "one canonical source owner per root; non-overlapping scouts",
            "MEASURE": "queue, proof yield, source SHA, coverage opportunity and zero-covered assets",
            "ANALYZE": "root recurrence and blocked predecessor before new fan-out",
            "IMPROVE": "bounded disjoint source repairs after native first-red proof",
            "CONTROL": "exact-main independent recurrence proof, never a staged scout",
            "MIP": "modernize evidence; innovate bounded experiments; perpetuate qualified controls",
        },
    }


def _required_paths(contract, root):
    for relative in contract.get("required_paths", []):
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"contract path escapes the repository root: {relative}")
        if not target.exists():
            raise ValueError(f"required path is missing: {relative}")


def _quantile(values, fraction):
    return None if not values else sorted(values)[math.ceil(len(values)*fraction)-1]


def run_local(tasks, handlers, workers=2, max_pending=8, *, root=None, policy=None,
              input_validator: Callable | None = None, output_validator: Callable | None = None):
    """Run bounded local handlers, validating outputs before successors start.

    ``max_pending`` bounds the materialized ready buffer; eligible overflow is
    explicitly deferred in the finite task manifest. At most ``workers`` futures
    are submitted, so ThreadPoolExecutor's internal pending queue cannot flood.
    Handlers must implement any timeout: Python threads cannot safely kill them.
    """
    configured = load_policy(policy)
    _integer(workers, "workers", 1, configured["max_workers"])
    _integer(max_pending, "max_pending", 1, configured["max_pending"])
    checked, _ = _tasks(tasks, configured)
    if not isinstance(handlers, dict) or any(not callable(handlers.get(key)) for key in checked):
        raise ValueError("every task requires a registered callable handler")
    if any(value is not None and not callable(value) for value in (input_validator, output_validator)):
        raise ValueError("validators must be callable")
    base = Path.cwd().resolve() if root is None else Path(root).resolve()
    if not base.is_dir():
        raise ValueError("repository root must be an existing directory")
    began_utc = datetime.now(timezone.utc).isoformat()
    began = time.monotonic()
    lock = threading.Lock()
    rows = {key: {"state": "pending", "repo": task["repo"], "needs": task["needs"],
                  "ready_at_seconds": None, "started_at_seconds": None,
                  "execution_finished_at_seconds": None, "verify_started_at_seconds": None,
                  "finished_at_seconds": None, "ready_wait_seconds": None,
                  "execution_seconds": None, "verification_seconds": None,
                  "result": None, "error": None, "events": []} for key, task in checked.items()}
    active = peak_active = peak_ready = peak_deferred = 0
    deferred_ids = set()
    last_repo = None
    ready, futures = set(), {}

    def transition(key, state):
        moment = time.monotonic() - began
        rows[key]["state"] = state
        rows[key]["events"].append({"state": state, "at_seconds": moment})
        return moment

    def fill_ready():
        nonlocal peak_ready, peak_deferred
        # The caller holds lock. Refill after each submission as well as after a
        # completion, so a one-item buffer can still feed several local workers.
        eligible = [key for key in checked if rows[key]["state"] in {"pending", "deferred_ready"}
                    and all(rows[n]["state"] == "succeeded" for n in checked[key]["needs"])]
        for key in _fair_order(eligible, checked, last_repo):
            if rows[key]["ready_at_seconds"] is None:
                # Eligibility begins when the last verified prerequisite ends,
                # not when this polling-free coordinator next notices it.
                rows[key]["ready_at_seconds"] = max(
                    (rows[parent]["finished_at_seconds"] for parent in checked[key]["needs"]), default=0.0
                )
            target = "ready" if len(ready) < max_pending else "deferred_ready"
            if rows[key]["state"] != target:
                transition(key, target)
            if target == "ready":
                ready.add(key)
            else:
                deferred_ids.add(key)
        peak_ready = max(peak_ready, len(ready))
        peak_deferred = max(peak_deferred, sum(row["state"] == "deferred_ready" for row in rows.values()))

    def execute(key):
        nonlocal active, peak_active
        task, row = checked[key], rows[key]
        with lock:
            active += 1
            peak_active = max(peak_active, active)
            row["started_at_seconds"] = transition(key, "running")
            row["ready_wait_seconds"] = row["started_at_seconds"] - row["ready_at_seconds"]
        phase = "input_contract"
        try:
            _required_paths(task["input_contract"], base)
            if input_validator is not None and input_validator(copy.deepcopy(task)) is False:
                raise ValueError("input validator rejected task")
            phase = "handler"
            result = handlers[key]()
            with lock:
                row["execution_finished_at_seconds"] = time.monotonic() - began
                row["verify_started_at_seconds"] = transition(key, "verifying")
            phase = "output_contract"
            _required_paths(task["output_contract"], base)
            keys = task["output_contract"].get("required_result_keys", [])
            if keys and (not isinstance(result, dict) or any(name not in result for name in keys)):
                raise ValueError("output lacks required result keys")
            if output_validator is not None and output_validator(copy.deepcopy(task), result) is False:
                raise ValueError("output validator rejected task")
            # Copy JSON data so a handler cannot mutate an admitted receipt later.
            serialized = json.loads(json.dumps(result, allow_nan=False))
            with lock:
                row["result"] = serialized
                row["finished_at_seconds"] = transition(key, "succeeded")
        except Exception as exc:
            with lock:
                row["error"] = {"phase": phase, "type": type(exc).__name__, "message": str(exc)}
                row["finished_at_seconds"] = transition(key, "failed")
        finally:
            with lock:
                finished = row["execution_finished_at_seconds"]
                if finished is None:
                    finished = time.monotonic() - began
                    row["execution_finished_at_seconds"] = finished
                row["execution_seconds"] = finished - row["started_at_seconds"]
                if row["verify_started_at_seconds"] is not None:
                    row["verification_seconds"] = row["finished_at_seconds"] - row["verify_started_at_seconds"]
                active -= 1

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="atlas-local") as executor:
        while any(row["state"] not in _TERMINAL for row in rows.values()):
            with lock:
                # Close the transitive failed-dependency set before admitting work.
                changed = True
                while changed:
                    changed = False
                    for key in sorted(checked):
                        if rows[key]["state"] not in {"pending", "deferred_ready"}:
                            continue
                        failed = [n for n in checked[key]["needs"] if rows[n]["state"] in {"failed", "blocked"}]
                        if failed:
                            rows[key]["error"] = {"phase": "dependency", "blocked_by": failed}
                            rows[key]["finished_at_seconds"] = transition(key, "blocked")
                            changed = True
                fill_ready()
            while len(futures) < workers:
                with lock:
                    fill_ready()
                selection = next((key for key in _fair_order(ready, checked, last_repo)
                                  if not any(conflicts(checked[key], checked[other]) for other in futures.values())), None)
                if selection is None:
                    break
                ready.remove(selection)
                last_repo = checked[selection]["repo"]
                with lock:
                    transition(selection, "reserved")
                futures[executor.submit(execute, selection)] = selection
            if futures:
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda item: futures[item]):
                    future.result()
                    del futures[future]
            elif any(row["state"] not in _TERMINAL for row in rows.values()):
                raise RuntimeError("validated local DAG made no progress")
    waits = [row["ready_wait_seconds"] for row in rows.values() if row["ready_wait_seconds"] is not None]
    elapsed = time.monotonic() - began
    success = all(row["state"] == "succeeded" for row in rows.values())
    return {
        "schema": "atlas.local-broker.receipt.v1", "started_at": began_utc,
        "evidence_class": "LOCAL_GENERATOR_EXECUTION_NOT_REMOTE_CAPACITY",
        "outcome": "LOCAL_GENERATORS_PASS" if success else "LOCAL_GENERATORS_FAIL", "success": success,
        "bounds": {"workers": workers, "max_pending": max_pending, "task_count": len(checked)},
        "tasks": {key: rows[key] for key in sorted(rows)},
        "metrics": {
            "elapsed_seconds": elapsed, "max_running": peak_active, "peak_ready": peak_ready,
            "deferred_ready_count": len(deferred_ids), "peak_deferred_ready": peak_deferred,
            "ready_wait_sample_count": len(waits), "ready_wait_p50_seconds": _quantile(waits, .5),
            "ready_wait_p95_seconds": _quantile(waits, .95),
            "succeeded": sum(row["state"] == "succeeded" for row in rows.values()),
            "failed": sum(row["state"] == "failed" for row in rows.values()),
            "blocked": sum(row["state"] == "blocked" for row in rows.values()),
        },
        "local_process_only": True, "automatic_retries": False,
        "remote_capacity": "UNKNOWN", "dispatch_authorized": False,
        "merge_authorized": False, "authority_transfer": False,
    }
