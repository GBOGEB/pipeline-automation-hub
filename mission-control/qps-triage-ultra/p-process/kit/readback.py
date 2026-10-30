#!/usr/bin/env python3
"""Code Purple readback: one census of an incident, read from GitHub.

Reads incident.yaml, queries the GitHub REST API through the `gh` CLI, and writes
  census.json        machine-readable census row (one per run; keep them all)
  after_action.md    lift check, red classification, follow-ups, next actions

Classification rule (the core of the method):
  red on the PR head AND red in the latest scheduled run on the default branch -> inherited
  red on the PR head only                                                      -> source-defect candidate
  cancelled / neutral                                                          -> not material

Usage: python readback.py [incident.yaml] [--out DIR]
Needs: gh (authenticated), PyYAML.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml


TRANSIENT = re.compile(r"timeout|timed out|TLS handshake|connection (reset|refused|attempt failed)|connectex|error connecting to|unexpected EOF|HTTP 5\d\d", re.I)


def gh(path: str, paginate: bool = False):
    cmd = ["gh", "api", path] + (["--paginate"] if paginate else [])
    for attempt in range(5):  # retry network blips only; 4xx and auth errors fail at once
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if out.returncode == 0 or not TRANSIENT.search(out.stderr):
            break
        time.sleep(3 * (attempt + 1))
    if out.returncode != 0:
        raise RuntimeError(f"gh api {path}: {out.stderr.strip()[:300]}")
    txt = out.stdout.strip()
    if paginate and txt.startswith("[") and "][" in txt:
        txt = txt.replace("][", ",")
    return json.loads(txt) if txt else None


def check_tally(repo: str, sha: str) -> dict:
    runs = gh(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")["check_runs"]
    tally: dict[str, int] = {}
    reds: list[str] = []
    for r in runs:
        key = r["conclusion"] or r["status"]
        tally[key] = tally.get(key, 0) + 1
        if r["conclusion"] == "failure":
            reds.append(r["name"])
    return {"sha": sha, "total": len(runs), "tally": tally, "reds": sorted(set(reds))}


def main_nightly_reds(repo: str, workflow: str | None, branch: str) -> dict:
    if not workflow:
        return {"workflow": None, "reds": []}
    runs = gh(f"repos/{repo}/actions/workflows/{workflow}/runs?branch={branch}&event=schedule&per_page=1")["workflow_runs"]
    if not runs:
        return {"workflow": workflow, "reds": [], "note": "no scheduled run found"}
    run = runs[0]
    jobs = gh(f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
    reds = sorted({j["name"] for j in jobs if j["conclusion"] == "failure"})
    return {"workflow": workflow, "run_id": run["id"], "sha": run["head_sha"], "at": run["created_at"], "reds": reds}


def pr_state(repo: str, number: int) -> dict:
    p = gh(f"repos/{repo}/pulls/{number}")
    return {"repo": repo, "number": number, "title": p["title"], "state": p["state"], "merged": p["merged"],
            "merged_at": p["merged_at"], "head": p["head"]["sha"], "merge_commit": p.get("merge_commit_sha")}


def missing_rules(actual: list[dict], expected: list[dict]) -> list[str]:
    """Return human-readable gaps between the ruleset's rules and the declared expectation."""
    gaps = []
    for e in expected:
        hits = [r for r in actual if r.get("type") == e["type"]]
        if not hits:
            gaps.append(f"{e['type']} rule absent")
            continue
        if e["type"] == "required_status_checks":
            params = hits[0].get("parameters") or {}
            have = {c.get("context") for c in params.get("required_status_checks", [])}
            for ctx in e.get("contexts", []):
                if ctx not in have:
                    gaps.append(f"required check '{ctx}' absent")
            if e.get("strict") and not params.get("strict_required_status_checks_policy"):
                gaps.append("strict up-to-date policy off")
    return gaps


def gate_at_merge(runs: list[dict], gate_check: str, merged_at: str) -> str:
    """Gate state as of the merge: the latest gate run completed at or before merged_at.

    A rerun that turns green after the merge must not make an ungated merge look gated (L5).
    Runs still open, or finished only after the merge, count as 'in_progress' at merge time."""
    gate = [r for r in runs if r["name"] == gate_check]
    if not gate:
        return "none"
    done = sorted((r for r in gate if r.get("completed_at") and r["completed_at"] <= merged_at), key=lambda r: r["completed_at"])
    return (done[-1]["conclusion"] or "in_progress") if done else "in_progress"


def gate_audit(repo: str, since_iso: str, gate_check: str) -> list[dict]:
    """Every PR merged since `since_iso`: the gate conclusion and red-check count on its merged head."""
    rows = []
    for m in merges_since(repo, since_iso, inclusive=False):
        p = gh(f"repos/{repo}/pulls/{m['number']}")
        sha = p["head"]["sha"]
        runs = gh(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")["check_runs"]
        rows.append({"number": m["number"], "merged_at": m["merged_at"], "head": sha, "merged_by": (p.get("merged_by") or {}).get("login"),
                     "gate": gate_at_merge(runs, gate_check, m["merged_at"]),
                     "reds": sum(1 for r in runs if r["conclusion"] == "failure")})
    return rows


def classify(pr_reds: list[str], inherited: list[str]) -> dict:
    inh = set(inherited)
    return {"inherited": [r for r in pr_reds if r in inh], "source_defect_candidates": [r for r in pr_reds if r not in inh]}


def merges_since(repo: str, iso: str, inclusive: bool = False) -> list[dict]:
    pulls = gh(f"repos/{repo}/pulls?state=closed&sort=updated&direction=desc&per_page=100")
    keep = [p for p in pulls if p["merged_at"] and (p["merged_at"] >= iso if inclusive else p["merged_at"] > iso)]
    return sorted([{"number": p["number"], "merged_at": p["merged_at"], "title": p["title"]} for p in keep], key=lambda x: x["merged_at"])


def run(incident_path: Path, out_dir: Path) -> dict:
    inc = yaml.safe_load(incident_path.read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    repos = {r["name"]: r for r in inc["repos"]}
    census = {"schema": "code-purple.census/v2", "incident": inc["id"], "generated_at": now, "repos": {}, "prs": [], "lift": [], "follow_ups": []}

    for name, r in repos.items():
        main = gh(f"repos/{name}/commits/{r['default_branch']}")
        entry = {"default_head": main["sha"], "default_head_at": main["commit"]["committer"]["date"],
                 "open_prs": len(gh(f"repos/{name}/pulls?state=open&per_page=100")),
                 "nightly": main_nightly_reds(name, r.get("nightly_workflow"), r["default_branch"])}
        if r.get("ruleset_id"):
            rs = gh(f"repos/{name}/rulesets/{r['ruleset_id']}")
            entry["ruleset"] = {"id": rs["id"], "name": rs["name"], "enforcement": rs["enforcement"], "bypass_actors": len(rs["bypass_actors"]),
                                "rules": rs.get("rules", []), "updated_at": rs.get("updated_at")}
            entry["default_branch_protected"] = gh(f"repos/{name}/branches/{r['default_branch']}").get("protected")
        census["repos"][name] = entry

    for t in inc["tracked_prs"]:
        s = pr_state(t["repo"], t["number"])
        s["role"] = t.get("role")
        if not s["merged"] and s["state"] == "open":
            s["checks"] = check_tally(t["repo"], s["head"])
            s["classes"] = classify(s["checks"]["reds"], census["repos"][t["repo"]]["nightly"]["reds"])
        census["prs"].append(s)

    by_pr = {(p["repo"], p["number"]): p for p in census["prs"]}
    for c in inc["lift_criteria"]:
        ref, ok, evidence = c["ref"], False, ""
        if c["kind"] == "pr_merged":
            p = by_pr.get((ref["repo"], ref["number"])) or pr_state(ref["repo"], ref["number"])
            ok, evidence = bool(p["merged"]), f"merged_at={p['merged_at']}"
        elif c["kind"] == "ruleset_clean":
            rs = census["repos"][ref["repo"]]["ruleset"]
            missing = missing_rules(rs["rules"], ref.get("expected_rules", []))
            if not ref.get("expected_rules"):
                missing = ["expected_rules not declared: cannot verify content"]
            ok = rs["enforcement"] == "active" and rs["bypass_actors"] == 0 and not missing and len(rs["rules"]) > 0
            evidence = f"{rs['enforcement']}, bypass={rs['bypass_actors']}, rules={len(rs['rules'])}" + (f"; missing: {'; '.join(missing)}" if missing else "")
        elif c["kind"] == "gated_merges":
            p = by_pr.get((ref["repo"], ref["after_pr"])) or pr_state(ref["repo"], ref["after_pr"])
            audit = gate_audit(ref["repo"], p["merged_at"], ref["gate_check"]) if p["merged_at"] else []
            ungated = [a for a in audit if a["gate"] != "success"]
            census["admission_audit"] = {"since": p["merged_at"], "gate_check": ref["gate_check"], "merged": len(audit),
                                         "gate_green": len(audit) - len(ungated), "ungated": len(ungated),
                                         "with_red_checks": sum(1 for a in audit if a["reds"] > 0),
                                         "by_gate_state": {k: sum(1 for a in audit if a["gate"] == k) for k in sorted({a["gate"] for a in audit})},
                                         "rows": audit}
            ok = len(ungated) <= ref.get("max_ungated", 0)
            evidence = f"{len(audit)} merged; gate green on {len(audit) - len(ungated)}; {census['admission_audit']['with_red_checks']} merged with red checks"
        elif c["kind"] == "merges_since":
            p = by_pr.get((ref["repo"], ref["after_pr"])) or pr_state(ref["repo"], ref["after_pr"])
            m = merges_since(ref["repo"], p["merged_at"]) if p["merged_at"] else []
            ok, evidence = len(m) >= ref["min"], f"{len(m)} merges since {p['merged_at']}"
            census["merges_since_unblock"] = len(m)
        elif c["kind"] == "open_prs_at_most":
            n, base = census["repos"][ref["repo"]]["open_prs"], inc["baseline"]["open_prs"]
            ok, evidence = n <= base * ref["max_fraction_of_baseline"], f"{n} open (baseline {base})"
        census["lift"].append({"id": c["id"], "text": c["text"], "ok": ok, "evidence": evidence})
    census["lifted"] = all(x["ok"] for x in census["lift"])

    for f in inc.get("follow_up_issues", []):
        i = gh(f"repos/{f['repo']}/issues/{f['number']}")
        census["follow_ups"].append({"repo": f["repo"], "number": f["number"], "state": i["state"], "title": i["title"], "check": f["check"]})

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "census.json").write_text(json.dumps(census, indent=2), encoding="utf-8", newline="\n")
    (out_dir / "after_action.md").write_text(render_md(inc, census), encoding="utf-8", newline="\n")
    return census


def render_md(inc: dict, c: dict) -> str:
    L = [f"# {inc['title']}", "", f"Incident `{inc['id']}` · readback {c['generated_at']} · owner {inc['owner']}", ""]
    L += [f"## Lift: {'LIFTED' if c['lifted'] else 'NOT LIFTED'}", "", "| ID | Criterion | Met | Evidence |", "|---|---|---|---|"]
    L += [f"| {x['id']} | {x['text']} | {'yes' if x['ok'] else 'no'} | {x['evidence']} |" for x in c["lift"]]
    a = c.get("admission_audit")
    if a:
        L += ["", "## Admission integrity", "", f"Since {a['since']}: **{a['merged']} merged**, gate `{a['gate_check']}` green on **{a['gate_green']}**, {a['with_red_checks']} merged with at least one red check. Gate states: " + ", ".join(f"{k} {v}" for k, v in a["by_gate_state"].items()) + "."]
    L += ["", "## Tracked PRs", "", "| PR | Role | State | Inherited reds | Source-defect candidates |", "|---|---|---|---|---|"]
    for p in c["prs"]:
        st = "merged" if p["merged"] else p["state"]
        cl = p.get("classes", {})
        L.append(f"| {p['repo']}#{p['number']} | {p['role']} | {st} | {', '.join(cl.get('inherited', [])) or '—'} | {', '.join(cl.get('source_defect_candidates', [])) or '—'} |")
    L += ["", "## Default branches", "", "| Repo | Head | Open PRs | Nightly reds (inherited set) | Ruleset |", "|---|---|---|---|---|"]
    for n, r in c["repos"].items():
        rs = r.get("ruleset")
        L.append(f"| {n} | `{r['default_head'][:8]}` | {r['open_prs']} | {', '.join(r['nightly']['reds']) or '—'} | {f'{rs['enforcement']}, bypass {rs['bypass_actors']}' if rs else 'none'} |")
    L += ["", "## Follow-ups", ""]
    L += [f"- {f['repo']}#{f['number']} ({f['state']}): {f['title']} — check: {f['check']}" for f in c["follow_ups"]]
    open_f = [f for f in c["follow_ups"] if f["state"] == "open"]
    L += ["", "## Next actions", ""]
    if not c["lifted"]:
        L += [f"- Meet {x['id']}: {x['text']} ({x['evidence']})" for x in c["lift"] if not x["ok"]]
    L += [f"- Verify on the default branch, then close {f['repo']}#{f['number']}" for f in open_f]
    L += ["- Turn every inherited red into a dated burn-down item; never repair it inside an unrelated PR"]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("incident", nargs="?", default=str(Path(__file__).with_name("incident.yaml")))
    ap.add_argument("--out", default=str(Path(__file__).with_name("out")))
    a = ap.parse_args()
    c = run(Path(a.incident), Path(a.out))
    print(json.dumps({"lifted": c["lifted"], "lift": [(x["id"], x["ok"]) for x in c["lift"]], "merges_since_unblock": c.get("merges_since_unblock")}))
    sys.exit(0)
