#!/usr/bin/env python3
"""N3 warm-handler pilot inside the EXISTING Method Atlas local broker.

Executes two distinct real producers: main.validate_profile and G9.build.
The existing broker.run_local owns 4-task DAG, path conflict admission,
nonzero step and actual wall-clock receipts; this module registers handlers
without modifying the broker or its max_workers=4 policy.

Cold modes invoke each producer's existing CLI. Warm modes import the same
source once, then invoke those public functions in broker-bounded threads.
Four matched same-runner blocks compare cold/warm workers 1/2/4; invalid
census/clock cases must block the join, and post-producer hash tampering
must fail output validation. All output goes to temporary directories.
Not remote dispatch, native fleet 4-pulse proof, production adoption or
engineering credit.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import html
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ATLAS = Path("mission-control/federation-atlas/orchestration/main.py")
BROKER = Path("mission-control/federation-atlas/orchestration/broker.py")
G9 = Path("mission-control/gogreen/outcome_convergence/outcome_flight.py")
FIXTURE = Path("mission-control/gogreen/outcome_convergence/samples/native_full_window_20261017.json")
PROFILE = Path("mission-control/federation-atlas/orchestration/PIPELINE_CONTRACTS_v1.json")
POLICY = Path("mission-control/federation-atlas/orchestration/BROKER_POLICY_v1.json")
SOURCE_FILES = (ATLAS, BROKER, G9, FIXTURE, PROFILE, POLICY)
MODES = {"cold1": ("CLI_PER_TASK", 1), "cold2": ("CLI_PER_TASK", 2),
         "cold4": ("CLI_PER_TASK", 4),
         "warm1": ("PRELOADED_FUNCTIONS", 1), "warm2": ("PRELOADED_FUNCTIONS", 2),
         "warm4": ("PRELOADED_FUNCTIONS", 4)}
EXPECTED = {"baseline": (57, 46, 10, 1), "counterfactual": (57, 45, 11, 1)}
G9_MEMBERS = {"metrics.json", "sipoc_dag.json", "source_window.json", "index.html"}
SHA40 = re.compile(r"^[0-9a-f]{40}$")
NEGATIVE_ERRORS = {"invalid_census": "incomplete or overlarge first-page census",
                   "invalid_clock": "invalid clock progression"}
SCHEMA = "method-atlas.warm-broker-pilot.v1"


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False,
                       ensure_ascii=True) + "\n").encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def demand(condition, reason):
    if not condition:
        raise ValueError(reason)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    demand(spec is not None and spec.loader is not None, "LOCAL_PRODUCER_IMPORT_UNAVAILABLE")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def pin(root, head):
    demand(bool(SHA40.fullmatch(head or "")), "SOURCE_HEAD_SHA_INVALID")
    p = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                       capture_output=True, text=True, timeout=10, check=False)
    demand(p.returncode == 0 and p.stdout.strip() == head, "CHECKOUT_HEAD_MISMATCH")
    return head


def source_hashes(root):
    return {p.as_posix(): digest((root / p).read_bytes()) for p in SOURCE_FILES}


def input_variants(root):
    base = json.loads((root / FIXTURE).read_bytes())
    changed = copy.deepcopy(base)
    row = next((r for c in changed["cohorts"] for r in c["runs"]
                if r.get("conclusion") == "success"), None)
    demand(row is not None, "NO_SUCCESS_FOR_COUNTERFACTUAL")
    row["conclusion"] = "failure"
    invalid = copy.deepcopy(base)
    invalid["cohorts"][0]["returned_count"] += 1
    clock = copy.deepcopy(base)
    clock["cohorts"][0]["runs"][0]["run_started_at"] = "2026-10-15T00:00:00Z"
    return {"baseline": base, "counterfactual": changed,
            "invalid_census": invalid, "invalid_clock": clock}


def read_g9(out, head, variant):
    demand(out.is_dir() and set(x.name for x in out.iterdir()) ==
           G9_MEMBERS | {"manifest.json"}, "G9_OUTPUT_MEMBER_SET_INVALID")
    manifest = json.loads((out / "manifest.json").read_bytes())
    demand(manifest.get("source_sha") == head and
           manifest.get("merge_authorized") is False and
           set(manifest.get("files") or {}) == G9_MEMBERS,
           "G9_SOURCE_HEAD_OR_AUTHORITY_INVALID")
    for name, expected in manifest["files"].items():
        demand(digest((out / name).read_bytes()) == expected,
               "G9_CURRENT_MEMBER_SHA_MISMATCH")
    values = json.loads((out / "metrics.json").read_bytes())
    counts = (values.get("total_native_runs"),
              values.get("native_terminal_success"),
              values.get("native_terminal_failure"),
              values.get("native_terminal_cancelled"))
    demand(counts == EXPECTED[variant], "G9_SEMANTIC_COUNTS_CHANGED")
    return {"member_sha": dict(sorted(manifest["files"].items())),
            "semantic_counts": list(counts),
            "members_sha256": digest(canonical(manifest["files"]))}


def read_profile(out, head):
    demand(out.is_dir() and set(x.name for x in out.iterdir()) ==
           {"source-check.json"}, "METHOD_PROFILE_MEMBERS_INVALID")
    obj = json.loads((out / "source-check.json").read_bytes())
    demand(obj.get("schema") == "missioncontrol.orchestration.source_check.v1"
           and obj.get("status") == "PASS"
           and obj.get("remote_dispatch") is False
           and type(obj.get("blocks")) is int and obj["blocks"] > 0
           and type(obj.get("joins")) is int and obj["joins"] > 0,
           "METHOD_PROFILE_SEMANTIC_OR_AUTHORITY_MISMATCH")
    return {"sha256": digest((out / "source-check.json").read_bytes()),
            "blocks": obj["blocks"], "joins": obj["joins"]}


def tasks():
    paths = [p.as_posix() for p in SOURCE_FILES]
    specs = [
        ("pin", [], [p.as_posix() for p in (POLICY, PROFILE)], []),
        ("profile", ["pin"], [ATLAS.as_posix(), PROFILE.as_posix()],
         ["n3/profile"]),
        ("g9", ["pin"], [G9.as_posix(), FIXTURE.as_posix()],
         ["n3/g9"]),
        ("join", ["profile", "g9"], ["n3/profile", "n3/g9"], ["n3/join"]),
    ]
    return [{"id": identity, "repo": "GBOGEB/pipeline-automation-hub",
             "needs": needs, "read_paths": reads, "write_paths": writes,
             "estimated_seconds": None,
             "input_contract": {"required_paths": [p for p in reads if p in paths]},
             "output_contract": {"required_result_keys": ["status", "output_files_sha256"]}}
            for identity, needs, reads, writes in specs]


def _cli(args, root, head):
    p = subprocess.run(args, cwd=root, capture_output=True, text=True,
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                       timeout=35, check=False)
    return p


def trial(root, head, location, mode, variant, pool, files, injected=False):
    """Return only verified/sanitized broker receipt. No claim of native evidence."""
    backend, workers = MODES[mode]
    root, location = Path(root).resolve(), Path(location).resolve()
    demand(location != root and not location.is_relative_to(root), "PILOT_OUTPUT_IN_CHECKOUT")
    demand(not location.exists() or not any(location.iterdir()), "NONEMPTY_PILOT_OUTPUT")
    demand(variant in (*EXPECTED, *NEGATIVE_ERRORS) and
           type(injected) is bool and not (injected and variant in NEGATIVE_ERRORS),
           "INVALID_PILOT_VARIANT")
    location.mkdir(parents=True, exist_ok=True)
    input_path = files[variant]
    output_profile = location / "profile"
    output_g9 = location / "g9"
    output_join = location / "join"
    expected_hashes = source_hashes(root)

    def source_pin():
        pin(root, head)
        demand(source_hashes(root) == expected_hashes, "SOURCE_BYTES_CHANGED")
        return {"status": "SOURCE_PINNED", "output_files_sha256": expected_hashes}

    def source_profile():
        if backend == "CLI_PER_TASK":
            p = _cli([sys.executable, str(root / ATLAS), "check",
                      "--root", str(root), "--head", head], root, head)
            demand(p.returncode == 0, "METHOD_PROFILE_COLD_CLI_FAILED")
            value = json.loads(p.stdout)
        else:
            value = pool["atlas"].validate_profile(root)
        output_profile.mkdir()
        (output_profile / "source-check.json").write_bytes(canonical(value))
        return {"status": "SOURCE_PROFILE_CREATED",
                "output_files_sha256": {
                    "source-check.json": digest((output_profile / "source-check.json").read_bytes())}}

    def outcome():
        if backend == "CLI_PER_TASK":
            p = _cli([sys.executable, str(root / G9), "--input",
                      str(input_path), "--out", str(output_g9),
                      "--source-sha", head], root, head)
            if variant in NEGATIVE_ERRORS:
                demand(p.returncode != 0 and NEGATIVE_ERRORS[variant] in p.stderr,
                       "G9_INVALID_COLD_INPUT_NOT_REJECTED")
                raise ValueError(NEGATIVE_ERRORS[variant])
            demand(p.returncode == 0, "G9_COLD_PRODUCER_FAILED")
        else:
            pool["g9"].build(copy.deepcopy(pool["inputs"][variant]), output_g9, head)
        observed = read_g9(output_g9, head, variant)
        # A post-producer fault must be caught by broker.output_validator,
        # not by the producer's own handler validation.
        if injected:
            (output_g9 / "metrics.json").write_bytes(b'{"tampered":true}\n')
        return {"status": "G9_PRODUCT_CREATED", "output_files_sha256":
                observed["member_sha"] | {"manifest.json":
                    digest((output_g9 / "manifest.json").read_bytes())}}

    def assemble():
        profile = read_profile(output_profile, head)
        g9 = read_g9(output_g9, head, variant)
        obj = {"schema": "method-atlas.warm-broker-join.v1",
               "source_sha": head, "profile_sha256": profile["sha256"],
               "profile_block_count": profile["blocks"], "profile_join_count": profile["joins"],
               "g9_members_sha256": g9["members_sha256"],
               "g9_semantic_counts": g9["semantic_counts"],
               "source_variant_sha256": digest(input_path.read_bytes()),
               "producer_paths": [ATLAS.as_posix(), G9.as_posix()],
               "merge_authorized": False, "dispatch_authorized": False}
        output_join.mkdir()
        (output_join / "join.json").write_bytes(canonical(obj))
        return {"status": "SOURCE_BOUND_FAN_IN_VERIFIED",
                "output_files_sha256": {"join.json": digest(
                    (output_join / "join.json").read_bytes())}}

    def output_validator(task, result):
        identity = task["id"]
        if identity == "pin":
            demand(result["output_files_sha256"] == expected_hashes,
                   "PIN_RESULT_STALE_SOURCE_SHA")
        if identity == "profile":
            valid = read_profile(output_profile, head)
            demand(result["output_files_sha256"]["source-check.json"] == valid["sha256"],
                   "PROFILE_RESULT_HASH_MISMATCH")
        if identity == "g9":
            # Injected post-production corruption hits here BEFORE fan-in admission.
            observed = read_g9(output_g9, head, variant)
            demand(result["output_files_sha256"]["metrics.json"] ==
                   observed["member_sha"]["metrics.json"], "G9_RESULT_HASH_MISMATCH")
        if identity == "join":
            actual = digest((output_join / "join.json").read_bytes())
            demand(actual == result["output_files_sha256"]["join.json"],
                   "JOIN_RESULT_MEMBER_TAMPER")
            observed = json.loads((output_join / "join.json").read_bytes())
            demand(observed["profile_sha256"] == read_profile(output_profile, head)["sha256"]
                   and observed["g9_members_sha256"] ==
                   read_g9(output_g9, head, variant)["members_sha256"],
                   "JOIN_CAUSAL_SOURCE_MEMBER_MISMATCH")
        return True

    callbacks = {"pin": source_pin, "profile": source_profile,
                 "g9": outcome, "join": assemble}
    receipt = pool["broker"].run_local(tasks(), callbacks, workers=workers,
                                       max_pending=4, root=root, output_validator=output_validator)
    is_negative = variant in NEGATIVE_ERRORS or injected
    state = {k: v["state"] for k, v in receipt["tasks"].items()}
    expected = ({"pin": "succeeded", "profile": "succeeded",
                 "g9": "failed", "join": "blocked"} if is_negative else
                {"pin": "succeeded", "profile": "succeeded",
                 "g9": "succeeded", "join": "succeeded"})
    demand(state == expected and receipt["success"] is (not is_negative),
           "BROKER_CAUSAL_STATE_OR_BLOCK_PROPAGATION_INVALID")
    if is_negative:
        demand(not output_join.exists(), "NEGATIVE_FAN_IN_WROTE_OUTPUT")
        phase = receipt["tasks"]["g9"]["error"]["phase"]
        demand(phase == ("output_contract" if injected else "handler"),
               "G9_NEGATIVE_FAILED_IN_WRONG_PHASE")
        if injected:
            demand(receipt["tasks"]["g9"]["error"]["type"] == "ValueError",
                   "G9_TAMPER_NOT_REJECTED")
        else:
            demand(NEGATIVE_ERRORS[variant] in receipt["tasks"]["g9"]["error"]["message"],
                   "G9_NEGATIVE_WRONG_CAUSAL_SIGNATURE")
    else:
        demand(output_join.is_dir() and (output_join / "join.json").is_file(),
               "POSITIVE_FAN_IN_MISSING")
    limited = {
        "mode": mode, "variant": variant, "injected": injected,
        "backend": backend, "workers": workers,
        "outcome": receipt["outcome"], "state": state,
        "elapsed_seconds": round(receipt["metrics"]["elapsed_seconds"], 6),
        "ready_p95_seconds": round(receipt["metrics"]["ready_wait_p95_seconds"], 6),
        "max_running": receipt["metrics"]["max_running"],
        "dependency_count": 4, "verified_outputs": 2 if not is_negative else 1,
        "accepted_fan_in": not is_negative,
        "fan_in_sha256": (digest((output_join / "join.json").read_bytes())
                          if not is_negative else None),
        "profile_sha256": read_profile(output_profile, head)["sha256"],
        "g9_semantic_counts": (read_g9(output_g9, head, variant)["semantic_counts"]
                                if not is_negative else None),
        "error_type": (receipt["tasks"]["g9"]["error"]["type"] if is_negative else None),
        "error_phase": (receipt["tasks"]["g9"]["error"]["phase"] if is_negative else None),
        "source_head": head,
    }
    return limited, receipt


def summary(rows, modes):
    by_mode = {}
    for mode in modes:
        positives = [r for r in rows if r["mode"] == mode and
                     r["variant"] in EXPECTED and not r["injected"]]
        negatives = [r for r in rows if r["mode"] == mode and
                     (r["variant"] in NEGATIVE_ERRORS or r["injected"])]
        demand(positives and len(positives) == len(negatives),
               "POSITIVE_NEGATIVE_PAIRS_INCOMPLETE")
        by_mode[mode] = {
            "backend": MODES[mode][0], "workers": MODES[mode][1],
            "positive_dags": len(positives), "negative_dags": len(negatives),
            "median_positive_wall_seconds": round(statistics.median(
                r["elapsed_seconds"] for r in positives), 6),
            "median_invalid_wall_seconds": round(statistics.median(
                r["elapsed_seconds"] for r in negatives), 6),
            "median_ready_p95_seconds": round(statistics.median(
                r["ready_p95_seconds"] for r in positives), 6),
            "verified_products": len(positives) * 2 + len(negatives),
            "blocked_fan_in": len(negatives),
        }
    speedups = {}
    for workers in (1, 2, 4):
        cold, warm = "cold" + str(workers), "warm" + str(workers)
        if cold in by_mode and warm in by_mode:
            speedups[str(workers)] = round(
                by_mode[cold]["median_positive_wall_seconds"] /
                by_mode[warm]["median_positive_wall_seconds"], 4)
    return {"by_mode": by_mode, "cold_to_warm_speedup_by_worker_count": speedups,
            "ci": None, "independent_native_fleet_pulses": 0,
            "interpretation": "DESCRIPTIVE_CORRELATED_LOCAL_BROKER_RUNS_ONLY"}


def render(report):
    rows = []
    for mode, r in report["summary"]["by_mode"].items():
        rows.append("<tr><td><code>" + html.escape(mode) + "</code></td><td>" +
                    str(r["workers"]) + "</td><td>" + html.escape(r["backend"]) +
                    "</td><td>" + str(r["median_positive_wall_seconds"]) +
                    "</td><td>" + str(r["blocked_fan_in"]) + "</td></tr>")
    return """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Method Atlas N3 | Warm broker</title><style>body{background:#1b0d2d;color:#f7edf9;max-width:1060px;margin:auto;padding:25px;font:15px/1.5 Aptos,system-ui,sans-serif}h1{font-size:2rem}h2{color:#f3bde7}code{color:#f9c7ef;font-family:Consolas,monospace}strong{color:#fac5ef}.note{border-left:4px solid #b261aa;background:#332046;padding:14px}table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid #714d86;padding:10px;text-align:left}.view{overflow-x:auto}a{color:#f7c0ff}details{margin-top:18px;padding:14px;border:1px solid #80529a;border-radius:9px}small{color:#d5bbde}@media(max-width:560px){body{padding:14px}.view:before{display:block;content:"Swipe horizontally to inspect all columns";color:#d5bbde}}</style>
<h1>N3 · Governed warm-worker DAG pilot</h1>
<p>Two existing production processors under the one existing Method Atlas local broker.</p>
<div class="note"><strong>Actual task execution ≠ native fleet admission.</strong>
<p>All runs are local and source-bound. Only four workers maximum, with no remote dispatch, mutator-policy increase or domain-engineering approval.</p></div>
<h2>Broker measurements</h2><div class="view"><table><thead><tr><th>Mode</th><th>Workers</th><th>Backend</th><th>Median valid DAG wall (s)</th><th>Blocked invalid joins</th></tr></thead><tbody>""" + "".join(rows) + """</tbody></table></div>
<p>Registered DAG: <code>pin → profile + G9 → join</code>. Each join checks current product/member hashes, source SHA and declared dependencies. Invalid G9 census and clock inputs cannot produce a successful join.</p>
<p>Open <a href="runtime-replay.html">the existing Method Atlas playback viewer</a> to experience real recorded task states and dependency order. The viewer only replays evidence; it does not launch tasks.</p>
<details><summary>Scope and source identity</summary><p>HEAD <code>""" + html.escape(report["source"]["head"]) + """</code>. Warm bootstrap measured separately. Cross-runner queue p95, independent native job IDs, security authority and actual fleet throughput remain UNKNOWN.</p></details></html>
"""


def adapt_recorded_replay(markup, task_count):
    """Keep the canonical replay controller, adapt only N3-specific prose/CSS.

    Fail closed if the upstream renderer's exact prose/style anchors change.
    JSON event/timing semantics and browser controls are NEVER rewritten.
    """
    demand(type(task_count) is int and 1 <= task_count <= 4, "N3_REPLAY_COUNT_INVALID")
    old = "Eight registered tasks, their dependency order and their generated products."
    updated = (str(task_count) +
               " registered local broker tasks, their dependencies and verified output products.")
    old_contract = ("Receipt source identity, dependency completion before successors start, "
                    "output contracts, exact producer-to-assembly bytes, and package member hashes.")
    new_contract = ("Exact source identity, Kahn dependency completion, actual Method Atlas "
                    "and G9 execution, output-member hashes, and ALL-join verification.")
    old_style = "</style><header>"
    mobile = (
        "@media(max-width:520px){.scroll table{min-width:590px}"
        ".scroll::before{content:'Swipe horizontally for all execution columns';"
        "display:block;color:#773893;font-size:.8rem;margin:6px 0}}"
    )
    for needle in (old, old_contract, old_style):
        demand(markup.count(needle) == 1, "CANONICAL_REPLAY_TEMPLATE_ANCHOR_DRIFT")
    result = (markup.replace(old, updated)
                    .replace(old_contract, new_contract)
                    .replace(old_style, mobile + old_style))
    demand("Eight registered tasks" not in result and
           str(task_count) + " registered local broker tasks" in result,
           "N3_REPLAY_TASK_POPULATION_MISLABELED")
    return result


def run(root, head, out, *, pulses=4, modes=None, tamper=True):
    root, out = Path(root).resolve(), Path(out).resolve()
    modes = list(MODES) if modes is None else list(modes)
    demand(type(pulses) is int and 1 <= pulses <= 4 and modes and
           len(modes) == len(set(modes)) and set(modes) <= set(MODES) and
           type(tamper) is bool, "PILOT_BOUNDS_INVALID")
    demand(out != root and not out.is_relative_to(root), "OUTPUT_PATH_OVERLAPS_SOURCE")
    demand(not out.exists() or (out.is_dir() and not any(out.iterdir())),
           "OUTPUT_DIRECTORY_NOT_EMPTY")
    pin(root, head)
    before = source_hashes(root)
    inputs = input_variants(root)
    start = time.perf_counter()
    registry = {"broker": load_module("n3_real_broker", root / BROKER),
                "inputs": inputs}
    t0 = time.perf_counter()
    registry["atlas"] = load_module("n3_real_atlas", root / ATLAS)
    registry["g9"] = load_module("n3_real_g9", root / G9)
    warm_bootstrap = time.perf_counter() - t0
    collected = []
    replay = None
    with tempfile.TemporaryDirectory(prefix="method-atlas-n3-warm-") as temp:
        td = Path(temp)
        files = {}
        for variant, data in inputs.items():
            path = td / (variant + ".json")
            path.write_bytes(canonical(data))
            files[variant] = path
        for pulse in range(1, pulses + 1):
            order = modes if pulse % 4 in (1, 0) else list(reversed(modes))
            variant = "baseline" if pulse % 2 else "counterfactual"
            negative = "invalid_census" if pulse % 2 else "invalid_clock"
            hashes = {}
            for mode in order:
                valid, receipt = trial(root, head, td / f"p{pulse}-{mode}-valid",
                                       mode, variant, registry, files)
                demand(valid["accepted_fan_in"], "POSITIVE_DAG_NOT_ADMITTED")
                hashes[mode] = valid["fan_in_sha256"]
                collected.append({"pulse": pulse, **valid})
                if replay is None and mode.startswith("warm"):
                    replay = receipt
                invalid, _ = trial(root, head, td / f"p{pulse}-{mode}-negative",
                                   mode, negative, registry, files)
                demand(not invalid["accepted_fan_in"], "INVALID_DAG_FALSE_GREEN")
                collected.append({"pulse": pulse, **invalid})
            demand(len(set(hashes.values())) == 1,
                   "COLD_WARM_SOURCE_OUTCOME_JOIN_DIVERGENCE")
        if tamper:
            for mode in ("cold2", "warm2"):
                if mode not in modes:
                    continue
                corrupted, _ = trial(root, head, td / f"tamper-{mode}", mode,
                                     "baseline", registry, files, injected=True)
                demand(not corrupted["accepted_fan_in"] and
                       corrupted["error_phase"] == "output_contract",
                       "POST_PRODUCER_TAMPER_NOT_BLOCKED")
                collected.append({"pulse": None, **corrupted})
        demand(source_hashes(root) == before, "SOURCE_BYTES_CHANGED_DURING_N3")
        pin(root, head)
        report = {
            "schema": SCHEMA,
            "source": {"repository": "GBOGEB/pipeline-automation-hub",
                       "head": head, "files_sha256": before,
                       "processors": [ATLAS.as_posix(), G9.as_posix()],
                       "broker": BROKER.as_posix()},
            "input_variants_sha256": {name: digest(canonical(value))
                                       for name, value in inputs.items()},
            "plan": {"pulses": pulses, "modes": modes,
                     "positive_dag_count": pulses * len(modes),
                     "invalid_dag_count": pulses * len(modes),
                     "tamper_dag_count": sum(m in modes for m in ("cold2", "warm2")) if tamper else 0,
                     "tasks_per_dag": 4, "output_join_rule": "ALL_PRODUCERS_VERIFIED"},
            "bootstrap": {"warm_modules_import_seconds": round(warm_bootstrap, 6)},
            "rows": collected, "summary": summary(
                [r for r in collected if r["pulse"] is not None], modes),
            "safety": {"remote_dispatch": False, "source_changed": False,
                       "mutator_max_workers_changed": False, "external_watcher_added": False,
                       "native_4_pulse_scale_admission": "HOLD",
                       "merger_admission": "HOLD", "formal_engineering_credit_delta": 0,
                       "fleet_capacity_proven": False,
                       "independent_native_job_identity_verified": False},
            "evidence_class": "REAL_TWO_PROCESSOR_LOCAL_DAG_AND_CONTROLLED_NEGATIVES",
            "overall_elapsed_seconds": round(time.perf_counter()-start, 6),
        }
        demand(replay is not None, "NO_WARM_REPLAY_TO_REVIEW")
        viewer = load_module("n3_existing_replay_renderer", root / HERE.relative_to(root) /
                             "runtime_evidence.py")
        reply = dict(replay)
        count = len(reply["tasks"])
        reply["source_sha"] = head
        reply["counts"] = {
            "registered_tasks": count, "successful_tasks": count,
            "registered_dependency_edges": 4, "observed_verified_dependency_edges": 4}
        reply["interpretation"] = ("Observed local broker DAG with two actual processors;"
                                    " replay is evidence, not live scheduling.")
        markup = adapt_recorded_replay(viewer.render(reply), count)
    out.mkdir(parents=True, exist_ok=True)
    (out / "n3_receipt.json").write_bytes(canonical(report))
    (out / "index.html").write_text(render(report), encoding="utf-8", newline="\n")
    (out / "runtime-replay.html").write_text(markup, encoding="utf-8", newline="\n")
    (out / "n3_dag.mmd").write_text("""flowchart TD
  P["Exact source & policy pin"] --> A["Method Atlas source-contract processor"]
  P --> G["GOGREEN G9 real outcome producer"]
  A --> J["ALL: verified source/member join"]
  G --> J
  G -. invalid census/clock/tamper .-> X["Output rejected, join BLOCKED"]
  J --> R["Actual broker receipt + offline replay"]
  R --> O["Independent owner HOLD; no remote dispatch"]
""", encoding="utf-8", newline="\n")
    names = ("n3_receipt.json", "index.html", "runtime-replay.html", "n3_dag.mmd")
    manifest = {"schema": "method-atlas.n3.warm-broker-manifest.v1",
                "source_sha": head,
                "files_sha256": {name: digest((out / name).read_bytes()) for name in names},
                "native_scaling_admitted": False, "merge_authorized": False}
    (out / "manifest.json").write_bytes(canonical(manifest))
    print(json.dumps({
        "status": "PASS_TWO_REAL_PROCESSORS_BROKER_BOUND",
        "source_head": head,
        "broker_dags": report["plan"]["positive_dag_count"] +
                       report["plan"]["invalid_dag_count"] +
                       report["plan"]["tamper_dag_count"],
        "negative_or_tamper_dags": report["plan"]["invalid_dag_count"] +
                                  report["plan"]["tamper_dag_count"],
        "speedup": report["summary"]["cold_to_warm_speedup_by_worker_count"],
        "native_scale_admitted": False,
    }, sort_keys=True))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pulses", type=int, default=4)
    args = ap.parse_args(argv)
    run(args.root, args.head, args.out, pulses=args.pulses)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
