#!/usr/bin/env python3
"""FOCUS5 H08 "effective protection and rejected RED canary": receipts and live verification.

Proof class GITHUB_REJECTED_RED_MERGE, as in gogreen/required_gate/governed_landing_probe.py:
a merge of a PR whose head is red on a *required* check was attempted against the default
branch and GitHub refused it (HTTP 405). A receipt alone is never PASS: focus5_pulse re-verifies
every receipt live with verify_receipt(), on the exact current configuration:

  * the default branch has a pull_request rule and a required_status_checks rule;
  * every ruleset carrying those rules is active, targets the default branch, has no bypass
    actors, and the reading user can never bypass it;
  * the receipt's failing check is one of the required contexts, and its ruleset is still in force;
  * the canary PR targets the default branch, was never merged, still has the receipt's head SHA,
    and that head's latest run of the failing check concluded failure;
  * the receipt records HTTP 405 for that head with a response digest.

Anything missing is UNKNOWN, never PASS. Private repositories are rejected: their PR numbers and
SHAs must not enter this public file (their H08 stays UNKNOWN in the public pulse).

Producing a receipt attempts a real merge, so `attempt` checks every precondition first, refuses
unless all hold, and requires --confirm-merge-attempt. It is an owner action (or explicitly
owner-authorised); the pulse and `verify` only read.

  python tools/h08_canary.py verify --repo GBOGEB/yaml-grammar
  python tools/h08_canary.py attempt --repo GBOGEB/yaml-grammar --pr 9 \
      --check "Offline fixture integrity (211 productions) (3.12)" --confirm-merge-attempt
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = "data/FOCUS5_H08_CANARY_RECEIPTS.json"
SCHEMA = "jade.focus5.h08_canary_receipts.v1"
PROOF = "GITHUB_REJECTED_RED_MERGE"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
# 405 also means "still a draft" or "not mergeable" (conflict); only a protection refusal counts.
PROTECTION_405 = re.compile(r"status check|rule violation", re.I)
# a refusal while checks are still queued/pending proves gating, not that a RED head is rejected
PENDING_405 = re.compile(r"queued|expected|pending|in progress|waiting", re.I)

_pb = importlib.util.spec_from_file_location("private_boundary", ROOT / "tools" / "private_boundary.py")
PB = importlib.util.module_from_spec(_pb)
_pb.loader.exec_module(PB)


def gh(path: str) -> object:
    out = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def validate_receipts(doc: dict, private=None) -> dict[str, list[dict]]:
    """Repo -> receipts. Raises ValueError on a malformed file or a private repository."""
    if doc.get("schema") != SCHEMA:
        raise ValueError("unknown receipts schema")
    private = set(PB.private_repos() if private is None else private)
    out: dict[str, list[dict]] = {}
    for r in doc.get("receipts", []):
        repo = r.get("repo", "")
        if repo.count("/") != 1:
            raise ValueError(f"{repo!r}: expected owner/name")
        if repo in private:
            raise ValueError(f"{repo}: private repository receipts must not be stored in the public hub")
        if r.get("proof_class") != PROOF:
            raise ValueError(f"{repo}: proof_class must be {PROOF}")
        if not isinstance(r.get("pr_number"), int) or not HEX40.match(str(r.get("head_sha", ""))):
            raise ValueError(f"{repo}: pr_number int and 40-hex head_sha required")
        if not str(r.get("failing_check") or "").strip() or not isinstance(r.get("ruleset_id"), int):
            raise ValueError(f"{repo}: failing_check and ruleset_id required")
        a = r.get("attempt") or {}
        if a.get("http_status") != 405 or not HEX64.match(str(a.get("response_sha256", ""))) or not a.get("at"):
            raise ValueError(f"{repo}: attempt needs http_status 405, response_sha256 and at")
        if not PROTECTION_405.search(str(a.get("message", ""))):
            raise ValueError(f"{repo}: 405 message does not name a status check or rule violation")
        if PENDING_405.search(str(a.get("message", ""))):
            raise ValueError(f"{repo}: 405 was for pending checks, not a rejected RED head")
        out.setdefault(repo, []).append(r)
    for rs in out.values():
        rs.sort(key=lambda r: r["attempt"]["at"])
    return out


def load_receipts(root: Path = ROOT) -> dict[str, list[dict]]:
    path = root / RECEIPTS
    return validate_receipts(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else {}


def effective_protection(repo: str, branch: str, lookup=gh) -> tuple[bool, str, set[int], set[str]]:
    """(ok, detail, ruleset ids carrying the rules, required check contexts)."""
    rules = lookup(f"repos/{repo}/rules/branches/{branch}")
    types = {r["type"] for r in rules}
    if "pull_request" not in types:
        return False, "no pull request rule", set(), set()
    if "required_status_checks" not in types:
        return False, "no required status checks rule", set(), set()
    contexts = {c["context"] for r in rules if r["type"] == "required_status_checks"
                for c in (r.get("parameters") or {}).get("required_status_checks", [])}
    ids = {r["ruleset_id"] for r in rules if r["type"] in ("pull_request", "required_status_checks")
           and r.get("ruleset_id") is not None}
    if not ids:
        return False, "pull request / status rules not from a readable ruleset", ids, contexts
    for rid in sorted(ids):
        rs = lookup(f"repos/{repo}/rulesets/{rid}")
        include = ((rs.get("conditions") or {}).get("ref_name") or {}).get("include") or []
        if rs.get("enforcement") != "active" or rs.get("target") != "branch":
            return False, f"ruleset {rid} not active on branches", ids, contexts
        if "~DEFAULT_BRANCH" not in include and f"refs/heads/{branch}" not in include:
            return False, f"ruleset {rid} does not target the default branch", ids, contexts
        if rs.get("bypass_actors") != [] or rs.get("current_user_can_bypass") != "never":
            return False, f"ruleset {rid} has bypass actors or the reader can bypass", ids, contexts
    return True, f"rulesets {sorted(ids)} active, no bypass; {len(contexts)} required checks", ids, contexts


def latest_check(repo: str, sha: str, name: str, lookup=gh) -> dict | None:
    runs = lookup(f"repos/{repo}/commits/{sha}/check-runs?per_page=100")["check_runs"]
    done = [r for r in runs if r.get("name") == name and r.get("status") == "completed"]
    return max(done, key=lambda r: (r.get("completed_at") or "", r.get("id") or 0)) if done else None


def verify_receipt(repo: str, branch: str, receipt: dict, lookup=gh) -> tuple[str, str | None, str]:
    """(PASS|UNKNOWN, evidence url, reason) for one receipt on the current configuration."""
    ok, detail, ids, contexts = effective_protection(repo, branch, lookup)
    if not ok:
        return "UNKNOWN", None, f"protection not effective: {detail}"
    check, pr_n = receipt["failing_check"], receipt["pr_number"]
    if check not in contexts:
        return "UNKNOWN", None, f"canary check {check!r} is not a required context now"
    if receipt["ruleset_id"] not in ids:
        return "UNKNOWN", None, f"receipt ruleset {receipt['ruleset_id']} is no longer in force"
    pr = lookup(f"repos/{repo}/pulls/{pr_n}")
    if pr.get("merged_at") or pr.get("merged"):
        return "UNKNOWN", None, f"canary PR #{pr_n} was merged"
    if (pr.get("base") or {}).get("ref") != branch or (pr.get("head") or {}).get("sha") != receipt["head_sha"]:
        return "UNKNOWN", None, f"canary PR #{pr_n} base or head changed since the receipt"
    run = latest_check(repo, receipt["head_sha"], check, lookup)
    if not run or run.get("conclusion") != "failure":
        return "UNKNOWN", None, f"latest {check!r} on the canary head is not a failure"
    return ("PASS", pr.get("html_url"),
            f"rejected RED canary #{pr_n} ({check} failed; merge refused 405 at {receipt['attempt']['at']}); {detail}")


def evaluate(repo: str, branch: str, receipts: list[dict], lookup=gh) -> tuple[str, str | None, str]:
    """Newest receipt that still verifies wins; otherwise the newest receipt's reason."""
    last = ("UNKNOWN", None, "no rejected RED canary receipt")
    for r in reversed(receipts):
        res = verify_receipt(repo, branch, r, lookup)
        if res[0] == "PASS":
            return res
        if last[2] == "no rejected RED canary receipt":
            last = res
    return last


def attempt(repo: str, pr_n: int, check: str, lookup=gh, merge=None) -> dict:
    """Check every precondition, then try to merge the red canary and record GitHub's refusal."""
    meta = lookup(f"repos/{repo}")
    branch = meta["default_branch"]
    if meta.get("private"):
        raise SystemExit("private repository: receipts are not stored in the public hub")
    ok, detail, ids, contexts = effective_protection(repo, branch, lookup)
    if not ok:
        raise SystemExit(f"REFUSED before attempting: protection not effective ({detail})")
    if check not in contexts:
        raise SystemExit(f"REFUSED: {check!r} is not a required check (required: {sorted(contexts)})")
    pr = lookup(f"repos/{repo}/pulls/{pr_n}")
    head = pr["head"]["sha"]
    if pr.get("state") != "open" or pr["base"]["ref"] != branch or pr.get("draft"):
        raise SystemExit("REFUSED: canary PR must be open, ready for review (not draft) and target the default branch")
    runs = lookup(f"repos/{repo}/commits/{head}/check-runs?per_page=100")["check_runs"]
    if any(r.get("name") == check and r.get("status") != "completed" for r in runs):
        raise SystemExit(f"REFUSED: a run of {check!r} on {head[:12]} is still queued or in progress; wait for it")
    run = latest_check(repo, head, check, lookup)
    if not run or run.get("conclusion") != "failure":
        raise SystemExit(f"REFUSED: latest {check!r} on {head[:12]} is not a completed failure")
    status, body = (merge or _merge)(repo, pr_n, head)
    if status != 405:
        raise SystemExit(f"ALARM: merge attempt returned HTTP {status}, not 405 - protection did NOT reject: {body[:300]}")
    if not PROTECTION_405.search(_message(body)) or PENDING_405.search(_message(body)):
        raise SystemExit(f"NOT A CANARY: 405 was not a RED-check refusal ({_message(body)[:200]}); no receipt written")
    rule_id = min(ids)
    return {"repo": repo, "pr_number": pr_n, "head_sha": head, "base_branch": branch, "failing_check": check,
            "failing_check_run": run.get("html_url"), "ruleset_id": rule_id, "proof_class": PROOF,
            "attempt": {"at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "http_status": status, "message": _message(body)[:300],
                        "response_sha256": hashlib.sha256(body.encode()).hexdigest()}}


def _message(body: str) -> str:
    try:
        return str(json.loads(body).get("message", ""))
    except (ValueError, AttributeError):
        return body


def _merge(repo: str, pr_n: int, head: str) -> tuple[int, str]:
    p = subprocess.run(["gh", "api", "--include", "-X", "PUT", f"repos/{repo}/pulls/{pr_n}/merge",
                        "-f", f"sha={head}"], capture_output=True, text=True)
    m = re.match(r"HTTP/\S+ (\d{3})", p.stdout)
    body = p.stdout.split("\r\n\r\n", 1)[-1] if "\r\n\r\n" in p.stdout else p.stdout.split("\n\n", 1)[-1]
    return (int(m.group(1)) if m else -1), body.strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="read-only: evaluate H08 for a repo from the committed receipts")
    v.add_argument("--repo", required=True)
    a = sub.add_parser("attempt", help="OWNER ACTION: attempt to merge a red canary and record the refusal")
    a.add_argument("--repo", required=True)
    a.add_argument("--pr", type=int, required=True)
    a.add_argument("--check", required=True, help="a required check that is red on the canary head")
    a.add_argument("--confirm-merge-attempt", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "verify":
        branch = gh(f"repos/{args.repo}")["default_branch"]
        out = dict(zip(("status", "evidence", "reason"), evaluate(args.repo, branch, load_receipts().get(args.repo, []))))
        ok, detail, _ids, contexts = effective_protection(args.repo, branch)
        out["protection_ready_for_canary"] = ok
        out["protection"] = detail
        out["required_checks"] = sorted(contexts)
        print(json.dumps(out, indent=1))
        return 0
    if not args.confirm_merge_attempt:
        raise SystemExit("attempt makes a real merge call; re-run with --confirm-merge-attempt")
    receipt = attempt(args.repo, args.pr, args.check)
    path = ROOT / RECEIPTS
    doc = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema": SCHEMA, "receipts": []}
    doc["receipts"].append(receipt)
    validate_receipts(doc)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"receipt recorded: {receipt['repo']} #{receipt['pr_number']} 405 {receipt['attempt']['message'][:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
