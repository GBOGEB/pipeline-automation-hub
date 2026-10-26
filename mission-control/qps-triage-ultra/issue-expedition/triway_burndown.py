#!/usr/bin/env python3
"""Read-only Mission Control issue burndown (hub #308/#324/#372).

This consumer ranks textual observations, not engineering decisions.
A checkbox is self-report, a mention is association, a dependency phrase is
a candidate blocker, a PR is not proof, and no score confers closure credit.
"""
from __future__ import annotations
import argparse
import csv
import importlib.util
import hashlib
import io
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

# Consume the sole title-vocabulary authority in issue_rank, never fork a parser.
_TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "issue_rank" / "title_taxonomy.py"
_spec = importlib.util.spec_from_file_location("missioncontrol_title_taxonomy", _TAXONOMY_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("title taxonomy provider unavailable")
tt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tt)

SCHEMA = "missioncontrol.issue_expedition.triway.v1"
CENSUS = "missioncontrol.issue_expedition.github_census.v1"
DEFAULT_REPOS = ("GBOGEB/cryoplant-project", "GBOGEB/ABACUS",
                 "GBOGEB/CODEX", "GBOGEB/pipeline-automation-hub",
                 "GBOGEB/gg_MATH")
REPO = re.compile(r"GBOGEB/[A-Za-z0-9_.-]+\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
ITEM = re.compile(r"^\s*[-*]\s+\[([xX ])\]\s+(.+?)\s*$")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
REF = re.compile(
    r"https://github\.com/GBOGEB/(?P<urlrepo>[A-Za-z0-9_.-]+)/issues/(?P<urlnum>\d+)"
    r"|GBOGEB/(?P<namerepo>[A-Za-z0-9_.-]+)#(?P<namenum>\d+)"
    r"|(?<![A-Za-z0-9/])#(?P<localnum>\d+)"
)
DEP = re.compile(r"\b(?:blocked by|depends on|waiting for|requires)\b.{0,72}\Z", re.I)
CLAIM = re.compile(r"\b(?:fix(?:es|ed)?|clos(?:es|ed)?|resolv(?:es|ed)?)\b.{0,40}\Z", re.I)
PRIORITY = re.compile(r"(?:^|[/:\s_-])P([0-4])(?:$|[/:\s_-])", re.I)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def timestamp(value):
    require(isinstance(value, str) and value, "timestamp absent")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    require(dt.tzinfo is not None, "naive timestamp forbidden")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def identity(repo, number):
    require(isinstance(repo, str) and bool(REPO.fullmatch(repo)), "bad repo")
    require(type(number) is int and number > 0, "bad number")
    return f"{repo}#{number}"


def checklist(body):
    """Return explicit DoD/DoV steps; no checklist => null, not 0/0."""
    steps = {"DoD": [], "DoV": [], "OTHER": []}
    section = "OTHER"
    for line in body.splitlines():
        h = HEADING.match(line)
        if h:
            title = h.group(1)
            section = ("DoD" if re.search(r"\bDoD\b|definition of done", title, re.I)
                       else "DoV" if re.search(r"\bDoV\b|definition of verification", title, re.I)
                       else "OTHER")
            continue
        m = ITEM.match(line)
        if m:
            steps[section].append({"text": m.group(2)[:300],
                                   "checked_in_issue": m.group(1).lower() == "x",
                                   "evidence": "ISSUE_BODY_SELF_ASSERTED_UNVERIFIED"})
    def summary(rows):
        return (None if not rows else
                {"checked": sum(x["checked_in_issue"] for x in rows),
                 "total": len(rows),
                 "remaining": sum(not x["checked_in_issue"] for x in rows),
                 "grade": "SELF_REPORTED_NOT_QUALIFIED"})
    return {key: {"items": val, "progress": summary(val)} for key, val in steps.items()}


def references(body, repo, pr=False):
    found = {}
    fence = False
    for line in body.splitlines():
        if line.strip().startswith((chr(96) * 3, "~~~")):
            fence = not fence
            continue
        if fence:
            continue
        for m in REF.finditer(line):
            name = m.group("urlrepo") or m.group("namerepo") or repo.split("/")[1]
            num = int(m.group("urlnum") or m.group("namenum") or m.group("localnum"))
            target = identity("GBOGEB/" + name, num)
            before = line[max(0, m.start() - 90):m.start()]
            kind = ("PR_CLOSURE_CLAIM" if pr and CLAIM.search(before) else
                    "PR_ASSOCIATION" if pr else
                    "DECLARED_BLOCKER_CANDIDATE" if DEP.search(before) else
                    "TEXT_ASSOCIATION")
            found[target, kind] = {"target": target, "kind": kind,
                                   "grade": "UNVERIFIED_SOURCE_TEXT"}
    return [found[key] for key in sorted(found)]


def priority(labels, title):
    ps = []
    for raw in labels:
        name = raw if isinstance(raw, str) else raw.get("name", "")
        m = PRIORITY.search(name)
        if m:
            ps.append(int(m.group(1)))
    if ps:
        return "P" + str(min(ps)), "ISSUE_LABEL"
    m = re.match(r"^\s*\[?P([0-4])(?:\]|:|[- ])", title, re.I)
    return ("P" + m.group(1), "ISSUE_TITLE") if m else ("UNKNOWN", "UNCLASSIFIED")


def validate(c):
    require(isinstance(c, dict) and c.get("schema") == CENSUS, "bad census schema")
    require(c.get("authority_transfer") is False
            and c.get("formal_credit_delta") == 0, "authority/credit escalation")
    observed = timestamp(c.get("observed_at"))
    repos = c.get("repositories")
    require(isinstance(repos, list) and bool(repos)
            and len(repos) == len(set(repos))
            and all(isinstance(r, str) and REPO.fullmatch(r) for r in repos), "bad scope")
    heads = c.get("source_heads")
    require(isinstance(heads, dict) and set(heads) == set(repos)
            and all(isinstance(s, str) and SHA.fullmatch(s) for s in heads.values()),
            "missing exact-head readback")
    issues, prs = c.get("issues"), c.get("pull_requests")
    require(isinstance(issues, list) and isinstance(prs, list), "missing populations")
    ids = set()
    for issue in issues:
        require(isinstance(issue, dict) and issue.get("repo") in repos, "out-of-scope issue")
        key = identity(issue["repo"], issue.get("number"))
        require(key not in ids, "duplicate issue")
        ids.add(key)
        require(issue.get("state") == "open", "non-open issue in open census")
        require(isinstance(issue.get("body"), str)
                and isinstance(issue.get("title"), str)
                and isinstance(issue.get("labels"), list), "missing issue fields")
        timestamp(issue.get("created_at"))
        timestamp(issue.get("updated_at"))
    prids = set()
    for pr in prs:
        require(isinstance(pr, dict) and pr.get("repo") in repos, "out-of-scope PR")
        key = identity(pr["repo"], pr.get("number"))
        require(key not in prids and pr.get("state") == "open"
                and isinstance(pr.get("body"), str), "invalid open PR")
        prids.add(key)
    counts = c.get("counts")
    require(isinstance(counts, dict) and set(counts) == set(repos), "count manifest mismatch")
    for repo in repos:
        n = counts[repo]
        require(isinstance(n, dict) and type(n.get("issues")) is int
                and type(n.get("prs")) is int
                and n["issues"] == sum(x["repo"] == repo for x in issues)
                and n["prs"] == sum(x["repo"] == repo for x in prs), "incomplete census")
    return observed, repos, heads, issues, prs


def project(census, previous=None):
    observed, repos, heads, issues, prs = validate(census)
    nodes, edge_map = {}, {}
    for issue in issues:
        repo, n = issue["repo"], issue["number"]
        key = identity(repo, n)
        p, basis = priority(issue["labels"], issue["title"])
        checks = checklist(issue["body"])
        nodes[key] = {
            "ref": key, "repo": repo, "number": n,
            "url": f"https://github.com/{repo}/issues/{n}",
            "title": issue["title"],
            "title_taxonomy": tt.parse_title(issue["title"], "Issue", issue["labels"]),
            "created_at": timestamp(issue["created_at"]),
            "updated_at": timestamp(issue["updated_at"]),
            "priority": p, "priority_basis": basis,
            "body_sha256": hashlib.sha256(issue["body"].encode()).hexdigest(),
            "DoD": checks["DoD"], "DoV": checks["DoV"],
            "unclassified_checklist": checks["OTHER"],
            "qualified_DoD": None, "qualified_DoV": None,
            "owner_accepted": None, "closure_credit": 0,
            "open_pr_overlap": [], "degree": 0, "blocker_candidates": 0,
            "dependent_candidates": 0, "outside_scope_references": [],
        }
        for ref in references(issue["body"], repo):
            if ref["target"] != key:
                edge_map[key, ref["target"], ref["kind"]] = {
                    "from": key, "to": ref["target"], "kind": ref["kind"],
                    "source_url": nodes[key]["url"], "verified": False,
                }
    for pr in prs:
        repo, number = pr["repo"], pr["number"]
        for ref in references(pr["body"], repo, pr=True):
            if ref["target"] in nodes:
                nodes[ref["target"]]["open_pr_overlap"].append({
                    "ref": identity(repo, number), "kind": ref["kind"],
                    "url": f"https://github.com/{repo}/pull/{number}",
                    "head_sha": pr.get("head_sha"), "verified_merged": False})
    links, dependents, blocked = defaultdict(set), defaultdict(set), defaultdict(set)
    for e in edge_map.values():
        a, b = e["from"], e["to"]
        if b not in nodes:
            nodes[a]["outside_scope_references"].append(b)
            continue
        links[a].add(b)
        links[b].add(a)
        if e["kind"] == "DECLARED_BLOCKER_CANDIDATE":
            blocked[a].add(b)
            dependents[b].add(a)
    for key, node in nodes.items():
        node["degree"] = len(links[key])
        node["blocker_candidates"] = len(blocked[key])
        node["dependent_candidates"] = len(dependents[key])
        node["outside_scope_references"] = sorted(set(node["outside_scope_references"]))
        node["open_pr_overlap"].sort(key=lambda x: (x["ref"], x["kind"]))
        d, v = node["DoD"]["progress"], node["DoV"]["progress"]
        node["near_finished_signal"] = bool(
            d and v and d["total"] >= 2 and v["total"] >= 1
            and d["remaining"] <= 1 and v["remaining"] <= 1)
        node["near_finished_grade"] = (
            "UNVERIFIED_CHECKBOX_SIGNAL" if node["near_finished_signal"] else None)
    def tier(x):
        return int(x["priority"][1]) if x["priority"] != "UNKNOWN" else 5
    def views(selected):
        rr = list(selected)
        return {
            "golden_oldest_first": [x["ref"] for x in sorted(
                rr, key=lambda x: (x["created_at"], x["ref"]))],
            "mycelium_newest_first": [x["ref"] for x in sorted(
                rr, key=lambda x: (x["created_at"], x["ref"]), reverse=True)],
            "graph_connected_first": [x["ref"] for x in sorted(
                rr, key=lambda x: (-x["dependent_candidates"], -x["degree"],
                                  x["created_at"], x["ref"]))],
            "owner_review_pressure": [x["ref"] for x in sorted(
                rr, key=lambda x: (tier(x), -x["dependent_candidates"],
                                  -len(x["open_pr_overlap"]),
                                  -int(x["near_finished_signal"]),
                                  x["created_at"], x["ref"]))],
        }
    per_repo = {}
    for repo in repos:
        selection = [x for x in nodes.values() if x["repo"] == repo]
        per_repo[repo] = {
            "count": len(selection),
            "priority_counts": dict(Counter(x["priority"] for x in selection)),
            "views": views(selection),
            "title_taxonomy": tt.summary([{"type": "Issue", "title_taxonomy": x["title_taxonomy"]}
                                         for x in selection]),
        }
    delta = None
    if previous is not None:
        require(previous.get("schema") == SCHEMA and
                previous.get("repositories") == repos, "unmatched previous cohort")
        older, current = set(previous["issues"]), set(nodes)
        delta = {
            "newly_seen_open": sorted(current - older),
            "absent_from_open_not_necessarily_closed": sorted(older - current),
            "persisting_open": len(current & older),
            "verified_causal_root_closure": None,
        }
    edges = sorted(edge_map.values(), key=lambda x: (x["from"], x["to"], x["kind"]))
    related = tt.associated_families(
        [{"key": k, "type": "Issue", "title_taxonomy": x["title_taxonomy"]}
         for k, x in nodes.items()],
        [{"source": e["from"], "target": e["to"], "kind": e["kind"]}
         for e in edges if e["to"] in nodes], max_hops=2)
    for issue_ref, candidates in related.items():
        nodes[issue_ref]["title_taxonomy"]["related_families"] = candidates
    return {
        "schema": SCHEMA, "observed_at": observed,
        "source_grade": "NON_ATOMIC_COMPLETE_API_PAGINATION",
        "repositories": repos, "source_heads": heads,
        "authority_transfer": False, "formal_credit_delta": 0,
        "merge_admission": "HOLD", "verified_causal_root_closure": None,
        "pca": "WITHHELD_NO_ADMISSIBLE_MEASURED_COHORT",
        "bradley_terry": "WITHHELD_NO_SAME_SLOT_OBSERVED_PAIR_TRIALS",
        "ranking_grade": "DETERMINISTIC_ADVISORY_HEURISTIC_NOT_GGMATH_INFERENCE",
        "metrics": {
            "open_issues": len(nodes), "open_prs": len(prs),
            "explicit_DoD": sum(x["DoD"]["progress"] is not None for x in nodes.values()),
            "explicit_DoV": sum(x["DoV"]["progress"] is not None for x in nodes.values()),
            "with_uncategorized_checklists": sum(
                x["unclassified_checklist"]["progress"] is not None for x in nodes.values()),
            "candidate_dependency_links_in_scope": sum(
                x["kind"] == "DECLARED_BLOCKER_CANDIDATE" and x["to"] in nodes for x in edges),
            "association_or_candidate_links": len(edges),
            "verified_DoD_steps": None, "verified_DoV_steps": None,
            "verified_root_closures": None,
        },
        "issues": dict(sorted(nodes.items())), "edges": edges, "views": views(nodes.values()),
        "title_taxonomy_total": tt.summary([{"type": "Issue", "title_taxonomy": x["title_taxonomy"]}
                                            for x in nodes.values()]),
        "by_repository": per_repo, "open_identity_delta": delta,
    }


def _get(path, token, opener):
    require(path.startswith("/repos/GBOGEB/"), "untrusted GitHub URL")
    req = Request("https://api.github.com" + path, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "missioncontrol-issue-burndown-readonly",
        **({"Authorization": "Bearer " + token} if token else {})})
    with opener(req, timeout=25) as response:
        return json.load(response)


def _pages(repo, resource, token, opener, max_pages):
    result = []
    for page in range(1, max_pages + 1):
        batch = _get(f"/repos/{repo}/{resource}?state=open&per_page=100&page={page}",
                     token, opener)
        require(isinstance(batch, list), "bad page payload")
        result.extend(batch)
        if len(batch) < 100:
            return result
    raise ValueError("pagination incomplete: max_pages exceeded")


def collect(repositories=DEFAULT_REPOS, *, token=None, opener=urlopen, max_pages=20):
    require(type(max_pages) is int and 1 <= max_pages <= 100, "invalid max_pages")
    require(bool(repositories) and len(set(repositories)) == len(repositories),
            "empty/duplicate repository census")
    heads, counts, issues, prs = {}, {}, [], []
    for repo in repositories:
        require(isinstance(repo, str) and bool(REPO.fullmatch(repo)), "bad repository")
        metadata = _get("/repos/" + repo, token, opener)
        commit = _get("/repos/" + repo + "/commits/" +
                      quote(metadata["default_branch"], safe=""), token, opener)
        heads[repo] = commit["sha"]
        items = _pages(repo, "issues", token, opener, max_pages)
        pulls = _pages(repo, "pulls", token, opener, max_pages)
        issue_items = [i for i in items if "pull_request" not in i]
        counts[repo] = {"issues": len(issue_items), "prs": len(pulls)}
        for i in issue_items:
            issues.append({
                "repo": repo, "number": i["number"], "state": i["state"],
                "title": i.get("title") or "", "body": i.get("body") or "",
                "created_at": i["created_at"], "updated_at": i["updated_at"],
                "labels": [x.get("name", "") for x in i.get("labels", [])],
            })
        for p in pulls:
            prs.append({
                "repo": repo, "number": p["number"], "state": p["state"],
                "body": p.get("body") or "", "head_sha": p.get("head", {}).get("sha")})
    return {
        "schema": CENSUS, "repositories": list(repositories),
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_heads": heads, "counts": counts,
        "issues": issues, "pull_requests": prs,
        "authority_transfer": False, "formal_credit_delta": 0,
    }


def csv_view(report):
    result = io.StringIO()
    columns = ("ref", "repo", "priority", "created_at", "dod_checked", "dod_total",
               "dov_checked", "dov_total", "near_finished", "association_degree",
               "candidate_dependents", "open_pr_count")
    writer = csv.DictWriter(result, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for n in report["issues"].values():
        d, v = n["DoD"]["progress"], n["DoV"]["progress"]
        writer.writerow({
            "ref": n["ref"], "repo": n["repo"], "priority": n["priority"],
            "created_at": n["created_at"], "dod_checked": d["checked"] if d else "",
            "dod_total": d["total"] if d else "",
            "dov_checked": v["checked"] if v else "",
            "dov_total": v["total"] if v else "",
            "near_finished": n["near_finished_signal"],
            "association_degree": n["degree"],
            "candidate_dependents": n["dependent_candidates"],
            "open_pr_count": len(n["open_pr_overlap"])})
    return result.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", help="private source census; never upload raw issue bodies")
    mode.add_argument("--github", action="store_true", help="read-only GitHub REST fetch")
    parser.add_argument("--repos", nargs="+", default=list(DEFAULT_REPOS))
    parser.add_argument("--previous", help="matched earlier derived projection")
    parser.add_argument("--out", required=True)
    parser.add_argument("--csv")
    args = parser.parse_args()
    c = (collect(args.repos, token=os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN"))
         if args.github else json.loads(Path(args.input).read_text(encoding="utf-8")))
    old = json.loads(Path(args.previous).read_text(encoding="utf-8")) if args.previous else None
    report = project(c, old)
    Path(args.out).write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                              encoding="utf-8")
    if args.csv:
        Path(args.csv).write_text(csv_view(report), encoding="utf-8")
    print(json.dumps(report["metrics"], sort_keys=True))


if __name__ == "__main__":
    main()
