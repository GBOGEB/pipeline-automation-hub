#!/usr/bin/env python3
"""Evaluate the P process: which mode each repository is in, and why.

Inputs: kit census (Code Purple lift), EVERRED report (roots + probes), ruleset drift. Pure function `decide`;
the CLI writes p_state.json. UNKNOWN stays UNKNOWN: a repo with no drift entry is reported, never green.
Usage: python p_decide.py [--census F] [--everred F] [--drift F] [--out F]
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREFIX = {"ABACUS": "GBOGEB/ABACUS", "CODEX": "GBOGEB/CODEX", "CRYO": "GBOGEB/cryoplant-project", "GGMATH": "GBOGEB/gg_MATH",
          "PAH": "GBOGEB/pipeline-automation-hub", "QET": "GBOGEB/Q_engineering_tools"}
OPEN = {"DISCOVERED", "TRIAGED", "OWNED", "FIX_COMMITTED", "PRODUCER_GREEN", "CONSUMERS_REPLAYED", "BLOCKED_AUTHORITY",
        "BLOCKED_INFRA", "BLOCKED_DEPENDENCY", "REOPENED"}


def repo_of(root_id: str) -> str:
    return PREFIX.get(root_id.split("-")[0], "UNKNOWN")


def decide(census: dict, everred: dict, drift: dict, cp_repos: list[str]) -> dict:
    repos = sorted(set(drift.get("repos", {})) | set(PREFIX.values()))
    roots = everred.get("roots", [])
    out = {}
    for repo in repos:
        rr = [r for r in roots if repo_of(r["id"]) == repo]
        reasons = []
        if repo in cp_repos and not census.get("lifted", False):
            met = sum(1 for x in census.get("lift", []) if x.get("ok"))
            reasons.append(f"E2: Code Purple case open, {met} of {len(census.get('lift', []))} lift criteria met")
        for r in rr:
            if r.get("severity") == "P0" and (r.get("probe") or {}).get("red") and r.get("state") in OPEN:
                reasons.append(f"E1: {r['id']} P0 control-plane probe red")
        d = drift.get("repos", {}).get(repo)
        open_roots = [r for r in rr if r.get("state") in OPEN and not r.get("derived")]
        out[repo] = {
            "mode": "CODE_PURPLE" if reasons else "EVERRED",
            "reasons": reasons,
            "ruleset": "UNKNOWN" if d is None else ("RED" if d.get("red") else "GREEN"),
            "ruleset_gaps": None if d is None else d.get("gaps", []),
            "open_roots": len(open_roots),
            "worst": min((r.get("severity", "P9") for r in open_roots), default=None),
        }
    return {"schema": "p-process.state/1.0", "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "census_at": census.get("generated_at"), "everred_at": everred.get("generated_at"), "drift_at": drift.get("generated_at"),
            "lifted": census.get("lifted"), "repos": out}


def first(*c):
    return next(Path(x) for x in c if x and Path(x).is_file())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--census"); ap.add_argument("--everred"); ap.add_argument("--drift")
    ap.add_argument("--out", default=str(ROOT / "site/data/p_state.json"))
    a = ap.parse_args()
    census = json.loads(first(a.census, ROOT / "kit/out/census.json", ROOT / "site/code-purple/kit/census.json").read_text())
    ev = json.loads(first(a.everred, ROOT / "everred/out/everred.json", ROOT / "site/everred/data/everred.json").read_text())
    drift = json.loads(first(a.drift, ROOT / "rulesets/drift.json").read_text())
    import yaml
    inc = yaml.safe_load((ROOT / "kit/incident.yaml").read_text())
    cp = [r["name"] for r in inc["repos"] if r.get("role") == "blocked"]
    st = decide(census, ev, drift, cp)
    st["incident"] = inc["id"]
    o = Path(a.out); o.parent.mkdir(parents=True, exist_ok=True)
    o.write_text(json.dumps(st, indent=2) + "\n")
    print(json.dumps({k: v["mode"] for k, v in st["repos"].items()}))


if __name__ == "__main__":
    main()
