"""Issue burn-down pulse: open issues, their PRs, and opened/closed per day.

Companion to burndown_pulse.py (same rows-by-`kind` file, same refresh
pattern). The open-issue population comes from the canonical PAH register,
`retrieve_issue_register` in mission-control/federation-atlas/central/recensus.py,
loaded from origin/master of the local pipeline-automation-hub clone so the
owner's function is imported, not copied. This script adds only the issue <-> PR
links, which no other tool owns.

Rows: meta, repo, issue, pr, edge (issue-PR link), day (opened/closed/open at end of day).

Usage: python issue_pulse.py OUT_DIR [--pah CLONE] [--ref REF]
Needs `gh` signed in (unset GITHUB_TOKEN/GH_TOKEN if it returns 401) and a
pipeline-automation-hub clone. The clone is, in order: --pah, the ISSUE_PULSE_PAH
environment variable, or the clone this script sits in. The register is read
from REF (default origin/master), so `git -C <clone> fetch origin master` first.

Read-only toward GitHub: every call goes through burndown_pulse.gh(), which
refuses anything that is not a list/view or a GET.
"""
import argparse
import collections
import datetime as dt
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from burndown_pulse import BAD, OWNER, PENDING, check_state, gh_retry, parse  # noqa: E402

REPOS = ["pipeline-automation-hub", "cryoplant-project", "ABACUS", "CODEX"]
SHORT = {"pipeline-automation-hub": "PAH", "cryoplant-project": "cryoplant", "ABACUS": "ABACUS", "CODEX": "CODEX"}
# tools/workstation/dashboards/pulse/issue_pulse.py -> the clone root is four levels up.
HERE_CLONE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 4))
DEFAULT_REF = "origin/master"
REGISTER = "mission-control/federation-atlas/central"
DAYS = 14
STALE_DAYS = 30
# The canonical typed reference parser (owner per AGENTS.md: issue triway burndown); imported, not copied.
TRIWAY = os.path.join(HERE_CLONE, "mission-control", "qps-triage-ultra", "issue-expedition", "triway_burndown.py")
_spec = importlib.util.spec_from_file_location("triway_burndown", TRIWAY)
triway = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(triway)

ISSUE_QUERY = """
query($owner:String!,$name:String!,$cursor:String){repository(owner:$owner,name:$name){
 issues(states:OPEN,first:50,after:$cursor){pageInfo{hasNextPage endCursor} nodes{number
  assignees(first:3){nodes{login}}
  closedByPullRequestsReferences(first:10,includeClosedPrs:true){nodes{number state isDraft repository{nameWithOwner}}}
  timelineItems(itemTypes:[CROSS_REFERENCED_EVENT,CONNECTED_EVENT],last:40){nodes{__typename
   ...on CrossReferencedEvent{willCloseTarget source{__typename ...on PullRequest{number state isDraft repository{nameWithOwner}}}}
   ...on ConnectedEvent{subject{__typename ...on PullRequest{number state isDraft repository{nameWithOwner}}}}}}}}}}
"""


def pah_clone(arg=None):
    """The PAH clone to read the register from: --pah, then ISSUE_PULSE_PAH, then this clone."""
    return arg or os.environ.get("ISSUE_PULSE_PAH") or HERE_CLONE


def load_register(clone, ref=DEFAULT_REF):
    """Import retrieve_issue_register/exact_count from the PAH register at `ref` of `clone`."""
    tmp = tempfile.mkdtemp(prefix="issue_register_")
    for name in ("recensus.py", "code_health.py"):
        src = subprocess.run(["git", "-C", clone, "show", f"{ref}:{REGISTER}/{name}"],
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
        with open(os.path.join(tmp, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(src)
    sys.path.insert(0, tmp)
    try:
        spec = importlib.util.spec_from_file_location("recensus", os.path.join(tmp, "recensus.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(tmp)
        shutil.rmtree(tmp, ignore_errors=True)
    sha = subprocess.run(["git", "-C", clone, "rev-parse", "--short=8", ref],
                         capture_output=True, text=True, check=True).stdout.strip()
    return mod, sha


def gh_get(path):
    """Getter for the register: read-only `gh api` GET of the same REST path."""
    return gh_retry("api", path.lstrip("/"))


def search_all(query):
    items, page = [], 1
    while True:
        r = gh_retry("api", "-X", "GET", "search/issues", "-f", f"q={query}", "-F", "per_page=100", "-F", f"page={page}")
        items += r["items"]
        if len(items) >= r["total_count"] or not r["items"] or page >= 10:
            return items
        page += 1


def graphql_issues(repo):
    out, cursor = [], None
    while True:
        args = ["api", "graphql", "-f", f"query={ISSUE_QUERY}", "-F", f"owner={OWNER}", "-F", f"name={repo}"]
        if cursor:
            args += ["-F", f"cursor={cursor}"]
        page = gh_retry(*args)["data"]["repository"]["issues"]
        out += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return out
        cursor = page["pageInfo"]["endCursor"]


def pr_light(p):
    checks = p.get("statusCheckRollup") or []
    reds = sum(1 for c in checks if check_state(c) in BAD)
    pending = sum(1 for c in checks if check_state(c) in PENDING)
    return "draft" if p["isDraft"] else "red" if reds else "pending" if pending else "green"


def main(out_dir, clone=None, ref=DEFAULT_REF, now=None, register=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    since = (now - dt.timedelta(days=DAYS)).date()
    reg, reg_sha = register or load_register(pah_clone(clone), ref)
    rows = []
    for repo in REPOS:
        full = f"{OWNER}/{repo}"
        short = SHORT[repo]
        expected = reg.exact_count(gh_get, full, "issue", "open")
        issues = reg.retrieve_issue_register(gh_get, full, "open", expected)
        links = {i["number"]: i for i in graphql_issues(repo)}

        prs = gh_retry("pr", "list", "-R", full, "--state", "open", "--limit", "200", "--json",
                       "number,title,body,isDraft,statusCheckRollup,closingIssuesReferences,createdAt,url")
        open_nums = {i["number"] for i in issues}
        edges = {}  # (issue, pr) -> kind
        pr_state = {}
        for p in prs:
            pr_state[p["number"]] = ("open", pr_light(p))
            for ref in p.get("closingIssuesReferences") or []:
                if ref.get("repository", {}).get("nameWithOwner", full) == full:
                    edges[(ref["number"], p["number"])] = "closes"
            text = f"{p['title']}\n{p.get('body') or ''}"
            # Closure claims first, so a closure is not shadowed by an association of the same issue.
            refs = sorted(triway.references(text, full, pr=True), key=lambda r: r["kind"] != "PR_CLOSURE_CLAIM")
            for ref in refs:
                if ref["repo"] != full:
                    continue
                if ref["kind"] == "PR_CLOSURE_CLAIM":
                    edges.setdefault((ref["number"], p["number"]), "closes")
                elif ref["number"] in open_nums:
                    edges.setdefault((ref["number"], p["number"]), "mentions")
        for num, node in links.items():
            for src in node["closedByPullRequestsReferences"]["nodes"]:
                if src["repository"]["nameWithOwner"] == full:
                    edges[(num, src["number"])] = "closes"
                    pr_state.setdefault(src["number"], ("merged" if src["state"] == "MERGED" else src["state"].lower(),
                                                          "draft" if src.get("isDraft") else ""))
            for ev in node["timelineItems"]["nodes"]:
                src = ev.get("source") or ev.get("subject") or {}
                if src.get("__typename") != "PullRequest" or src["repository"]["nameWithOwner"] != full:
                    continue
                kind = "closes" if ev.get("willCloseTarget") or ev["__typename"] == "ConnectedEvent" else "mentions"
                key = (num, src["number"])
                if edges.get(key) != "closes":
                    edges[key] = kind
                if src["number"] not in pr_state:
                    pr_state[src["number"]] = ("merged" if src["state"] == "MERGED" else src["state"].lower(),
                                               "draft" if src.get("isDraft") else "")

        # Only a closing link (Closes #n, linked in the sidebar) says a PR resolves an
        # issue. A mention is context: kept as an edge only while the PR is open, and
        # counted for merged PRs, since census PRs mention dozens of issues each.
        by_issue = collections.defaultdict(list)
        for (inum, pnum), kind in edges.items():
            if inum not in open_nums:
                continue
            state, light = pr_state.get(pnum, ("unknown", ""))
            by_issue[inum].append((pnum, kind, state, light))
            if kind == "closes" or state == "open":
                rows.append(dict(kind="edge", key=f"{short}#{inum}>{pnum}", repo=short, issue=f"{short}#{inum}",
                                 pr=f"{short}#{pnum}", link=kind, pr_state=state, pr_light=light))

        for i in issues:
            n = i["number"]
            states = sorted(by_issue.get(n, []))
            closing = [s for s in states if s[1] == "closes"]
            closing_open = [s for s in closing if s[2] == "open"]
            closing_merged = [s for s in closing if s[2] == "merged"]
            related_open = [s for s in states if s[1] == "mentions" and s[2] == "open"]
            mentioned_merged = sum(1 for s in states if s[1] == "mentions" and s[2] == "merged")
            labels = i["labels"]
            idle = (now - parse(i["updated_at_utc"])).total_seconds() / 86400
            first = lambda light: next(s[0] for s in closing_open if s[3] == light)  # noqa: E731
            if "parked-intent" in labels:
                nxt, link_state = "Parked: wake check owns it", "parked"
            elif any(s[3] == "red" for s in closing_open):
                nxt, link_state = f"Fix checks on PR #{first('red')}", "pr-red"
            elif any(s[3] == "pending" for s in closing_open):
                nxt, link_state = "Wait for PR checks", "pr-pending"
            elif any(s[3] == "green" for s in closing_open):
                nxt, link_state = f"Review and merge PR #{first('green')}", "pr-green"
            elif closing_open:
                nxt, link_state = "Owner marks PR ready", "pr-draft"
            elif closing_merged:
                nxt, link_state = f"Close or confirm: PR #{closing_merged[0][0]} merged", "pr-merged"
            elif related_open:
                nxt, link_state = f"Link PR #{related_open[0][0]} with 'Closes #{n}', or split", "pr-related"
            elif idle > STALE_DAYS:
                nxt, link_state = "Stale: triage or close", "stale"
            else:
                nxt, link_state = "Needs a PR or a lane", "no-pr"
            rows.append(dict(
                kind="issue", key=f"{short}#{n}", repo=short, number=n, title=(i["title"] or "")[:110],
                labels=", ".join(labels)[:120], assignees=", ".join(a["login"] for a in links.get(n, {}).get("assignees", {}).get("nodes", [])),
                age_days=round((now - parse(i["created_at_utc"])).total_seconds() / 86400, 1), idle_days=round(idle, 1),
                closing_prs="; ".join(f"#{p} {st}{' ' + lt if lt else ''}" for p, _, st, lt in closing),
                related_prs="; ".join(f"#{p} {lt}" for p, _, _, lt in related_open),
                mentioned_by_merged=mentioned_merged,
                link_state=link_state, next_step=nxt, url=i["url"]))

        for p in prs:
            closes = sorted({inum for (inum, pn), k in edges.items() if pn == p["number"] and k == "closes"})
            related = sorted({inum for (inum, pn), k in edges.items() if pn == p["number"] and k == "mentions"} - set(closes))
            link = "closes" if closes else "related" if related else "orphan"
            rows.append(dict(kind="pr", key=f"{short}#{p['number']}", repo=short, pr=p["number"], title=p["title"][:100],
                             light=pr_light(p), closes=", ".join(f"#{n}" for n in closes),
                             related=", ".join(f"#{n}" for n in related), link=link, url=p["url"]))

        created = search_all(f"repo:{full} is:issue created:>={since.isoformat()}")
        closed = search_all(f"repo:{full} is:issue closed:>={since.isoformat()}")
        c_day = collections.Counter(x["created_at"][:10] for x in created)
        x_day = collections.Counter(x["closed_at"][:10] for x in closed if x.get("closed_at"))
        open_eod = len(issues)
        series = []
        for k in range(0, DAYS + 1):
            day = (now - dt.timedelta(days=k)).date().isoformat()
            series.append(dict(kind="day", key=f"{short}|{day}", repo=short, day=day,
                               opened=c_day.get(day, 0), closed=x_day.get(day, 0), open_eod=open_eod))
            open_eod = open_eod - c_day.get(day, 0) + x_day.get(day, 0)
        rows += reversed(series)

        mine = [r for r in rows if r.get("repo") == short and r["kind"] == "issue"]
        my_prs = [r for r in rows if r.get("repo") == short and r["kind"] == "pr"]
        rows.append(dict(
            kind="repo", key=short, repo=short, open_issues=len(mine),
            opened_14d=sum(c_day.values()), closed_14d=sum(x_day.values()),
            net_14d=sum(c_day.values()) - sum(x_day.values()),
            with_closing_pr=sum(r["link_state"] in ("pr-red", "pr-pending", "pr-green", "pr-draft") for r in mine),
            closing_pr_merged=sum(r["link_state"] == "pr-merged" for r in mine),
            related_pr_only=sum(r["link_state"] == "pr-related" for r in mine),
            no_pr=sum(r["link_state"] == "no-pr" for r in mine), stale=sum(r["link_state"] == "stale" for r in mine),
            parked=sum(r["link_state"] == "parked" for r in mine),
            open_prs=len(my_prs), prs_closing=sum(r["link"] == "closes" for r in my_prs),
            prs_related=sum(r["link"] == "related" for r in my_prs), orphan_prs=sum(r["link"] == "orphan" for r in my_prs),
            closing_link_pct=round(100 * sum(r["link"] == "closes" for r in my_prs) / len(my_prs), 1) if my_prs else None))

    rows.insert(0, dict(kind="meta", key="issue_pulse", pulse_at=now.isoformat(timespec="seconds"),
                        register=f"pipeline-automation-hub@{reg_sha}:{REGISTER}/recensus.py",
                        repos=", ".join(SHORT[r] for r in REPOS)))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "issue_pulse.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rows, f, indent=0)
    counts = collections.Counter(r["kind"] for r in rows)
    summary = {"path": path, "rows": len(rows), "pulse_at": rows[0]["pulse_at"], "counts": counts,
               "register": rows[0]["register"]}
    print(json.dumps(summary))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out_dir", nargs="?", default=".")
    ap.add_argument("--pah", help="pipeline-automation-hub clone (default: ISSUE_PULSE_PAH, then this clone)")
    ap.add_argument("--ref", default=DEFAULT_REF, help="git ref to read the register from")
    a = ap.parse_args()
    main(a.out_dir, a.pah, a.ref)
