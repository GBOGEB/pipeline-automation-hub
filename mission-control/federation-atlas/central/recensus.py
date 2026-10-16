#!/usr/bin/env python3
"""Read-only live CODE-HEALTH recensus into a DERIVED receipt, never SSOT.

The frozen N register remains versioned and unmodified. This tool reads native
GitHub REST endpoints with optional GITHUB_TOKEN, fails closed on incomplete
search populations, and emits a next observation without launching workers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from .code_health import REGISTRY, SHA, read_json, validate
except ImportError:
    from code_health import REGISTRY, SHA, read_json, validate

API_ROOT = "https://api.github.com"
REPOSITORY = re.compile(r"^GBOGEB/[A-Za-z0-9_.-]+$")
MAX_REPOS = 12


def github_get(path, *, token=None):
    """Allow only approved GitHub read-only REST paths, no arbitrary URLs."""
    if not (path.startswith("/repos/GBOGEB/") or
            path.startswith("/search/issues?")):
        raise ValueError("non-GitHub or mutating endpoint")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "missioncontrol-code-health-census",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(API_ROOT + path, headers=headers, method="GET")
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def exact_count(getter, repo, kind, state):
    if kind not in ("issue", "pr") or state not in ("open", "closed"):
        raise ValueError("unsupported census population")
    query = f"repo:{repo} is:{kind} is:{state}"
    result = getter("/search/issues?" + urlencode({"q": query, "per_page": 1}))
    if not isinstance(result, dict):
        raise ValueError("invalid GitHub search result")
    count = result.get("total_count")
    if result.get("incomplete_results") is True or (
        type(count) is not int or count < 0
    ):
        raise ValueError("incomplete or invalid GitHub issue census")
    return count



def retrieve_issue_register(getter, repo, state, expected):
    """Enumerate only genuine GitHub Issues with exact bounded pagination.

    These records are operational work surfaces; never treat an issue close as
    an admitted BD causal root. Incomplete/paged/churning registers fail.
    """
    if not REPOSITORY.fullmatch(repo) or state not in ("open", "closed"):
        raise ValueError("invalid issue-register scope")
    if type(expected) is not int or expected < 0 or expected > 1000:
        raise ValueError("unbounded native issue population")
    rows, observed = [], set()
    pages = max(1, (expected + 99) // 100)
    for page in range(1, pages + 1):
        query = urlencode({
            "q": f"repo:{repo} is:issue is:{state}",
            "per_page": 100,
            "page": page,
        })
        result = getter("/search/issues?" + query)
        if (
            not isinstance(result, dict) or
            result.get("incomplete_results") is True or
            result.get("total_count") != expected or
            not isinstance(result.get("items"), list)
        ):
            raise ValueError("incomplete or changing issue-register page")
        for issue in result["items"]:
            if not isinstance(issue, dict):
                raise ValueError("invalid issue record")
            number = issue.get("number")
            if (
                type(number) is not int or number < 1 or
                number in observed or
                issue.get("state") != state or
                issue.get("html_url") !=
                f"https://github.com/{repo}/issues/{number}" or
                "pull_request" in issue
            ):
                raise ValueError("wrong or duplicate issue identity")
            observed.add(number)
            raw_labels = issue.get("labels", [])
            if not isinstance(raw_labels, list):
                raise ValueError("invalid issue label population")
            labels = [label.get("name") for label in raw_labels]
            if any(not isinstance(label, str) for label in labels):
                raise ValueError("untyped issue labels")
            rows.append({
                "repo": repo,
                "number": number,
                "title": issue.get("title"),
                "url": issue["html_url"],
                "state": state,
                "created_at_utc": issue.get("created_at"),
                "updated_at_utc": issue.get("updated_at"),
                "closed_at_utc": issue.get("closed_at"),
                "labels": labels,
                "bd_root_id": None,
                "accepted_root_closure": None,
            })
    if len(rows) != expected:
        raise ValueError("issue-register coverage incomplete")
    return rows


def collect(snapshot, *, getter=github_get, observed_at_utc=None,
            include_pr_heads=True, include_issue_register=False):
    """Recensus bounded source cohort, preserve historical root UNKNOWN."""
    validate(snapshot)
    repos = snapshot["census"]["repositories"]
    if len(repos) > MAX_REPOS:
        raise ValueError("too many native repository lookups")
    if observed_at_utc is None:
        observed_at_utc = datetime.now(timezone.utc).isoformat()
    try:
        stamp = datetime.fromisoformat(observed_at_utc.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise ValueError("UTC observation timestamp required") from None
    if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError("source census requires UTC observation timestamp")

    observations = []
    for source in repos:
        repo = source["id"]
        if not REPOSITORY.fullmatch(repo):
            raise ValueError("unsupported repository identity")
        branch = source["default_branch"]
        details = getter(f"/repos/{repo}/commits/{branch}")
        if not isinstance(details, dict):
            raise ValueError("invalid GitHub commit metadata")
        sha = details.get("sha")
        if not isinstance(sha, str) or SHA.fullmatch(sha) is None:
            raise ValueError("missing exact native default head")
        counts = {
            "open_issues": exact_count(getter, repo, "issue", "open"),
            "closed_issues": exact_count(getter, repo, "issue", "closed"),
            "open_prs": exact_count(getter, repo, "pr", "open"),
            "closed_prs": exact_count(getter, repo, "pr", "closed"),
        }
        baseline = {
            "open_issues": source["issue_register"]["open"],
            "closed_issues": source["issue_register"]["closed"],
            "open_prs": source["pull_request_register"]["open"],
            "closed_prs": source["pull_request_register"]["closed"],
        }
        observations.append({
            "repo": repo,
            "branch": branch,
            "head_sha": sha,
            "baseline_source_sha": source["source_sha"],
            "head_changed": sha != source["source_sha"],
            "counts": counts,
            "prior_counts": baseline,
            "record_deltas": {key: counts[key]-baseline[key] for key in counts},
            "record_deltas_are_root_closures": False,
            "source": f"https://github.com/{repo}/tree/{sha}",
        })
    issue_records = None
    if include_issue_register:
        issue_records = []
        for row in observations:
            for state in ("open", "closed"):
                issue_records.extend(
                    retrieve_issue_register(
                        getter, row["repo"], state,
                        row["counts"][state + "_issues"],
                    )
                )
    totals = {
        key: sum(row["counts"][key] for row in observations)
        for key in ("open_issues", "closed_issues", "open_prs", "closed_prs")
    }
    prs = []
    if include_pr_heads:
        for item in snapshot["work"]:
            if item["ref_type"] != "pr":
                continue
            result = getter(f"/repos/{item['repo']}/pulls/{item['number']}")
            if not isinstance(result, dict):
                raise ValueError("invalid native pull request")
            head = result.get("head")
            if (result.get("number") != item["number"] or
                not isinstance(head, dict) or
                not isinstance(head.get("sha"), str) or
                SHA.fullmatch(head["sha"]) is None or
                not isinstance(head.get("ref"), str) or
                not head["ref"]):
                raise ValueError("PR head identity unavailable")
            prs.append({
                "work_id": item["id"],
                "repo": item["repo"],
                "pr_number": item["number"],
                "head_sha": head["sha"],
                "branch": head["ref"],
                "base_branch": (result.get("base") or {}).get("ref"),
                "state": result.get("state"),
                "draft": result.get("draft"),
                "merged": result.get("merged"),
                "url": item["url"],
                "runner_launch_inferred": False,
            })
    return {
        "schema": "missioncontrol.code_health.recensus.v1",
        "observed_at_utc": observed_at_utc,
        "source_schema": snapshot["schema"],
        "source_register_sha256": hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "source_baseline_date": snapshot["census_date"],
        "scope": snapshot["census"]["scope"],
        "snapshot_class": "DERIVED_GITHUB_REST_OBSERVATION_NOT_SSOT",
        "repositories": observations,
        "totals": totals,
        "scoped_pr_heads": prs,
        "scoped_pr_heads_observed": len(prs),
        "issue_register_records": issue_records,
        "issue_register_observed": (
            len(issue_records) if issue_records is not None else None
        ),
        "issue_register_full_population_verified": (
            len(issue_records) == totals["open_issues"] + totals["closed_issues"]
            if issue_records is not None else None
        ),
        "unobserved_other_repos": None,
        "native_queue_p95_seconds": None,
        "native_runner_slots": None,
        "bd_canonical_open": None,
        "bd_canonical_closed": None,
        "crew_auth_launches": None,
        "accepted_rex": None,
        "prediction_scored": False,
        "independent_gate_vector": None,
        "admission": "HOLD",
        "authority_transfer": False,
        "mutation_permitted": False,
        "merge_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=REGISTRY)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--skip-pr-heads", action="store_true")
    parser.add_argument(
        "--full-issue-register", action="store_true",
        help="paginate all issue record metadata; closed issues are not roots",
    )
    options = parser.parse_args(argv)
    snapshot = read_json(options.source)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    data = collect(
        snapshot,
        getter=lambda path: github_get(path, token=token),
        include_pr_heads=not options.skip_pr_heads,
        include_issue_register=options.full_issue_register,
    )
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "observed_at_utc": data["observed_at_utc"],
        "repos": len(data["repositories"]),
        "pr_heads": len(data["scoped_pr_heads"]),
        "issue_register_observed": data["issue_register_observed"],
        "issues_open": data["totals"]["open_issues"],
        "admission": "HOLD",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
