"""One canonical GitHub pulse for the Burn-down Matrix dashboard.

Reads open PRs, recent merges and default-branch workflow health for each repo
in one pass, records each default branch's head SHA, and writes pulse.json:
a flat list of rows tagged by `kind` (meta, repo, pr, wf, day).

Usage: python burndown_pulse.py OUT_DIR
Needs `gh` signed in (unset GITHUB_TOKEN/GH_TOKEN if it returns 401).

Read-only toward GitHub: `gh()` refuses any call that is not a list/view or a GET
(see `assert_read_only`). The scheduled task "burndown-pulse-refresh" runs it every
30 minutes and uploads pulse.json to the dashboard; see README.md next to this file.
"""
import collections
import datetime as dt
import json
import os
import subprocess
import sys
import time

OWNER = "GBOGEB"
REPOS = ["pipeline-automation-hub", "cryoplant-project", "ABACUS"]
SHORT = {"pipeline-automation-hub": "PAH", "cryoplant-project": "cryoplant", "ABACUS": "ABACUS"}
BAD = {"FAILURE", "ERROR", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"}
PENDING = {"PENDING", "QUEUED", "IN_PROGRESS", "EXPECTED", "WAITING", "REQUESTED"}


# The only gh subcommands this script may run. Everything else is refused.
READ_ONLY = {("repo", "view"), ("pr", "list"), ("run", "list"), ("api",)}
FIELD_FLAGS = {"-f", "-F", "--field", "--raw-field", "--input"}

# Replaced by the offline tests with a fake gh runner.
run = subprocess.run


def assert_read_only(args):
    """Raise ValueError unless `gh *args` only reads from GitHub."""
    if not args or (tuple(args[:2]) not in READ_ONLY and tuple(args[:1]) not in READ_ONLY):
        raise ValueError(f"gh {' '.join(args[:2])} is not on the read-only list")
    if args[0] != "api":
        return
    method = None
    for i, a in enumerate(args):
        if a in ("-X", "--method") and i + 1 < len(args):
            method = args[i + 1].upper()
        elif a.startswith("--method="):
            method = a.split("=", 1)[1].upper()
    if len(args) > 1 and args[1] == "graphql":
        if any("mutation" in a for a in args if a.startswith("query=")):
            raise ValueError("gh api graphql: mutations are not allowed")
        return
    # `gh api` with fields and no method defaults to POST.
    if method not in (None, "GET") or (method is None and FIELD_FLAGS & set(args)):
        raise ValueError(f"gh api: only GET is allowed, got {method or 'POST'}")


def gh(*args):
    assert_read_only(args)
    env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "GH_TOKEN")}
    out = run(["gh", *args], capture_output=True, text=True, encoding="utf-8", env=env, check=True)
    return json.loads(out.stdout) if out.stdout.strip() else None


def gh_retry(*args, tries=4):
    for i in range(tries):
        try:
            return gh(*args)
        except subprocess.CalledProcessError as e:
            # GitHub's API returns transient 502/504s under load; back off and retry.
            if i == tries - 1:
                sys.stderr.write(e.stderr or "")
                raise
            time.sleep(5 * (i + 1))


def check_state(c):
    return (c.get("conclusion") or c.get("state") or c.get("status") or "").upper()


def red_kind(name):
    n = (name or "").lower()
    if "first-pass" in n:
        return "fpc"
    if "launcher" in n or "gogreen required" in n:
        return "launcher"
    return "other"


def parse(ts):
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def main(out_dir, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    rows = []
    for repo in REPOS:
        full = f"{OWNER}/{repo}"
        short = SHORT[repo]
        branch = gh_retry("repo", "view", full, "--json", "defaultBranchRef")["defaultBranchRef"]["name"]
        head = gh_retry("api", f"repos/{full}/commits/{branch}", "--jq", "{sha: .sha}")["sha"]

        prs = gh_retry("pr", "list", "-R", full, "--state", "open", "--limit", "200", "--json",
                 "number,title,isDraft,mergeStateStatus,baseRefName,headRefName,headRefOid,statusCheckRollup,updatedAt,createdAt")
        heads = {p["headRefName"]: p["number"] for p in prs}
        for p in prs:
            checks = p["statusCheckRollup"] or []
            reds = sorted({c.get("name") or c.get("context") for c in checks if check_state(c) in BAD})
            kinds = {red_kind(r) for r in reds}
            pending = sum(1 for c in checks if check_state(c) in PENDING)
            title = p["title"]
            hold = "DO NOT MERGE" in title.upper() and "UNLESS GREEN" not in title.upper()
            if hold:
                nxt = "Hold: title says do not merge"
            elif p["isDraft"]:
                nxt = "Owner marks ready"
            elif p["mergeStateStatus"] == "DIRTY":
                nxt = "Merge default branch, re-receipt"
            elif pending:
                nxt = "Wait for checks"
            elif "other" in kinds or "launcher" in kinds:
                nxt = "Fix failing checks"
            elif "fpc" in kinds:
                nxt = "Codex review on exact head"
            elif p["mergeStateStatus"] in ("CLEAN", "HAS_HOOKS"):
                nxt = "Merge-ready (squash)"
            else:
                nxt = "Check merge state"
            stacked = heads.get(p["baseRefName"])
            rows.append(dict(
                kind="pr", key=f"{short}#{p['number']}", repo=short, pr=p["number"], title=title[:100],
                draft=int(p["isDraft"]), merge_state=p["mergeStateStatus"],
                base=p["baseRefName"], stacked_on=f"{short}#{stacked}" if stacked else "",
                head_sha=p["headRefOid"][:8], checks=len(checks), reds=len(reds), pending=pending,
                fpc_red=int("fpc" in kinds), launcher_red=int("launcher" in kinds), other_red=int("other" in kinds),
                red_names="; ".join(reds)[:300], age_days=round((now - parse(p["createdAt"])).total_seconds() / 86400, 1),
                next_step=nxt))

        # One day per call: the rollup for a whole week times out GitHub's GraphQL API.
        merged = []
        for i in range(6, -1, -1):
            day = (now - dt.timedelta(days=i)).date().isoformat()
            merged += gh_retry("pr", "list", "-R", full, "--state", "merged", "--search", f"merged:{day}",
                               "--limit", "100", "--json", "number,mergedAt,statusCheckRollup")
        per_day = collections.Counter(m["mergedAt"][:10] for m in merged)
        merged_red = [m for m in merged if any(check_state(c) in BAD for c in m["statusCheckRollup"] or [])]
        merged_fpc_red = [m for m in merged if any(check_state(c) in BAD and red_kind(c.get("name")) == "fpc"
                                                   for c in m["statusCheckRollup"] or [])]
        for i in range(6, -1, -1):
            day = (now - dt.timedelta(days=i)).date().isoformat()
            rows.append(dict(kind="day", key=f"{short}|{day}", repo=short, day=day, merged=per_day.get(day, 0)))

        runs = gh_retry("run", "list", "-R", full, "--branch", branch, "--limit", "300", "--json",
                  "workflowName,conclusion,status,createdAt,headSha,event,databaseId")
        by_wf = collections.defaultdict(list)
        for r in runs:
            if r["status"] == "completed" and r["conclusion"] not in ("skipped", "cancelled"):
                by_wf[r["workflowName"]].append(r)
        red_wf = 0
        for name, rs in by_wf.items():
            rs.sort(key=lambda r: r["createdAt"], reverse=True)
            if check_state(rs[0]) not in BAD:
                continue
            red_wf += 1
            streak = 0
            for r in rs:
                if check_state(r) not in BAD:
                    break
                streak += 1
            capped = streak == len(rs)
            rows.append(dict(
                kind="wf", key=f"{short}|{name}", repo=short, workflow=name, event=rs[0]["event"],
                last_at=rs[0]["createdAt"], streak=streak, streak_note="or more" if capped else "",
                first_red_at=rs[streak - 1]["createdAt"], head_sha=rs[0]["headSha"][:8],
                run_url=f"https://github.com/{full}/actions/runs/{rs[0]['databaseId']}"))

        mine = [r for r in rows if r.get("repo") == short and r["kind"] == "pr"]
        rows.append(dict(
            kind="repo", key=short, repo=short, branch=branch, head_sha=head[:8], open_prs=len(mine),
            open_drafts=sum(r["draft"] for r in mine), merge_ready=sum(r["next_step"].startswith("Merge-ready") for r in mine),
            fpc_red=sum(r["fpc_red"] for r in mine), dirty=sum(r["merge_state"] == "DIRTY" for r in mine),
            merged_7d=len(merged), merged_24h=sum(parse(m["mergedAt"]) > now - dt.timedelta(hours=24) for m in merged),
            merged_with_red_7d=len(merged_red), merged_fpc_red_7d=len(merged_fpc_red), red_workflows=red_wf))

    rows.insert(0, dict(kind="meta", key="pulse", pulse_at=now.isoformat(timespec="seconds"),
                        heads="; ".join(f"{r['repo']}@{r['head_sha']}" for r in rows if r["kind"] == "repo")))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "pulse.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rows, f, indent=0)
    summary = {"path": path, "rows": len(rows), "pulse_at": rows[0]["pulse_at"], "heads": rows[0]["heads"]}
    print(json.dumps(summary))
    return summary


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
