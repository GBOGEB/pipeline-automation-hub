#!/usr/bin/env python3
"""EVERRED harvest: failure occurrences -> signatures -> roots, with DMAIC metrics.

Scope per repo (bounded, reproducible):
  * default branch: failed checks on the current head + latest scheduled run of each declared nightly workflow
  * open PRs: exact head
  * recently merged PRs: merged head (to measure what entered main)

For every failed Actions job it records one OCCURRENCE per failed step:
  repo, sha, pr, workflow, job, step, run_id, run_attempt, job_id, url, environment (OS/Python split out of the name)
Signature = normalized "workflow :: job :: step" (environment and hashes removed).
Each signature is linked to the first ROOT whose `match` covers it; otherwise it is UNMATCHED (a candidate root).

Outputs (out/):
  occurrences.json   every occurrence (immutable evidence for this census)
  everred.json       roots with linked occurrences, unmatched signatures, metrics
  rex_return.yaml    CODEX REX return (schema gbogeb-repo-rex-return/1.0): one record per root, merge key = signature
  register.md        human register

Metrics follow EVERRED §9: unknown denominators produce "UNKNOWN", never 0.
Usage: python harvest.py [roots.yaml] [--merged 20] [--out DIR]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ENV_RE = [
    re.compile(r"\s*\((Python\s*3\.\d+,\s*)?(ubuntu|windows|macos)[\w.-]*\)", re.I),   # "(Python 3.12, ubuntu-latest)"
    re.compile(r"\s*\(py3\.\d+\)", re.I),
    re.compile(r"\s*[-–]\s*(ubuntu|windows|macos)[\w.-]*", re.I),                       # " - ubuntu-24.04"
    re.compile(r"\s*[-–]?\s*Python\s*3\.\d+", re.I),                                   # " - Python 3.12"
]
HEX_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
SEQ_RE = re.compile(r"(?<=-)\d{3}\b")
CACHE: dict[str, object] = {}


def gh(path: str):
    if path in CACHE:
        return CACHE[path]
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"gh api {path}: {out.stderr.strip()[:200]}")
    CACHE[path] = json.loads(out.stdout) if out.stdout.strip() else None
    return CACHE[path]


def split_env(name: str) -> tuple[str, str]:
    env = []
    for rx in ENV_RE:
        for m in rx.finditer(name):
            env.append(m.group(0).strip(" -–()"))
        name = rx.sub("", name)
    return name.strip(), ", ".join(e for e in env if e)


def norm(s: str) -> str:
    return SEQ_RE.sub("*", HEX_RE.sub("<sha>", s)).strip()


def failed_jobs_for_sha(repo: str, sha: str) -> list[dict]:
    runs = gh(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")["check_runs"]
    jobs = []
    for r in runs:
        if r["conclusion"] != "failure" or "/actions/runs/" not in (r.get("html_url") or ""):
            continue
        try:
            j = gh(f"repos/{repo}/actions/jobs/{r['id']}")
        except RuntimeError:
            continue
        jobs.append(j)
    return jobs


def occurrences_from_job(repo: str, j: dict, pr: int | None, source: str) -> list[dict]:
    job, env = split_env(j["name"])
    steps = [s for s in j.get("steps", []) if s.get("conclusion") == "failure"] or [{"name": "(job failed, no failed step)", "number": None}]
    out = []
    for s in steps:
        out.append({
            "repo": repo, "sha": j["head_sha"], "pr": pr, "source": source,
            "workflow": j.get("workflow_name") or "?", "job": job, "env": env, "step": s["name"], "step_number": s.get("number"),
            "run_id": j["run_id"], "run_attempt": j.get("run_attempt"), "job_id": j["id"], "url": j["html_url"],
            "completed_at": j.get("completed_at"), "runner": j.get("runner_name"),
            "signature": f"{norm(j.get('workflow_name') or '?')} :: {norm(job)} :: {norm(s['name'])}",
        })
    return out


def harvest(repo: str, branch: str, nightly: list[str], merged_n: int) -> list[dict]:
    occ: list[dict] = []
    # default branch: every failed check on the current head, plus the latest scheduled run of each nightly workflow
    head = gh(f"repos/{repo}/commits/{branch}")["sha"]
    for j in failed_jobs_for_sha(repo, head):
        occ += occurrences_from_job(repo, j, None, f"{branch}:head")
    for wf in nightly:
        runs = gh(f"repos/{repo}/actions/workflows/{wf}/runs?branch={branch}&event=schedule&per_page=1")["workflow_runs"]
        if runs and runs[0]["conclusion"] == "failure" and runs[0]["head_sha"] != head:
            for j in gh(f"repos/{repo}/actions/runs/{runs[0]['id']}/jobs?per_page=100")["jobs"]:
                if j["conclusion"] == "failure":
                    j.setdefault("workflow_name", runs[0]["name"])
                    occ += occurrences_from_job(repo, j, None, f"{branch}:nightly")
    # open PRs
    for p in gh(f"repos/{repo}/pulls?state=open&per_page=50"):
        for j in failed_jobs_for_sha(repo, p["head"]["sha"]):
            occ += occurrences_from_job(repo, j, p["number"], "open-pr")
    # recently merged PRs
    closed = gh(f"repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100")
    merged = sorted([p for p in closed if p["merged_at"]], key=lambda p: p["merged_at"], reverse=True)[:merged_n]
    for p in merged:
        for j in failed_jobs_for_sha(repo, p["head"]["sha"]):
            occ += occurrences_from_job(repo, j, p["number"], "merged-pr")
    return occ


def matches(o: dict, m: dict) -> bool:
    if "probe" in m:
        return False
    if m.get("repo") and m["repo"] != o["repo"]:
        return False
    for key in ("workflow", "job", "step"):
        if m.get(key) and m[key].lower() not in o[key].lower():
            return False
    return True


def load_drift(drift_path: str | None = None) -> dict:
    """Per-repo ruleset drift. Reads drift_path (from verify_rulesets.py) or runs the probe now."""
    rs_dir = Path(__file__).resolve().parent.parent / "rulesets"
    if not drift_path:
        r = subprocess.run([sys.executable, str(rs_dir / "verify_rulesets.py")], capture_output=True, text=True, cwd=rs_dir)
        if r.returncode != 0:
            raise RuntimeError(f"verify_rulesets.py failed: {r.stderr.strip()[:300]}")
        drift_path = str(rs_dir / "drift.json")
    return json.loads(Path(drift_path).read_text())["repos"]


def probe_root(root: dict, drift: dict) -> dict | None:
    """Control-plane probe result for one root (V3 governance dimension); None if the root has no probe."""
    for m in root.get("match", []):
        if m.get("probe") == "ruleset_drift":
            d = drift.get(m["repo"])
            if d is None:  # repo not probed: fail closed, never green by omission
                return {"probe": "ruleset_drift", "red": True, "detail": f"{m['repo']} absent from drift census"}
            detail = f"effective={','.join(d.get('effective_rules') or []) or 'none'}; gaps={len(d.get('gaps', []))}"
            if d.get("untargeted_rulesets"):
                detail += "; " + "; ".join(d["untargeted_rulesets"])
            return {"probe": "ruleset_drift", "red": bool(d.get("red", True)), "detail": detail, "gaps": d.get("gaps", [])}
    return None


def run_probes(roots: list[dict], drift_path: str | None = None) -> dict[str, dict]:
    if not any(m.get("probe") for r in roots for m in r.get("match", [])):
        return {}
    drift = load_drift(drift_path)
    return {r["id"]: p for r in roots if (p := probe_root(r, drift))}


def ratio(n, d):
    return "UNKNOWN" if not d else round(n / d, 3)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("roots", nargs="?", default=str(Path(__file__).with_name("roots.yaml")))
    ap.add_argument("--merged", type=int, default=20)
    ap.add_argument("--out", default=str(Path(__file__).with_name("out")))
    ap.add_argument("--drift", help="drift.json from verify_rulesets.py (default: run the probe now)")
    a = ap.parse_args()
    ledger = yaml.safe_load(Path(a.roots).read_text(encoding="utf-8"))
    roots = ledger["roots"]
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    occ = []
    for repo in ledger["repo_scope"]:
        occ += harvest(repo, "main", ledger.get("nightly_workflows", {}).get(repo, []), a.merged)
    probes = run_probes(roots, a.drift)

    linked = defaultdict(list)
    unmatched = defaultdict(list)
    for o in occ:
        rid = next((r["id"] for r in roots for m in r.get("match", []) if matches(o, m)), None)
        o["root"] = rid
        (linked[rid] if rid else unmatched[o["signature"]]).append(o)

    independent = [r for r in roots if not r.get("derived")]
    verified_states = {"TRIAGED", "OWNED", "FIX_COMMITTED", "PRODUCER_GREEN", "CONSUMERS_REPLAYED", "VERIFIED_FIXED", "CLOSED", "BLOCKED_AUTHORITY", "BLOCKED_INFRA", "BLOCKED_DEPENDENCY"}
    verified = [r for r in independent if r["state"] in verified_states]
    occ_indep = [o for o in occ if o["root"] and not next(r for r in roots if r["id"] == o["root"]).get("derived")]
    closed_like = [r for r in independent if r["state"] in ("VERIFIED_FIXED", "CLOSED")]
    reopened = [r for r in independent if r["state"] == "REOPENED"]
    consumers_known = [r for r in independent if r.get("consumers")]
    metrics = {
        "occurrences_total": len(occ),
        "occurrences_on_independent_roots": len(occ_indep),
        "distinct_signatures": len({o["signature"] for o in occ}),
        "roots_independent": len(independent),
        "roots_triaged_or_later": len(verified),
        "unmatched_signatures": len(unmatched),
        "failure_amplification": ratio(len(occ_indep), len(verified)),
        "failure_amplification_note": "occurrences linked to triaged independent roots / triaged independent roots",
        "signature_amplification_upper_bound": ratio(len(occ), len({o["signature"] for o in occ})),
        "root_closure_rate": ratio(len(closed_like), len(independent)),
        "recurrence_rate": ratio(len(reopened), len(closed_like)),
        "consumer_replay_coverage": "UNKNOWN",
        "consumer_replay_note": f"no replay outcomes recorded yet; {len(consumers_known)} roots list consumers",
        "active_roots_by_state": dict(Counter(r["state"] for r in independent)),
        "occurrences_by_source": dict(Counter(o["source"] for o in occ)),
        "control_plane_red": sum(1 for p in probes.values() if p["red"]),
        "control_plane_probed": len(probes),
        "dims": {d: dict(Counter((r.get("dims") or {}).get(d, "UNKNOWN") for r in independent)) for d in ["diagnosis", "repair", "integration", "security", "governance", "admission", "control"]},
    }

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "occurrences.json").write_text(json.dumps(occ, indent=1), encoding="utf-8")
    report = {"schema": "everred.census/1.0", "generated_at": now, "scope": ledger["repo_scope"], "metrics": metrics, "probes": probes,
              "roots": [{**{k: v for k, v in r.items() if k != "match"},
                         "occurrences": len(linked[r["id"]]),
                         "affected_prs": sorted({o["pr"] for o in linked[r["id"]] if o["pr"]}),
                         "affected_shas": len({o["sha"] for o in linked[r["id"]]}),
                         "probe": probes.get(r["id"]),
                         "last_seen": max((o["completed_at"] or "" for o in linked[r["id"]]), default=None)} for r in roots],
              "unmatched": [{"signature": s, "occurrences": len(v), "prs": sorted({o["pr"] for o in v if o["pr"]}),
                             "repos": sorted({o["repo"] for o in v}), "example_url": v[0]["url"]} for s, v in sorted(unmatched.items(), key=lambda x: -len(x[1]))]}
    (out / "everred.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    (out / "rex_return.yaml").write_text(yaml.safe_dump(rex_return(report, now), sort_keys=False, allow_unicode=True), encoding="utf-8")
    (out / "register.md").write_text(render(report), encoding="utf-8")
    print(json.dumps(metrics, indent=1))


STATE_TO_REX = {"DISCOVERED": "OPEN", "TRIAGED": "OPEN", "OWNED": "OPEN", "REOPENED": "OPEN", "FIX_COMMITTED": "CONTAINED",
                "PRODUCER_GREEN": "REPAIRED", "CONSUMERS_REPLAYED": "VERIFIED", "VERIFIED_FIXED": "VERIFIED", "CLOSED": "CONTROLLED",
                "BLOCKED_AUTHORITY": "DEFERRED", "BLOCKED_INFRA": "DEFERRED", "BLOCKED_DEPENDENCY": "DEFERRED"}
CLASS_TO_FAMILY = {"PRODUCT_DEFECT": "VALIDATION", "TEST_OR_MEASUREMENT_DEFECT": "VALIDATION", "GENERATED_ARTIFACT_DRIFT": "ARTIFACT",
                   "INFRA_ENV_DEFECT": "RUNTIME", "EXISTING_REPOSITORY_DEBT": "CI_CD", "SECURITY_OR_POLICY": "SECURITY", "CONTROL_PLANE_DRIFT": "AUTHORITY"}


def rex_return(rep: dict, now: str) -> dict:
    recs = []
    for r in rep["roots"]:
        if r.get("derived"):
            continue
        recs.append({"rex_id": r["id"].replace("EVR-", "REX-"), "signature": f"everred.{r['class'].lower()}.{r['id'].lower()}",
                     "issue_kind": "INCIDENT" if r["class"] == "CONTROL_PLANE_DRIFT" else "DEBT" if r["class"] == "EXISTING_REPOSITORY_DEBT" else "DEFECT",
                     "family": CLASS_TO_FAMILY[r["class"]], "symptom": r["title"],
                     "frequency": {"observed_count": r["occurrences"], "unit": "occurrences", "measurement_window": rep["generated_at"]},
                     "root_cause": "; ".join(r.get("evidence", [])) or "UNKNOWN", "repair_method": r.get("canonical_repair"),
                     "control_guard": [r.get("regression_contract")], "control_status": STATE_TO_REX[r["state"]], "everred_state": r["state"]})
    return {"schema": "gbogeb-repo-rex-return/1.0", "repo": "GBOGEB/ABACUS", "measurement_window": {"end": now, "basis": "everred harvest"},
            "records": recs, "return_contract": {"consumer": "GBOGEB/CODEX", "merge_key": "signature_plus_authority_relevant_scope", "authority_transfer": False}}


def render(rep: dict) -> str:
    m = rep["metrics"]
    L = ["# EVERRED register", "", f"Census {rep['generated_at']} · scope {', '.join(rep['scope'])}", "", "## Metrics", ""]
    L += [f"- **{k}**: {v}" for k, v in m.items()]
    L += ["", "## Roots", "", "| Root | Class | State | Owner | Occurrences | PRs | Probe | Title |", "|---|---|---|---|---|---|---|---|"]
    for r in rep["roots"]:
        pr = ", ".join(f"#{n}" for n in r["affected_prs"][:8]) + (" …" if len(r["affected_prs"]) > 8 else "")
        probe = ("RED: " if r["probe"]["red"] else "green: ") + r["probe"]["detail"] if r.get("probe") else ""
        L.append(f"| {r['id']}{' (derived)' if r.get('derived') else ''} | {r['class']} | {r['state']} | {r.get('owner') or '—'} | {r['occurrences']} | {pr or '—'} | {probe} | {r['title']} |")
    L += ["", "## Unmatched signatures (candidate roots — search the ledger before repairing)", "", "| Signature | Occurrences | PRs | Example |", "|---|---|---|---|"]
    L += [f"| `{u['signature']}` | {u['occurrences']} | {', '.join(f'#{n}' for n in u['prs'][:6]) or 'main'} | [run]({u['example_url']}) |" for u in rep["unmatched"]]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
