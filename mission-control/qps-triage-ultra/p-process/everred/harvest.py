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

Private repos (gh api repos/<r> says private, or the lookup fails) count in every metric but are
published as counts only (`private_aggregate`); none of their rows reach any output.
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
import time
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
TRANSIENT = re.compile(r"timeout|timed out|TLS handshake|connection (reset|refused|attempt failed)|connectex|error connecting to|unexpected EOF|HTTP 5\d\d", re.I)


def gh(path: str, tries: int = 5):
    """One cached gh api read. Network blips (TRANSIENT) are retried with backoff; 4xx, auth and any
    other error fail at once, and a blip that outlasts every try raises."""
    if path in CACHE:
        return CACHE[path]
    for attempt in range(tries):
        out = subprocess.run(["gh", "api", path], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if out.returncode == 0 or not TRANSIENT.search(out.stderr) or attempt == tries - 1:
            break
        time.sleep(3 * (attempt + 1))
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


def _check_run_pass(repo: str, sha: str) -> tuple[dict, list[int]]:
    """One uncached paged read: runs by id and the total_count reported on each page."""
    runs, totals, page = {}, [], 1
    while True:
        path = f"repos/{repo}/commits/{sha}/check-runs?per_page=100&page={page}"
        CACHE.pop(path, None)
        body = gh(path)
        totals.append(body["total_count"])
        batch = body["check_runs"]
        for r in batch:
            runs.setdefault(r["id"], r)
        if not batch or len(runs) >= totals[-1]:
            return runs, totals
        page += 1


PASS_PAUSE_S = 15  # pause before re-reading a head whose CI was still moving; n-th re-read waits n x this


def check_runs_for_sha(repo: str, sha: str, attempts: int = 6) -> list[dict]:
    """Every check run on sha, paged against total_count. Fails closed unless the census is stable.

    A single per_page=100 read silently dropped runs past 100 (ABACUS main had 121 on 2026-10-24).
    A head with live CI gains or loses runs between pages (ABACUS main grew 807 -> 811 within one read
    on 2026-10-25), and a shifted page can then hide a run although the counts add up. A pass is stable
    when total_count did not change across its pages and exactly that many distinct runs were read. The
    census is accepted only when two consecutive stable passes return the same id set; otherwise it is
    re-read, up to `attempts` passes, then raises. After a pass that moved or disagreed, the re-read waits
    (PASS_PAUSE_S x pass number) so in-flight CI can settle; the acceptance rule itself never loosens.
    """
    prev: dict | None = None
    settling = False
    for n in range(attempts):
        if settling:
            time.sleep(PASS_PAUSE_S * n)
        runs, totals = _check_run_pass(repo, sha)
        stable = len(set(totals)) == 1 and len(runs) == totals[0]
        if stable and prev is not None and set(runs) == set(prev):
            return list(runs.values())
        settling = not stable or prev is not None
        prev = runs if stable else None
    raise RuntimeError(f"check-runs for {repo}@{sha}: no two consecutive stable reads agreed; "
                       f"last read {len(runs)} distinct of total_count {'/'.join(map(str, totals))}")


def failed_jobs_for_sha(repo: str, sha: str) -> list[dict]:
    runs = check_runs_for_sha(repo, sha)
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
        r = subprocess.run([sys.executable, str(rs_dir / "verify_rulesets.py")], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=rs_dir)
        if r.returncode != 0:
            raise RuntimeError(f"verify_rulesets.py failed: {r.stderr.strip()[:300]}")
        drift_path = str(rs_dir / "drift.json")
    return json.loads(Path(drift_path).read_text(encoding="utf-8"))["repos"]


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
    private = {repo for repo in ledger["repo_scope"] if is_private(repo)}
    report, public_occ = build_report(ledger["repo_scope"], roots, occ, probes, now, private)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "occurrences.json").write_text(json.dumps(public_occ, indent=1), encoding="utf-8", newline="\n")
    (out / "everred.json").write_text(json.dumps(report, indent=1), encoding="utf-8", newline="\n")
    (out / "rex_return.yaml").write_text(yaml.safe_dump(rex_return(report, now), sort_keys=False, allow_unicode=True), encoding="utf-8", newline="\n")
    (out / "register.md").write_text(render(report), encoding="utf-8", newline="\n")
    print(json.dumps(report["metrics"], indent=1))


def is_private(repo: str) -> bool:
    """Privacy is read from the source (gh api repos/<r>, cached by gh()). Fails closed: a failed or
    ambiguous lookup counts the repo as private."""
    try:
        return (gh(f"repos/{repo}") or {}).get("private") is not False
    except RuntimeError:
        return True


def build_report(scope: list[str], roots: list[dict], occ: list[dict], probes: dict, now: str,
                 private: set[str] = frozenset()) -> tuple[dict, list[dict]]:
    """everred.json report + the publishable occurrence rows.

    Occurrences from `private` repos count in every aggregate metric, but no row-level private data
    (PR numbers, SHAs, run/job ids or URLs, workflow/job/step text, signatures, runners) is returned:
    they appear only as counts under `private_aggregate`.
    """
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

    def pub(rows):
        return [o for o in rows if o["repo"] not in private]

    public_unmatched = defaultdict(list)
    for o in pub(occ):
        if not o["root"]:
            public_unmatched[o["signature"]].append(o)
    private_aggregate = {}
    for repo in sorted(private):
        mine = [o for o in occ if o["repo"] == repo]
        private_aggregate[repo] = {"occurrences": len(mine), "distinct_signatures": len({o["signature"] for o in mine}),
                                   "unmatched_signatures": len({o["signature"] for o in mine if not o["root"]}),
                                   "linked_roots": dict(Counter(o["root"] for o in mine if o["root"]))}
    report = {"schema": "everred.census/1.0", "generated_at": now, "scope": scope, "metrics": metrics, "probes": probes,
              "roots": [{**{k: v for k, v in r.items() if k != "match"},
                         "occurrences": len(linked[r["id"]]),
                         "affected_prs": sorted({o["pr"] for o in pub(linked[r["id"]]) if o["pr"]}),
                         "affected_shas": len({o["sha"] for o in linked[r["id"]]}),
                         "probe": probes.get(r["id"]),
                         "last_seen": max((o["completed_at"] or "" for o in pub(linked[r["id"]])), default=None)} for r in roots],
              "unmatched": [{"signature": s, "occurrences": len(v), "prs": sorted({o["pr"] for o in v if o["pr"]}),
                             "repos": sorted({o["repo"] for o in v}), "example_url": v[0]["url"]} for s, v in sorted(public_unmatched.items(), key=lambda x: -len(x[1]))],
              "private_rows": "AGGREGATE_ONLY", "private_aggregate": private_aggregate}
    return report, pub(occ)


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
    if rep.get("private_aggregate"):
        L += ["", "## Private repositories (aggregate counts only; no rows are published)", "",
              "| Repo | Occurrences | Distinct signatures | Unmatched signatures | Linked roots |", "|---|---|---|---|---|"]
        L += [f"| {repo} | {a['occurrences']} | {a['distinct_signatures']} | {a['unmatched_signatures']} | "
              f"{', '.join(f'{k}: {v}' for k, v in a['linked_roots'].items()) or '—'} |" for repo, a in rep["private_aggregate"].items()]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
