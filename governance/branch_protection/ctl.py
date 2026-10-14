#!/usr/bin/env python3
"""Fail-closed, admin-operated default-branch ruleset controller.

No token in repository. Default is offline plan, never write.
Plan -> audited prerequisites -> explicit per-repository owner --apply -> readback.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys

POLICY = pathlib.Path(__file__).with_name("policy.json")
PASS = {"success"}  # skipped/neutral is NOT accepted as evidence of executed work.


class Hold(RuntimeError):
    pass


def load_policy(path=POLICY):
    p = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if p.get("schema") != "missioncontrol.branch_protection.v1":
        raise Hold("Unknown policy schema")
    entries = p.get("repositories", [])
    names = [x["repo"] for x in entries]
    if len(names) != len(set(names)) or not entries:
        raise Hold("Duplicate or missing repository policy entries")
    c = p["common"]
    if c["required_approving_review_count"] < 1 or c["bypass_actors"] != []:
        raise Hold("Policy cannot remove independent review or grant bypass")
    if not all(c[k] is True for k in (
        "dismiss_stale_reviews_on_push",
        "require_last_push_approval",
        "required_review_thread_resolution",
        "forbid_force_push",
        "forbid_deletion",
    )):
        raise Hold("Common controls were weakened")
    return p


def select(p, repo):
    matches = [x for x in p["repositories"] if x["repo"] == repo]
    if len(matches) != 1:
        raise Hold("Repository is not explicitly authorized by the policy")
    return matches[0]


def render(p, entry, stage):
    if stage not in ("core", "full"):
        raise Hold("Unsupported stage")
    c = p["common"]
    pull = {
        "allowed_merge_methods": c["allowed_merge_methods"],
        "dismiss_stale_reviews_on_push": c["dismiss_stale_reviews_on_push"],
        "require_code_owner_review": c["require_code_owner_review"],
        "require_last_push_approval": c["require_last_push_approval"],
        "required_approving_review_count": c["required_approving_review_count"],
        "required_review_thread_resolution": c["required_review_thread_resolution"],
    }
    rules = [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {"type": "pull_request", "parameters": pull},
    ]
    if stage == "full":
        checks = entry.get("required_checks", [])
        if not checks or len(checks) != len(set(checks)):
            raise Hold("Full stage has no unambiguous required check list; HOLD")
        rules.append({
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy":
                    c["strict_required_status_checks_policy"],
                "required_status_checks": [{"context": x} for x in checks],
            },
        })
    return {
        "name": entry["ruleset_name"],
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {
            "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []},
        },
        "rules": rules,
    }


def core_projection(value):
    """Compare API rules semantically; metadata is not part of the write contract."""
    return {
        "name": value.get("name"),
        "target": value.get("target"),
        "enforcement": value.get("enforcement"),
        "bypass_actors": value.get("bypass_actors", "NOT_READABLE"),
        "conditions": value.get("conditions"),
        "rules": sorted(
            [{"type": x.get("type"),
              **({"parameters": x["parameters"]} if "parameters" in x else {})}
             for x in value.get("rules", [])],
            key=lambda x: x["type"],
        ),
    }


def gh(endpoint, method="GET", payload=None):
    command = [
        "gh", "api", "--method", method,
        "-H", "Accept: application/vnd.github+json",
        "-H", "X-GitHub-Api-Version: 2022-11-28",
        endpoint,
    ]
    if payload is not None:
        command += ["--input", "-"]
    try:
        output = subprocess.run(
            command, input=json.dumps(payload) if payload is not None else None,
            text=True, capture_output=True, check=True, timeout=35,
        )
        return json.loads(output.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired,
            json.JSONDecodeError) as exc:
        raise Hold("GitHub API unavailable or denied: " + str(exc)) from exc


def snapshot(entry):
    repo = entry["repo"]
    metadata = gh("repos/" + repo)
    if metadata.get("archived") or metadata.get("default_branch") != entry["default_branch"]:
        raise Hold("Repository archived or default branch differs from policy")
    branch = gh("repos/" + repo + "/branches/" + entry["default_branch"])
    rows = gh("repos/" + repo + "/rulesets?per_page=100")
    if not isinstance(rows, list) or len(rows) == 100:
        raise Hold("Ruleset inventory incomplete")
    matches = [x for x in rows if x.get("name") == entry["ruleset_name"]
               and x.get("source_type") == "Repository"]
    if len(matches) > 1:
        raise Hold("Duplicate named rulesets")
    existing = None
    if matches:
        rid = matches[0]["id"]
        if entry.get("existing_ruleset_id") and rid != entry["existing_ruleset_id"]:
            raise Hold("Ruleset ID changed since baseline; manual reconciliation required")
        existing = gh("repos/" + repo + "/rulesets/" + str(rid))
    elif entry.get("existing_ruleset_id"):
        raise Hold("Expected ABACUS ruleset missing: do not create replacement")
    return metadata, branch, existing


def preflight_full(entry, pr_number):
    if not pr_number:
        raise Hold("Full stage requires --probe-pr for a live exact-head PR")
    repo = entry["repo"]
    pr = gh("repos/" + repo + "/pulls/" + str(pr_number))
    if pr.get("base", {}).get("ref") != entry["default_branch"]:
        raise Hold("Probe PR must target the specified default branch")
    head = pr.get("head", {}).get("sha")
    if not head or len(head) != 40:
        raise Hold("Probe PR exact head unknown")
    runs = gh("repos/" + repo + "/commits/" + head + "/check-runs?per_page=100")
    status = gh("repos/" + repo + "/commits/" + head + "/status")
    checks = runs.get("check_runs", [])
    if runs.get("total_count", 0) > len(checks):
        raise Hold("Check-run results are paginated; HOLD")
    statuses = status.get("statuses", [])
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)

    def fresh(stamp):
        if not stamp:
            return False
        return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")) >= cutoff

    for context in entry["required_checks"]:
        associated = [x for x in checks if x.get("name") == context]
        created = [x for x in statuses if x.get("context") == context]
        if not associated and not created:
            raise Hold("Exact PR head missing candidate context: " + context)
        if len(associated) > 1:
            raise Hold("Ambiguous duplicate check-run context: " + context)
        if associated and not all(x.get("status") == "completed"
                                  and x.get("conclusion") in PASS
                                  and fresh(x.get("completed_at"))
                                  for x in associated):
            raise Hold("Required check did not execute and pass: " + context)
        if created and not (created[0].get("state") == "success"
                            and fresh(created[0].get("updated_at"))):
            raise Hold("Required commit status is not recent successful: " + context)
    return {"pr_number": pr_number, "head_sha": head, "contexts": entry["required_checks"]}


def verify_expected(actual, desired):
    return core_projection(actual) == core_projection(desired)


def candidate_write(existing, desired, core, entry, stage):
    if existing is None:
        return "CREATE"
    if verify_expected(existing, desired):
        return "UNCHANGED"
    if (entry.get("existing_ruleset_id") == existing.get("id")
            and not existing.get("rules") and stage == "core"
            and existing.get("bypass_actors") == []
            and existing.get("target") == "branch"):
        return "REPAIR_EMPTY_EXISTING"
    if stage == "full" and verify_expected(existing, core):
        return "PROMOTE_VERIFIED_CORE"
    raise Hold("Ruleset drift, unknown overrides, or unsafe stage downgrade; HOLD")


def operate(p, entry, args):
    desired = render(p, entry, args.stage)
    if args.mode == "plan":
        print(json.dumps({"authority": "POLICY_PROPOSAL_NOT_LIVE",
                          "repository": entry["repo"], "stage": args.stage,
                          "payload": desired}, indent=2))
        return

    meta, branch, existing = snapshot(entry)
    core = render(p, entry, "core")
    disposition = candidate_write(existing, desired, core, entry, args.stage)
    before = {
        "repository": entry["repo"],
        "branch": entry["default_branch"],
        "head_sha": branch.get("commit", {}).get("sha"),
        "branch_protected": branch.get("protected"),
        "ruleset_id": existing.get("id") if existing else None,
        "decision": disposition,
    }
    if args.mode == "audit":
        before["result"] = ("PROTECTED_AS_CONFIGURED" if branch.get("protected")
                            and disposition == "UNCHANGED" else "NOT_YET_ENFORCED_AS_POLICY")
        print(json.dumps(before, indent=2))
        return

    if args.confirm_repo != entry["repo"]:
        raise Hold("Apply requires --confirm-repo equal to the exact target")
    if not args.reviewer_ready or not args.publishers_migrated:
        raise Hold("Owner must attest independent reviewer and PR-safe publishers")
    if not meta.get("permissions", {}).get("admin", False):
        raise Hold("Authenticated actor has no demonstrated repo admin permission")
    if args.stage == "full":
        before["probe"] = preflight_full(entry, args.probe_pr)
    if disposition == "UNCHANGED":
        before["result"] = "NO_WRITE_ALREADY_AS_CONFIGURED"
        print(json.dumps(before, indent=2))
        return
    endpoint = "repos/" + entry["repo"] + "/rulesets"
    if existing:
        rid = existing["id"]
        # Fresh re-read to reduce stale write risk. GitHub has no conditional ruleset PUT.
        latest = gh(endpoint + "/" + str(rid))
        if core_projection(latest) != core_projection(existing):
            raise Hold("Concurrent ruleset update detected; HOLD")
        written = gh(endpoint + "/" + str(rid), "PUT", desired)
    else:
        current = gh(endpoint)
        if any(x.get("name") == desired["name"] for x in current):
            raise Hold("Ruleset appeared concurrently; HOLD")
        written = gh(endpoint, "POST", desired)
    rid = written.get("id")
    if not rid:
        raise Hold("GitHub did not return created/updated ruleset ID")
    live = gh(endpoint + "/" + str(rid))
    branch_after = gh("repos/" + entry["repo"] + "/branches/" + entry["default_branch"])
    result = {
        "repository": entry["repo"], "branch": entry["default_branch"],
        "ruleset_id": rid, "head_sha": branch_after.get("commit", {}).get("sha"),
        "ruleset_exact_match": verify_expected(live, desired),
        "protected": branch_after.get("protected"),
        "bypass_actors": live.get("bypass_actors", "UNKNOWN"),
        "type": "POST_WRITE_READBACK",
    }
    print(json.dumps(result, indent=2))
    if not result["ruleset_exact_match"] or result["protected"] is not True:
        raise Hold("Write returned but effective admission not verified: HOLD")


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--repo", required=True, help="Exact allowlisted owner/repository")
    a.add_argument("--stage", choices=("core", "full"), default="core")
    a.add_argument("--mode", choices=("plan", "audit", "apply"), default="plan")
    a.add_argument("--confirm-repo", default="")
    a.add_argument("--reviewer-ready", action="store_true")
    a.add_argument("--publishers-migrated", action="store_true")
    a.add_argument("--probe-pr", type=int)
    a.add_argument("--policy", type=pathlib.Path, default=POLICY)
    args = a.parse_args(argv)
    try:
        p = load_policy(args.policy)
        operate(p, select(p, args.repo), args)
    except Hold as error:
        print(json.dumps({"result": "HOLD", "reason": str(error),
                          "repository": args.repo, "stage": args.stage}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
