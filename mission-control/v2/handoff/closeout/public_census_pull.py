#!/usr/bin/env python3
"""GET-only public GitHub CENSUS adapter; no issue/BD writes or worker dispatch."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PUBLIC = (
    ("GBOGEB/ABACUS", "main"),
    ("GBOGEB/CODEX", "main"),
    ("GBOGEB/pipeline-automation-hub", "master"),
    ("GBOGEB/gg_MATH", "main"),
)
SHA40 = re.compile(r"^[a-f0-9]{40}$")
API = "https://api.github.com"


def get_json(path):
    if not path.startswith("/") or "://" in path or "//" in path:
        raise ValueError("unsafe GitHub API path")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "missioncontrol-census-readonly",
    }
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    request = Request(API + path, headers=headers, method="GET")
    with urlopen(request, timeout=20) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("invalid API response")
    return value


def search(fetch, repo, kind, page=1, per_page=100):
    query = urlencode({"q": f"repo:{repo} is:open is:{kind}",
                       "per_page": per_page, "page": page})
    result = fetch("/search/issues?" + query)
    count = result.get("total_count")
    items = result.get("items")
    if (type(count) is not int or count < 0 or not isinstance(items, list)
            or result.get("incomplete_results") is not False):
        raise ValueError("incomplete GitHub search result")
    return count, items


def collect(fetch=get_json, at=None):
    at = at or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("timezone required")
    rows = []
    age_totals = [0, 0, 0, 0]
    for repo, default in PUBLIC:
        source = fetch("/repos/" + repo)
        if (source.get("full_name") != repo or source.get("private") is not False
                or source.get("default_branch") != default):
            raise ValueError("private, stale or unrecognised repository")
        branch = fetch("/repos/" + repo + "/branches/" + default)
        sha = branch.get("commit", {}).get("sha")
        if not isinstance(sha, str) or not SHA40.fullmatch(sha):
            raise ValueError("missing exact source SHA")
        count, items = search(fetch, repo, "issue")
        if count > 1000:
            raise ValueError("GitHub search population exceeds verifiable 1000 cap")
        for page in range(2, (count-1)//100+2):
            new_count, page_items = search(fetch, repo, "issue", page=page)
            if new_count != count:
                raise ValueError("pagination changed issue denominator")
            items.extend(page_items)
        if len(items) != count:
            raise ValueError("incomplete issue page, UNKNOWN not zero")
        ids = set()
        bins = [0, 0, 0, 0]
        for issue in items:
            n = issue.get("number")
            if "pull_request" in issue or type(n) is not int or n in ids:
                raise ValueError("PR/duplicate in ordinary issue population")
            ids.add(n)
            stamp = issue.get("created_at")
            if not isinstance(stamp, str):
                raise ValueError("missing issue timestamp")
            dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            delta = (at - dt).total_seconds() / 86400
            if delta < 0:
                raise ValueError("future issue time")
            bins[0 if delta < 7 else 1 if delta < 14 else 2 if delta < 30 else 3] += 1
        pr_count, _ = search(fetch, repo, "pr", per_page=1)
        age_totals = [x+y for x,y in zip(age_totals, bins)]
        rows.append({
            "repo": repo, "branch": default, "head_sha": sha,
            "ordinary_open_issues": count, "open_prs": pr_count,
            "age_bins_0_6_7_13_14_29_30plus": bins,
            "protected_rest": branch.get("protected") if type(branch.get("protected")) is bool else None,
        })
    issues_total = sum(x["ordinary_open_issues"] for x in rows)
    if sum(age_totals) != issues_total:
        raise ValueError("age denominator inconsistent")
    return {
        "schema": "missioncontrol.public_census_get_only.v1",
        "observed_utc": at.isoformat().replace("+00:00", "Z"),
        "snapshot_atomic": False, "scope": "FOUR_PUBLIC_CORE_REPOSITORIES",
        "repositories": rows, "ordinary_open_issues": issues_total,
        "open_prs": sum(x["open_prs"] for x in rows),
        "age_bins": age_totals, "restricted_child_sources": "WITHHELD",
        "causal_bd_roots_open": None, "causal_bd_roots_closed": None,
        "comparable_main_coverage": None, "pr_diff_coverage": None,
        "remote_crew_run_count": None, "accepted_rex": None,
        "merge_admission": "HOLD", "security_waiver": False,
        "authority_transfer": False,
    }


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--out", type=Path, required=True)
    opts = args.parse_args()
    try:
        census = collect()
        opts.out.parent.mkdir(parents=True, exist_ok=True)
        opts.out.write_text(json.dumps(census, sort_keys=True, indent=2)+"\n",encoding="utf-8", newline="\n")
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
        print("CENSUS_PULL_HOLD: incomplete source ("+type(exc).__name__+")",file=sys.stderr)
        return 2
    print(json.dumps({"repos":len(census["repositories"]),
                      "issues":census["ordinary_open_issues"],
                      "prs":census["open_prs"],"admission":"HOLD"},sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
