#!/usr/bin/env python3
"""JADE rolling-5 window: NIRVANA rotation, streaks, golden thread, SOURCE_RED.

Read-only projection over an append-only pulse ledger. Each pulse pins one
focus snapshot (data/FOCUS5_*.json shape) by sha256. The engine never mutates
GitHub, never grants release credit and never treats UNKNOWN as PASS.

  python tools/rolling5.py --write          regenerate site/rolling5.{json,csv}
  python tools/rolling5.py --check          fail if committed outputs drift
  python tools/rolling5.py --append-pulse data/FOCUS5_X.json --pulse-id P0002
"""
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
POLICY = "data/ROLLING5_POLICY.json"
LEDGER = "data/ROLLING5_PULSES.json"
OUT_JSON = "site/rolling5.json"
OUT_CSV = "site/rolling5.csv"
SCHEMA = "jade.temple.rolling5.projection/1.0"
PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"
SHA40 = re.compile(r"[0-9a-f]{40}")
REQUIRED_GATES = frozenset(f"H{i:02d}" for i in range(1, 13))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(root: Path, rel: str):
    return json.loads((root / rel).read_text(encoding="utf-8"))


# --- Ledger ---------------------------------------------------------------

def verified_pulses(root: Path, ledger: dict) -> list[tuple[dict, dict]]:
    """Return (pulse, snapshot) pairs; fail closed on any drift or reorder."""
    pulses = ledger.get("pulses")
    if not isinstance(pulses, list) or not pulses:
        raise ValueError("pulse ledger is empty")
    seen_ids, seen_hashes, out = set(), set(), []
    for pulse in pulses:
        pid, digest = pulse.get("id"), pulse.get("snapshot_sha256")
        if pid in seen_ids or digest in seen_hashes:
            raise ValueError(f"duplicate pulse id or snapshot: {pid}")
        if out and pulse["observed_date"] < out[-1][0]["observed_date"]:
            raise ValueError(f"pulse {pid} is older than its predecessor")
        raw = (root / pulse["snapshot"]).read_bytes()
        if sha256(raw) != digest:
            raise ValueError(f"snapshot drift for pulse {pid}: {pulse['snapshot']}")
        seen_ids.add(pid)
        seen_hashes.add(digest)
        out.append((pulse, json.loads(raw)))
    return out


def append_pulse(root: Path, snapshot_rel: str, pulse_id: str) -> dict:
    """Temporal hook: pin a new snapshot as the next pulse (append-only)."""
    ledger = load(root, LEDGER)
    verified_pulses(root, ledger)  # never extend a ledger that already drifted
    raw = (root / snapshot_rel).read_bytes()
    snapshot = json.loads(raw)
    rows_of(snapshot)  # validate shape before pinning
    pulse = {
        "id": pulse_id,
        "observed_date": snapshot["source"]["observed_date"],
        "snapshot": snapshot_rel,
        "snapshot_sha256": sha256(raw),
        "origin": "APPENDED",
    }
    ledger["pulses"].append(pulse)
    verified_pulses(root, ledger)
    (root / LEDGER).write_text(json.dumps(ledger, indent=2) + "\n",
                               encoding="utf-8", newline="\n")
    return pulse


def rows_of(snapshot: dict) -> dict[str, dict]:
    rows = {}
    for row in snapshot["rows"]:
        gate_ids = [g["id"] for g in row["gates"]]
        if len(gate_ids) != len(REQUIRED_GATES) or set(gate_ids) != REQUIRED_GATES:
            raise ValueError(f"invalid H01-H12 gate inventory in {row['repo']}")
        gates = {g["id"]: g["status"] for g in row["gates"]}
        if any(s not in (PASS, FAIL, UNKNOWN) for s in gates.values()):
            raise ValueError(f"unknown gate status in {row['repo']}")
        if row["repo"] in rows:
            raise ValueError(f"duplicate repository in pulse: {row['repo']}")
        rows[row["repo"]] = {
            "rank": row["rank"],
            "source_sha": row.get("source_sha"),
            "gates": gates,
            "candidate_branch": row.get("candidate_branch"),
            "candidate_sha": row.get("candidate_sha"),
            "blockers": list(row.get("blockers", [])),
        }
    return rows


# --- Streaks --------------------------------------------------------------

def streak_stats(history: list[str | None], unattended_after: int) -> dict:
    """Streaks over observed pulses; None means the repo was not observed."""
    runs, run = [], 0
    for status in history:
        if status == PASS:
            run += 1
        elif run:
            runs.append(run)
            run = 0
    current = run
    completed = runs  # PASS runs that already ended
    tail_unknown = 0
    for status in reversed(history):
        if status != UNKNOWN:
            break
        tail_unknown += 1
    regressions = sum(
        1 for a, b in zip(history, history[1:]) if a == PASS and b != PASS
    )
    return {
        "pulses_observed": sum(s is not None for s in history),
        "latest": history[-1] if history else None,
        "streak_on_current": current,
        "streak_record": max(completed + [current]),
        "previous_streak": completed[-1] if completed else None,
        "nevergreen": PASS not in history,
        "regressions": regressions,
        "unattended": (tail_unknown >= unattended_after
                       if len(history) >= unattended_after else None),
    }


# --- NIRVANA and rotation -------------------------------------------------

def nirvana(repo: str, timeline: list[dict], sustain: int) -> bool:
    """All gates PASS on one exact source SHA for `sustain` latest pulses."""
    if len(timeline) < sustain:
        return False
    recent = [rows.get(repo) for rows in timeline[-sustain:]]
    if any(r is None for r in recent):
        return False
    shas = {r["source_sha"] for r in recent}
    return (
        len(shas) == 1
        and bool(SHA40.fullmatch(next(iter(shas)) or ""))
        and all(set(r["gates"]) == REQUIRED_GATES
                and all(state == PASS for state in r["gates"].values())
                for r in recent)
    )


def rotate(window: list[str], roster: list[dict], graduated: set[str],
           size: int) -> dict:
    keep = [r for r in window if r not in graduated]
    queue = [x["repo"] for x in sorted(roster, key=lambda x: x["rank"])
             if x["repo"] not in keep and x["repo"] not in graduated]
    admitted = queue[: max(0, size - len(keep))]
    nxt = keep + admitted
    return {
        "current": window,
        "graduated": sorted(r for r in window if r in graduated),
        "admitted": admitted,
        "next": nxt,
        "empty_slots": size - len(nxt),
    }


def race(latest: dict[str, dict]) -> list[dict]:
    """First-to-NIRVANA ordering of current candidates (evidence only)."""
    out = []
    for repo, row in latest.items():
        values = list(row["gates"].values())
        out.append({
            "repo": repo,
            "pass": values.count(PASS),
            "fail": values.count(FAIL),
            "unknown": values.count(UNKNOWN),
            "remaining": len(values) - values.count(PASS),
            "rank": row["rank"],
        })
    out.sort(key=lambda x: (x["remaining"], x["fail"], x["rank"]))
    for i, item in enumerate(out, 1):
        item["position"] = i
    return out


# --- Golden thread --------------------------------------------------------

def golden_thread(row: dict, mapping: dict[str, list[str]]) -> dict:
    steps = []
    for step, evidence in mapping.items():
        if not evidence:
            status = UNKNOWN
        else:
            states = []
            for item in evidence:
                if item == "@candidate_branch":
                    ok = bool(row.get("candidate_branch")) and bool(
                        SHA40.fullmatch(row.get("candidate_sha") or ""))
                    states.append(PASS if ok else UNKNOWN)
                else:
                    states.append(row["gates"].get(item, UNKNOWN))
            status = (FAIL if FAIL in states
                      else PASS if set(states) == {PASS} else UNKNOWN)
        steps.append({"step": step, "status": status})
    position = 0
    for s in steps:
        if s["status"] != PASS:
            break
        position += 1
    first_break = steps[position]["step"] if position < len(steps) else None
    return {"position": position, "of": len(steps),
            "first_break": first_break, "steps": steps}


# --- SOURCE_RED -----------------------------------------------------------

def dependents(prereqs: dict[str, list[str]]) -> dict[str, set[str]]:
    reverse: dict[str, set[str]] = {g: set() for g in prereqs}
    for gate, needs in prereqs.items():
        for need in needs:
            reverse[need].add(gate)
    closure = {}
    for gate in prereqs:
        seen, stack = set(), list(reverse[gate])
        while stack:
            g = stack.pop()
            if g not in seen:
                seen.add(g)
                stack.extend(reverse[g])
        closure[gate] = seen
    return closure


def source_red(latest: dict[str, dict], edges: list[dict], policy: dict) -> dict:
    cfg = policy["source_red"]
    closure = dependents(policy["gate_prerequisites"])
    weights = cfg["edge_weights"]
    instances = []
    for repo, row in sorted(latest.items()):
        edge_score = sum(weights.get(e["state"], 0)
                         for e in edges if e["from"] == repo)
        for gate, status in sorted(row["gates"].items()):
            if status != FAIL:
                continue
            blocked = sorted(g for g in closure.get(gate, ())
                             if row["gates"].get(g) != PASS)
            instances.append({
                "repo": repo, "gate": gate, "blocks": blocked,
                "edge_score": edge_score,
                "unlock_score": len(blocked) + edge_score,
            })
    by_gate: dict[str, dict] = {}
    for inst in instances:
        agg = by_gate.setdefault(inst["gate"], {
            "gate": inst["gate"], "repos": [], "unlock_score": 0})
        agg["repos"].append(inst["repo"])
        agg["unlock_score"] += inst["unlock_score"]
    ranked = sorted(by_gate.values(),
                    key=lambda a: (-len(a["repos"]), -a["unlock_score"], a["gate"]))
    for agg in ranked:
        agg["repo_count"] = len(agg["repos"])
        agg["class"] = ("COMMON_CAUSE"
                        if agg["repo_count"] >= cfg["common_cause_min_repos"]
                        else "LOCAL")
    instances.sort(key=lambda i: (-i["unlock_score"], i["repo"], i["gate"]))
    # Not red, but never attended: UNKNOWN across many repos blocks just as hard.
    unknown: dict[str, list[str]] = {}
    for repo, row in sorted(latest.items()):
        for gate, status in row["gates"].items():
            if status == UNKNOWN:
                unknown.setdefault(gate, []).append(repo)
    common_unknown = sorted(
        ({"gate": g, "repos": r, "repo_count": len(r),
          "blocks": sorted(closure.get(g, ()))}
         for g, r in unknown.items()
         if len(r) >= cfg["common_cause_min_repos"]),
        key=lambda u: (-u["repo_count"], -len(u["blocks"]), u["gate"]))
    return {"ranked_gates": ranked, "instances": instances,
            "core_focus": ranked[0]["gate"] if ranked else None,
            "common_unknown": common_unknown}


# --- Projection -----------------------------------------------------------

def project(root: Path = ROOT) -> dict:
    """The model with private repos projected to counts only (tools/private_boundary.py)."""
    return PB.project(_project(root))


def _project(root: Path = ROOT) -> dict:
    policy = load(root, POLICY)
    ledger = load(root, LEDGER)
    roster = load(root, policy["roster_source"])["repositories"]
    pairs = verified_pulses(root, ledger)
    timeline = [rows_of(snap) for _, snap in pairs]
    latest_pulse, latest_snap = pairs[-1]
    latest = timeline[-1]
    sustain = policy["nirvana"]["sustain_pulses"]
    unattended_after = policy["streaks"]["unattended_after_pulses"]

    nirvana_ledger, achieved = [], set()
    for i, (pulse, _) in enumerate(pairs):
        for repo in sorted(timeline[i]):
            if repo not in achieved and nirvana(repo, timeline[: i + 1], sustain):
                achieved.add(repo)
                nirvana_ledger.append({"repo": repo, "pulse": pulse["id"],
                                       "order": len(nirvana_ledger) + 1})

    repos = []
    for repo, row in sorted(latest.items(), key=lambda kv: kv[1]["rank"]):
        gate_ids = sorted(row["gates"])
        streaks = {
            g: streak_stats([t.get(repo, {}).get("gates", {}).get(g)
                             if repo in t else None for t in timeline],
                            unattended_after)
            for g in gate_ids
        }
        repos.append({
            "repo": repo,
            "rank": row["rank"],
            "source_sha": row["source_sha"],
            "nirvana": repo in achieved,
            "verified_pass": sum(s == PASS for s in row["gates"].values()),
            "gate_denominator": len(gate_ids),
            "golden_thread": golden_thread(row, policy["golden_thread"]),
            "nevergreen_gates": [g for g in gate_ids if streaks[g]["nevergreen"]],
            "unattended_gates": [g for g in gate_ids if streaks[g]["unattended"]],
            "best_current_streak": max(
                (s["streak_on_current"] for s in streaks.values()), default=0),
            "regressions": sum(s["regressions"] for s in streaks.values()),
            "streaks": streaks,
            "blockers": row["blockers"],
        })

    window = [r["repo"] for r in repos]
    passed = sum(r["verified_pass"] for r in repos)
    denom = sum(r["gate_denominator"] for r in repos)
    return {
        "schema": SCHEMA,
        "authority": policy["authority"],
        "authority_transfer": False,
        "merge_admission": "HOLD",
        "release_credit": False,
        "inputs": {
            POLICY: sha256((root / POLICY).read_bytes()),
            LEDGER: sha256((root / LEDGER).read_bytes()),
            policy["roster_source"]: sha256(
                (root / policy["roster_source"]).read_bytes()),
        },
        "pulses": [{"id": p["id"], "observed_date": p["observed_date"],
                    "snapshot_sha256": p["snapshot_sha256"]} for p, _ in pairs],
        "history_depth": len(pairs),
        "history_note": (
            "Streaks need history: with fewer pulses than "
            f"{unattended_after}, 'unattended' is null and a nevergreen flag "
            "only means never PASS within the observed pulses."),
        "latest_pulse": latest_pulse["id"],
        "window_size": policy["window_size"],
        "window": rotate(window, roster, achieved, policy["window_size"]),
        "nirvana_ledger": nirvana_ledger,
        "race": race(latest),
        "metrics": {
            "verified_pass": passed,
            "gate_denominator": denom,
            "verified_completion_pct": round(100 * passed / denom, 2) if denom else None,
            "nirvana_count": len(achieved),
            "nevergreen_gate_instances": sum(len(r["nevergreen_gates"]) for r in repos),
            "fail_gate_instances": sum(
                list(r["gates"].values()).count(FAIL) for r in latest.values()),
        },
        "source_red": source_red(latest, latest_snap.get("edges", []), policy),
        "repos": repos,
    }


def render(model: dict) -> dict[str, bytes]:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["race_position", "repo", "rank", "verified_pass",
                "gate_denominator", "nirvana", "golden_thread_position",
                "golden_thread_first_break", "nevergreen_gates",
                "source_red_gates"])
    position = {r["repo"]: r["position"] for r in model["race"]}
    reds = {}
    for inst in model["source_red"]["instances"]:
        reds.setdefault(inst["repo"], []).append(inst["gate"])
    for r in sorted(model["repos"], key=lambda r: position[r["repo"]]):
        w.writerow([position[r["repo"]], r["repo"], r["rank"], r["verified_pass"],
                    r["gate_denominator"], r["nirvana"],
                    r["golden_thread"]["position"],
                    r["golden_thread"]["first_break"] or "",
                    "|".join(r["nevergreen_gates"]),
                    "|".join(sorted(reds.get(r["repo"], [])))])
    return {
        OUT_JSON: (json.dumps(model, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        OUT_CSV: buf.getvalue().encode("utf-8"),
    }


def main(argv=None, root: Path = ROOT) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--append-pulse", metavar="SNAPSHOT")
    ap.add_argument("--pulse-id")
    args = ap.parse_args(argv)
    if args.append_pulse:
        if not args.pulse_id:
            ap.error("--append-pulse requires --pulse-id")
        print(json.dumps(append_pulse(root, args.append_pulse, args.pulse_id)))
        return 0
    files = render(project(root))
    if args.check:
        drift = [rel for rel, data in files.items()
                 if not (root / rel).exists() or (root / rel).read_bytes() != data]
        if drift:
            print("ROLLING5_FIRST_RED: regenerate " + ", ".join(drift))
            return 1
        print("ROLLING5_PARITY_OK")
        return 0
    for rel, data in files.items():
        (root / rel).write_bytes(data)
    print("ROLLING5_WROTE " + " ".join(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
