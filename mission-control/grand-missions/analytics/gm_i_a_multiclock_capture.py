#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime
from pathlib import Path

def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def seconds(a: str, b: str) -> int:
    return int((ts(b) - ts(a)).total_seconds())

def fetch(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "GBOGEB-MissionControl-MultiClock"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)

def job(repo: str, run_id: int, name: str) -> dict:
    data = fetch(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")
    hits = [j for j in data["jobs"] if j["name"] == name]
    if len(hits) != 1:
        raise SystemExit(f"FAIL expected one job {name} in {repo} run {run_id}, got {len(hits)}")
    j = hits[0]
    if j.get("status") != "completed" or j.get("conclusion") != "success":
        raise SystemExit(f"FAIL job not successful: {repo} {run_id} {name}")
    return j

def step_seconds(j: dict, name: str) -> int:
    hits = [s for s in j.get("steps", []) if s["name"] == name]
    if len(hits) != 1 or hits[0].get("conclusion") != "success":
        raise SystemExit(f"FAIL step not successful/unique: {name}")
    s = hits[0]
    return seconds(s["started_at"], s["completed_at"])

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pulse-id", required=True)
    ap.add_argument("--coolprop-run", required=True, type=int)
    ap.add_argument("--abacus-run", required=True, type=int)
    ap.add_argument("--codex-run", required=True, type=int)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    heavy = job("GBOGEB/CoolProp", args.coolprop_run, "HEAVY producer - exact-source wheel")
    fast = job("GBOGEB/CoolProp", args.coolprop_run, "FAST consumer - artifact-only helium probe")
    dow = job("GBOGEB/ABACUS", args.abacus_run, "consume-provider-attestation")
    keb = job("GBOGEB/CODEX", args.codex_run, "consume-provider-attestation")

    row = {
        "pulse_id": args.pulse_id,
        "clock": "github_actions_exact_job_timestamps",
        "evidence_class": "MEASURED",
        "provider_source_sha": heavy["head_sha"],
        "heavy_queue_seconds": seconds(heavy["created_at"], heavy["started_at"]),
        "heavy_checkout_seconds": step_seconds(heavy, "Checkout exact source head"),
        "heavy_build_seconds": step_seconds(heavy, "Build exact-source wheel once"),
        "fast_queue_seconds": seconds(fast["created_at"], fast["started_at"]),
        "fast_execute_seconds": seconds(fast["started_at"], fast["completed_at"]),
        "dow_queue_seconds": seconds(dow["created_at"], dow["started_at"]),
        "dow_execute_seconds": seconds(dow["started_at"], dow["completed_at"]),
        "keb_queue_seconds": seconds(keb["created_at"], keb["started_at"]),
        "keb_execute_seconds": seconds(keb["started_at"], keb["completed_at"]),
        "evidence": {
            "heavy": {"repo": "GBOGEB/CoolProp", "run_id": args.coolprop_run, "job_id": heavy["id"], "runner_id": heavy["runner_id"]},
            "fast": {"repo": "GBOGEB/CoolProp", "run_id": args.coolprop_run, "job_id": fast["id"], "runner_id": fast["runner_id"]},
            "dow": {"repo": "GBOGEB/ABACUS", "run_id": args.abacus_run, "job_id": dow["id"], "runner_id": dow["runner_id"]},
            "keb": {"repo": "GBOGEB/CODEX", "run_id": args.codex_run, "job_id": keb["id"], "runner_id": keb["runner_id"]}
        }
    }
    Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(row, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
