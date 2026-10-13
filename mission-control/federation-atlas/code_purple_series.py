#!/usr/bin/env python3
"""CODE PURPLE BD queue + iteration-ordinal metric series.

Metrics are computed from repository files only (no wall clock, no network), so the
same tree always yields the same numbers. The series is indexed by an ordinal key
W(ave).C(ycle).I(teration).S(ub). Each entry stores the metrics at the moment a level
closed, the delta to the previous entry, and the SHA-256 of the previous entry.

Commands
  check   recompute metrics for this tree and compare with the latest entry (CI)
  append  add an entry for this tree (or --root <worktree>) at --key
  show    print computed metrics

Exit codes (REX): 0 PASS, 1 FAIL, 2 INCOMPLETE.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
QUEUE = HERE / "CODE_PURPLE_BD_QUEUE_v1.json"
SERIES = HERE / "CODE_PURPLE_ITERATION_SERIES_v1.json"
BEAMS = HERE / "CODE_PURPLE_BEAMS_DAG_v1.json"
PULSES = HERE / "TOP7_CENSUS_PULSES_v1.json"
SCHEMAS = HERE / "schemas"
CONTRACT = "mission-control/grand-missions/GM_DMAIC_EVOLUTION_T7_T14_T21_v1.json"
COVERAGE = "mission-control/grand-missions/GM_DMAIC_COVERAGE_TELEMETRY_v1.json"
TOPOLOGY = "mission-control/grand-missions/GM-I-A_FAST_HEAVY_FEDERATION_TOPOLOGY_v0.1.json"
GRAPH = "mission-control/federation-atlas/ATLAS_GRAPH_v1.yaml"
KEY_RX = re.compile(r"^W(\d+)\.C(\d+)\.I(\d+)\.S(\d+)$")
LEVELS = ["E0_OBSERVED", "E1_REPEATABLE", "E2_RECURSIVE", "E3_PARALLEL_TOP7", "E4_PARALLEL_TOP14", "E5_PARALLEL_TOP21"]
COMPLETE = {"DONE", "CONTROL", "SUPERSEDED", "INVALIDATED"}


class SeriesError(Exception):
    pass


def key_tuple(key: str) -> tuple[int, int, int, int]:
    m = KEY_RX.match(key)
    if not m:
        raise SeriesError(f"bad series key {key!r}; expected W<n>.C<n>.I<n>.S<n>")
    return tuple(int(g) for g in m.groups())  # type: ignore[return-value]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- schema subset
def validate(doc, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    """Validate the JSON Schema 2020-12 subset used by schemas/*.json."""
    root = root or schema
    errs: list[str] = []
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        return validate(doc, root["$defs"][ref], root, path)
    if "const" in schema and doc != schema["const"]:
        errs.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and doc not in schema["enum"]:
        errs.append(f"{path}: {doc!r} not in {schema['enum']}")
    t = schema.get("type")
    types = t if isinstance(t, list) else [t] if t else []
    pymap = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}
    if types and not any(
        (tp == "integer" and type(doc) is int) or (tp == "number" and type(doc) in (int, float))
        or (tp in pymap and type(doc) is pymap[tp]) for tp in types
    ):
        errs.append(f"{path}: expected type {types}")
        return errs
    if isinstance(doc, str):
        if "pattern" in schema and not re.search(schema["pattern"], doc):
            errs.append(f"{path}: {doc!r} does not match {schema['pattern']}")
        if len(doc) < schema.get("minLength", 0):
            errs.append(f"{path}: shorter than {schema['minLength']}")
    if isinstance(doc, dict):
        for req in schema.get("required", []):
            if req not in doc:
                errs.append(f"{path}: missing {req}")
        props = schema.get("properties", {})
        for k, v in doc.items():
            if k in props:
                errs.extend(validate(v, props[k], root, f"{path}.{k}"))
            elif schema.get("additionalProperties") is False:
                errs.append(f"{path}: unexpected {k}")
    if isinstance(doc, list):
        if len(doc) < schema.get("minItems", 0):
            errs.append(f"{path}: fewer than {schema['minItems']} items")
        if "items" in schema:
            for i, v in enumerate(doc):
                errs.extend(validate(v, schema["items"], root, f"{path}[{i}]"))
    return errs


# ---------------------------------------------------------------- queue semantics
def check_queue(queue: dict) -> list[str]:
    errs = validate(queue, load_json(SCHEMAS / "code_purple_bd_queue.schema.json"))
    if errs:
        return errs
    ids = [i["id"] for i in queue.get("items", [])]
    if len(ids) != len(set(ids)):
        errs.append("duplicate queue ids")
    beams = {b["id"] for b in load_json(BEAMS)["beams"]}
    for item in queue.get("items", []):
        if item["beam"] not in beams:
            errs.append(f"{item['id']}: unknown beam {item['beam']}")
        for dep in item["depends_on"]:
            if dep not in ids:
                errs.append(f"{item['id']}: unknown dependency {dep}")
        keys = [key_tuple(h["at"]) for h in item["history"]]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            errs.append(f"{item['id']}: history keys must be strictly increasing")
    return errs


def item_at(item: dict, key: str) -> dict | None:
    """State row of an item as of series key (None if not yet filed)."""
    k = key_tuple(key)
    rows = [h for h in item["history"] if key_tuple(h["at"]) <= k]
    return rows[-1] if rows else None


def queue_metrics(queue: dict, key: str) -> dict:
    open_states = set(queue["open_states"])
    rows = [(i, item_at(i, key)) for i in queue["items"]]
    rows = [(i, r) for i, r in rows if r is not None]
    by_state = {s: 0 for s in queue["lifecycle"]}
    by_flow = {f: 0 for f in queue["flows"]}
    for _, r in rows:
        by_state[r["state"]] += 1
        by_flow[r["flow"]] += 1
    return {
        "bd_total": len(rows),
        "bd_open": sum(r["state"] in open_states for _, r in rows),
        "bd_complete": sum(r["state"] in COMPLETE for _, r in rows),
        "bd_critical_open": sum(i["critical_path"] and r["state"] in open_states for i, r in rows),
        "bd_ready": by_flow["READY"],
        "bd_in_pr": by_flow["IN_PR"],
        "bd_blocked_or_held": by_flow["BLOCKED"] + by_flow["HOLD"] + by_flow["RETURN_OWNER"],
        **{f"bd_state_{s.lower()}": n for s, n in by_state.items()},
    }


# ---------------------------------------------------------------- gate ledger
def gate_ledger(contract: dict) -> dict:
    """Every promotion predicate as PASS / FAIL / UNKNOWN (null observation)."""
    cur, g1, g2 = contract["current"], contract["promotion_gates"]["top7_to_top14"], contract["promotion_gates"]["top14_to_top21"]
    evo = contract["iteration_evolution"]
    rep = cur.get("max_unchanged_root_auto_repeat_after_control")
    hand = evo.get("recursive_control_handoff_count")
    pd = cur.get("top14_proof_debt_observed")

    def p(label, obs, gate, ok):
        return {"label": label, "observed": obs, "gate": gate,
                "state": "UNKNOWN" if obs is None else ("PASS" if ok() else "FAIL")}

    top14 = [
        p("TOP7 classified", cur.get("top7_classified_observed"), f">= {g1['classified_min']}", lambda: cur["top7_classified_observed"] >= g1["classified_min"]),
        p("TOP7 green CONTROL", cur.get("top7_green_control_observed"), f">= {g1['green_control_min']}", lambda: cur["top7_green_control_observed"] >= g1["green_control_min"]),
        p("TOP7 unclassified", cur.get("top7_unclassified_observed"), f"<= {g1['unclassified_max']}", lambda: cur["top7_unclassified_observed"] <= g1["unclassified_max"]),
        p("Full DMAIC iterations", cur.get("mission_era_full_dmaic_iterations"), f">= {g1['full_dmaic_iterations_min']}", lambda: cur["mission_era_full_dmaic_iterations"] >= g1["full_dmaic_iterations_min"]),
        p("ABACUS D1 state", cur.get("abacus", {}).get("d1", {}).get("state"), g1["abacus_d1_requires"], lambda: cur["abacus"]["d1"]["state"] == g1["abacus_d1_requires"]),
        p("Proof debt non-increasing, 2 pulses", cur.get("top7_proof_debt_two_pulse_nonincreasing"), "true", lambda: cur["top7_proof_debt_two_pulse_nonincreasing"] is True),
        p("Unchanged-root auto-repeat", rep, f"<= {g1['unchanged_root_auto_repeat_max']}", lambda: rep <= g1["unchanged_root_auto_repeat_max"]),
        p("Iteration chain integrity", evo.get("iteration_chain_integrity"), "true", lambda: evo["iteration_chain_integrity"] is True),
        p("Recursive CONTROL handoffs", hand, f">= {g1['recursive_control_handoff_min']}", lambda: hand >= g1["recursive_control_handoff_min"]),
    ]
    top21 = [
        p("TOP14 classified", cur.get("top14_classified_observed"), f">= {g2['classified_min']}", lambda: cur["top14_classified_observed"] >= g2["classified_min"]),
        p("TOP14 green CONTROL", cur.get("top14_green_control_observed"), f">= {g2['green_control_min']}", lambda: cur["top14_green_control_observed"] >= g2["green_control_min"]),
        p("TOP14 unclassified", cur.get("top14_unclassified_observed"), f"<= {g2['unclassified_max']}", lambda: cur["top14_unclassified_observed"] <= g2["unclassified_max"]),
        p("TOP14 proof debt", pd, f"<= {g2['proof_debt_max']}", lambda: pd <= g2["proof_debt_max"]),
        p("Distinct repos with full DMAIC", cur.get("mission_era_distinct_repos_full_dmaic"), f">= {g2['full_dmaic_iterations_distinct_repos_min']}", lambda: cur["mission_era_distinct_repos_full_dmaic"] >= g2["full_dmaic_iterations_distinct_repos_min"]),
        p("Recurrent CONTROL, distinct source", cur.get("recurrent_controls_with_distinct_source_repeat"), f">= {g2['recurrent_control_distinct_source_repeat_min']}", lambda: cur["recurrent_controls_with_distinct_source_repeat"] >= g2["recurrent_control_distinct_source_repeat_min"]),
        p("Net semantic delta <= 0, 2 pulses", cur.get("top14_two_pulse_net_semantic_delta_le_zero"), "true", lambda: cur["top14_two_pulse_net_semantic_delta_le_zero"] is True),
        p("Proof yield non-degrading, 2 pulses", cur.get("top14_two_pulse_proof_yield_nondegrading"), "true", lambda: cur["top14_two_pulse_proof_yield_nondegrading"] is True),
        p("Unchanged-root auto-repeat", rep, f"<= {g2['unchanged_root_auto_repeat_max']}", lambda: rep <= g2["unchanged_root_auto_repeat_max"]),
        p("Iteration chain integrity", evo.get("iteration_chain_integrity"), "true", lambda: evo["iteration_chain_integrity"] is True),
        p("Recursive CONTROL handoffs", hand, f">= {g2['recursive_control_handoff_min']}", lambda: hand >= g2["recursive_control_handoff_min"]),
    ]
    return {"top7_to_top14": top14, "top14_to_top21": top21}


def _count(rows, state):
    return sum(r["state"] == state for r in rows)


# ---------------------------------------------------------------- tree metrics
def _zero_test_gates(root: Path) -> int | None:
    audit = ROOT / "scripts" / "zero_test_gate_audit.py"
    if not (root / ".github" / "workflows").is_dir():
        return None
    spec = importlib.util.spec_from_file_location("ztga_for_series", audit)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.audit(root)["summary"]["zero_test_gates"]


def _graph_bindings(root: Path) -> tuple[int | None, int | None]:
    p = root / GRAPH
    if not p.exists():
        return None, None
    import yaml  # pinned in CI: pyyaml==6.0.3
    edges = yaml.safe_load(p.read_text(encoding="utf-8"))["edges"]
    if any("binding" not in e for e in edges):
        return None, None
    return sum(e["binding"] == "RECEIPT" for e in edges), sum(e["binding"] == "DECLARED" for e in edges)


def compute_metrics(root: Path, queue: dict, key: str) -> dict:
    contract = load_json(root / CONTRACT)
    ledger = gate_ledger(contract)
    cur, evo = contract["current"], contract["iteration_evolution"]
    cov = load_json(root / COVERAGE) if (root / COVERAGE).exists() else None
    topo = load_json(root / TOPOLOGY)
    receipt_edges = sum(1 for e in topo["edges"] if e.get("state") == "PASS" and e.get("receipt_sha256"))
    g_receipt, g_declared = _graph_bindings(root)
    m = {
        "top14_gate_pass": _count(ledger["top7_to_top14"], "PASS"),
        "top14_gate_fail": _count(ledger["top7_to_top14"], "FAIL"),
        "top14_gate_unknown": _count(ledger["top7_to_top14"], "UNKNOWN"),
        "top21_gate_pass": _count(ledger["top14_to_top21"], "PASS"),
        "top21_gate_fail": _count(ledger["top14_to_top21"], "FAIL"),
        "top21_gate_unknown": _count(ledger["top14_to_top21"], "UNKNOWN"),
        "top7_green_control": cur.get("top7_green_control_observed"),
        "top14_green_control": cur.get("top14_green_control_observed"),
        "dmaic_complete_iterations": evo.get("complete_iteration_count"),
        "dmaic_evolution_level": LEVELS.index(evo["current_level"]) if evo.get("current_level") in LEVELS else None,
        "coverage_rows_measured": None if cov is None else sum(r["state"].startswith("MEASURED") for r in cov["rows"]),
        "coverage_rows_total": None if cov is None else len(cov["rows"]),
        "receipt_edges": receipt_edges,
        "graph_edges_receipt": g_receipt,
        "graph_edges_declared": g_declared,
        "zero_test_gates": _zero_test_gates(root),
    }
    m.update(queue_metrics(queue, key))
    return m


def delta(prev: dict | None, cur: dict) -> dict:
    if prev is None:
        return {}
    out = {}
    for k, v in cur.items():
        a = prev.get(k)
        if isinstance(v, int) and isinstance(a, int) and not isinstance(v, bool) and v != a:
            out[k] = v - a
        elif (a is None) != (v is None):
            out[k] = "BOUND" if a is None else "UNBOUND"
    return out


def digest(entry: dict) -> str:
    return hashlib.sha256(json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def check_series(series: dict) -> list[str]:
    errs = validate(series, load_json(SCHEMAS / "code_purple_iteration_series.schema.json"))
    if errs:
        return errs
    entries = series["entries"]
    keys = [key_tuple(e["key"]) for e in entries]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        errs.append("series keys must be strictly increasing")
    prev = None
    for e in entries:
        want = None if prev is None else digest(prev)
        if e["prev_digest"] != want:
            errs.append(f"{e['key']}: prev_digest broken (append-only chain)")
        if e["delta"] != delta(prev["metrics"] if prev else None, e["metrics"]):
            errs.append(f"{e['key']}: stored delta does not match metrics")
        prev = e
    for e in entries[:-1]:
        if e["tree"] == "PR_HEAD":
            errs.append(f"{e['key']}: only the latest entry may be PROVISIONAL_PR_HEAD")
    return errs


def run_check(root: Path = ROOT) -> tuple[int, list[str]]:
    queue, series = load_json(QUEUE), load_json(SERIES)
    errs = check_queue(queue) + check_series(series)
    if errs:
        return 1, errs
    latest = series["entries"][-1]
    for item in queue["items"]:
        if key_tuple(item["history"][-1]["at"]) > key_tuple(latest["key"]):
            errs.append(f"{item['id']}: history row beyond latest series key {latest['key']}")
    computed = compute_metrics(root, queue, latest["key"])
    if any(v is None for k, v in computed.items() if k in ("zero_test_gates", "graph_edges_receipt")):
        return 2, ["INCOMPLETE: audit or graph bindings not computable on this tree"]
    diff = {k: (latest["metrics"].get(k), v) for k, v in computed.items() if latest["metrics"].get(k) != v}
    if diff:
        errs.append(
            "metrics changed without a series entry: "
            + ", ".join(f"{k} {a}->{b}" for k, (a, b) in sorted(diff.items()))
            + ". Append one: python mission-control/federation-atlas/code_purple_series.py append "
              "--key W<w>.C<c>.I<i>.S<s+1> --closes SUB --label '<what closed>'"
        )
    return (1 if errs else 0), errs


def append(root: Path, key: str, closes: str, label: str, tree: str, refs: list[str]) -> dict:
    queue = load_json(QUEUE)
    series = load_json(SERIES) if SERIES.exists() else {
        "schema": "missioncontrol.code_purple.iteration_series.v1", "index": "WAVE.CYCLE.ITERATION.SUB",
        "authority_transfer": False,
        "rule": "Append-only. One entry per closed wave, cycle, iteration or sub-iteration. Metrics are recomputed from repository files; CI fails if the latest entry differs from the tree.",
        "entries": []}
    entries = series["entries"]
    if entries and key_tuple(key) <= key_tuple(entries[-1]["key"]):
        if entries[-1]["tree"] == "PR_HEAD" and entries[-1]["key"] == key:
            entries.pop()  # refresh the provisional entry of this PR
        else:
            raise SeriesError(f"key {key} must be after {entries[-1]['key']}")
    metrics = compute_metrics(root, queue, key)
    prev = entries[-1] if entries else None
    entry = {"key": key, "closes": closes, "label": label, "tree": tree,
             "evidence_class": "PROVISIONAL_PR_HEAD" if tree == "PR_HEAD" else "MEASURED",
             "refs": refs, "metrics": metrics, "delta": delta(prev["metrics"] if prev else None, metrics),
             "prev_digest": digest(prev) if prev else None}
    entries.append(entry)
    SERIES.write_text(json.dumps(series, indent=2) + "\n", encoding="utf-8")
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sh = sub.add_parser("show")
    sh.add_argument("--key", required=True)
    sh.add_argument("--root", default=str(ROOT))
    a = sub.add_parser("append")
    a.add_argument("--key", required=True)
    a.add_argument("--closes", required=True, choices=["OPEN", "SUB", "ITERATION", "CYCLE", "WAVE"])
    a.add_argument("--label", required=True)
    a.add_argument("--root", default=str(ROOT))
    a.add_argument("--tree", default="PR_HEAD", help="40-hex SHA the root was checked out at, or PR_HEAD")
    a.add_argument("--ref", action="append", default=[])
    args = ap.parse_args(argv)
    try:
        if args.cmd == "check":
            code, errs = run_check()
            for e in errs:
                print(("INCOMPLETE: " if code == 2 else "FAIL: ") + e)
            if code == 0:
                print(f"CODE_PURPLE_SERIES PASS latest={load_json(SERIES)['entries'][-1]['key']}")
            return code
        if args.cmd == "show":
            print(json.dumps(compute_metrics(Path(args.root), load_json(QUEUE), args.key), indent=2))
            return 0
        entry = append(Path(args.root), args.key, args.closes, args.label, args.tree, args.ref)
        print(json.dumps({"key": entry["key"], "delta": entry["delta"]}, indent=2))
        return 0
    except SeriesError as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
