#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

API = "https://api.github.com"

def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def seconds(a: str, b: str) -> int:
    return int((ts(b) - ts(a)).total_seconds())

def fetch(url: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "GBOGEB-MissionControl-MultiClock",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)

def run_meta(repo: str, run_id: int) -> dict:
    return fetch(f"{API}/repos/{repo}/actions/runs/{run_id}")

def run_artifacts(repo: str, run_id: int) -> list[dict]:
    data = fetch(f"{API}/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100")
    return [
        {
            "id": a["id"],
            "name": a["name"],
            "digest": a.get("digest"),
            "expired": a.get("expired"),
        }
        for a in data.get("artifacts", [])
    ]

def job(repo: str, run_id: int, name: str) -> dict:
    data = fetch(f"{API}/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")
    hits = [j for j in data["jobs"] if j["name"] == name]
    if len(hits) != 1:
        raise SystemExit(f"FAIL expected one job {name} in {repo} run {run_id}, got {len(hits)}")
    j = hits[0]
    if j.get("status") != "completed" or j.get("conclusion") != "success":
        raise SystemExit(f"FAIL job not successful: {repo} {run_id} {name}")
    if not j.get("runner_id"):
        raise SystemExit(f"FAIL successful job lacks runner identity: {repo} {run_id} {name}")
    return j

def step_seconds(j: dict, name: str) -> int:
    hits = [s for s in j.get("steps", []) if s["name"] == name]
    if len(hits) != 1 or hits[0].get("conclusion") != "success":
        raise SystemExit(f"FAIL step not successful/unique: {name}")
    s = hits[0]
    return seconds(s["started_at"], s["completed_at"])

def evidence(repo: str, run: dict, j: dict, artifacts: list[dict]) -> dict:
    return {
        "repo": repo,
        "run_id": run["id"],
        "run_attempt": run.get("run_attempt"),
        "head_sha": run["head_sha"],
        "job_id": j["id"],
        "runner_id": j["runner_id"],
        "runner_name": j.get("runner_name"),
        "created_at": j["created_at"],
        "started_at": j["started_at"],
        "completed_at": j["completed_at"],
        "artifacts": artifacts,
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pulse-id", required=True)
    ap.add_argument("--coolprop-run", required=True, type=int)
    ap.add_argument("--abacus-run", required=True, type=int)
    ap.add_argument("--codex-run", required=True, type=int)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    coolprop_run = run_meta("GBOGEB/CoolProp", args.coolprop_run)
    abacus_run = run_meta("GBOGEB/ABACUS", args.abacus_run)
    codex_run = run_meta("GBOGEB/CODEX", args.codex_run)

    heavy = job("GBOGEB/CoolProp", args.coolprop_run, "HEAVY producer - exact-source wheel")
    fast = job("GBOGEB/CoolProp", args.coolprop_run, "FAST consumer - artifact-only helium probe")
    dow = job("GBOGEB/ABACUS", args.abacus_run, "consume-provider-attestation")
    keb = job("GBOGEB/CODEX", args.codex_run, "consume-provider-attestation")

    coolprop_artifacts = run_artifacts("GBOGEB/CoolProp", args.coolprop_run)
    abacus_artifacts = run_artifacts("GBOGEB/ABACUS", args.abacus_run)
    codex_artifacts = run_artifacts("GBOGEB/CODEX", args.codex_run)

    row = {
        "pulse_id": args.pulse_id,
        "clock": "github_actions_exact_job_timestamps",
        "evidence_class": "MEASURED",
        "provider_source_sha": coolprop_run["head_sha"],
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
            "heavy": evidence("GBOGEB/CoolProp", coolprop_run, heavy, coolprop_artifacts),
            "fast": evidence("GBOGEB/CoolProp", coolprop_run, fast, coolprop_artifacts),
            "dow": evidence("GBOGEB/ABACUS", abacus_run, dow, abacus_artifacts),
            "keb": evidence("GBOGEB/CODEX", codex_run, keb, codex_artifacts),
        }
    }
    Path(args.out).write_text(json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(row, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
