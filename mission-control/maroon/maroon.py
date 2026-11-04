#!/usr/bin/env python3
"""CODE MAROON runner: open security alerts -> deduplicated roots -> fix list and disjoint lanes.

CODE_MAROON (SUPERSTITCH_TAXONOMY_v1.json) classifies review and security debt with separate source
receipts, manifestation-to-root deduplication and closed / deferred / outstanding dispositions. This
runner reads GitHub's own alert APIs (Dependabot, code scanning, secret scanning) per repository and:

- keeps every alert as a manifestation, with its source and state;
- groups manifestations into roots (one fix each): a package in one repository's ecosystem, a rule of
  one scanner in one repository, or a secret type in one repository;
- groups roots into lanes that touch disjoint files: one repository and one source family each, so
  separate workers never edit the same manifest or workflow;
- writes a full receipt (private: names packages, rules and paths) and a public projection (counts
  only).

It closes no finding and has no merge authority. Coverage gaps (scanning not enabled, or not readable
with the caller's token) are recorded as such, never as zero.

    python maroon.py fetch --owner GBOGEB --out <dir>         # raw alerts, one file
    python maroon.py build --raw <dir>/raw.json --out <dir>   # receipt, fix list, lanes, public projection
    python maroon.py diff --old <a>/MAROON_RECEIPT.json --new <b>/MAROON_RECEIPT.json --out <dir>  # what moved
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "code_maroon.receipt.v1"
PUBLIC_SCHEMA = "code_maroon.public.v1"
DELTA_SCHEMA = "code_maroon.delta.v1"
RANK = {"critical": 6, "high": 5, "medium": 4, "low": 3, "error": 2, "warning": 1, "note": 0}
SOURCES = {
    # source -> (API path, states to read, state -> disposition)
    "dependabot": ("dependabot/alerts", ("open", "fixed", "dismissed", "auto_dismissed"),
                   {"open": "outstanding", "fixed": "closed", "dismissed": "deferred", "auto_dismissed": "deferred"}),
    "code_scanning": ("code-scanning/alerts", ("open", "fixed", "dismissed"),
                      {"open": "outstanding", "fixed": "closed", "dismissed": "deferred"}),
    "secret_scanning": ("secret-scanning/alerts", ("open", "resolved"),
                        {"open": "outstanding", "resolved": "closed"}),
    # Review findings left on closed PRs. Not an alert API: review_threads.py fetches them into their own
    # raw file (`build --review`), for named repositories only; others are recorded as not_in_scope.
    "review_threads": (None, ("open", "resolved"), {"open": "outstanding", "resolved": "closed"}),
}


def run_gh(args: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


def coverage_of(error: str) -> str:
    """Why a source could not be read: scanning switched off, or not readable with this token."""
    return "not_enabled" if ("not enabled" in error or "disabled" in error) else "not_readable"


def fetch(owner: str, gh=run_gh) -> dict:
    """Raw alerts per repository and source, for every state SOURCES names."""
    code, out, err = gh(["repo", "list", owner, "--limit", "1000", "--no-archived", "--source",
                         "--json", "nameWithOwner,visibility"])
    if code:
        raise RuntimeError("gh repo list failed: " + err.strip()[:300])
    raw = {"owner": owner, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "repos": {}}
    for repo in sorted(json.loads(out), key=lambda r: r["nameWithOwner"]):
        name = repo["nameWithOwner"]
        entry = {"visibility": repo["visibility"].lower(), "sources": {}}
        for source, (path, states, _) in SOURCES.items():
            if path is None:
                continue  # read by its own fetcher
            got = {"alerts": []}
            for state in states:
                code, out, err = gh(["api", "--paginate", "--slurp", f"repos/{name}/{path}?state={state}&per_page=100"])
                if code:
                    got = {"coverage": coverage_of(err), "error": (err.strip().splitlines() or ["error"])[-1][:200]}
                    break
                got["alerts"] += [a for page in json.loads(out or "[]") for a in (page if isinstance(page, list) else [page])]
            if "error" not in got:
                got["coverage"] = "ok"
            entry["sources"][source] = got
        raw["repos"][name] = entry
    return raw


def package_name(ecosystem: str, name: str) -> str:
    """One spelling per package: pip names compare as PEP 503 normalizes them (Pillow == pillow)."""
    return re.sub(r"[-_.]+", "-", name).lower() if ecosystem == "pip" else name


def manifestation(repo: str, source: str, a: dict) -> dict:
    """One alert, reduced to what roots, lanes and dispositions need."""
    disposition = SOURCES[source][2].get(a.get("state"), "outstanding")
    if source == "dependabot":
        adv, vuln, dep = a["security_advisory"], a.get("security_vulnerability") or {}, a["dependency"]
        patched = (vuln.get("first_patched_version") or {}).get("identifier")
        eco = dep["package"]["ecosystem"]
        return {"repo": repo, "source": source, "number": a["number"], "disposition": disposition,
                "severity": adv["severity"], "family": eco, "subject": package_name(eco, dep["package"]["name"]),
                "path": dep.get("manifest_path"), "advisory": adv["ghsa_id"], "patched": patched}
    if source == "code_scanning":
        rule = a["rule"]
        loc = (a.get("most_recent_instance") or {}).get("location") or {}
        return {"repo": repo, "source": source, "number": a["number"], "disposition": disposition,
                "severity": rule.get("security_severity_level") or rule.get("severity") or "note",
                "family": a["tool"]["name"], "subject": rule["id"], "path": loc.get("path"), "advisory": None, "patched": None}
    if source == "review_threads":
        # One root per theme in a repository: Copilot and Codex flagging the same defect is one fix.
        # `advisory` carries the PR, so a root lists the PRs its threads came from. A thread on a PR that
        # closed without merging is about a change that never landed: set aside, not post-merge debt.
        if disposition == "outstanding" and a.get("pr_merged") is False:
            disposition = "deferred"
        return {"repo": repo, "source": source, "number": a["number"], "disposition": disposition,
                "severity": a["severity"], "family": a["theme"], "subject": a["theme"], "path": a.get("path"),
                "advisory": f"#{a['pr']}", "patched": None}
    if a.get("state") == "resolved" and a.get("resolution") != "revoked":
        disposition = "deferred"  # false positive, won't fix, used in tests: set aside, not closed
    return {"repo": repo, "source": source, "number": a["number"], "disposition": disposition, "severity": "high",
            "family": "secret", "subject": a.get("secret_type_display_name") or a.get("secret_type"),
            "path": None, "advisory": None, "patched": None}


def version_key(v: str):
    return [int(p) if p.isdigit() else p for p in v.replace("-", ".").split(".")]


def roots_of(manifestations: list[dict]) -> list[dict]:
    """Deduplicate manifestations into roots; a root's severity is its worst outstanding manifestation."""
    groups: dict[tuple, list[dict]] = collections.defaultdict(list)
    for m in manifestations:
        groups[(m["repo"], m["source"], m["family"], m["subject"])].append(m)
    roots = []
    for (repo, source, family, subject), ms in groups.items():
        open_ms = [m for m in ms if m["disposition"] == "outstanding"]
        counts = collections.Counter(m["disposition"] for m in ms)
        patched = sorted({m["patched"] for m in open_ms if m["patched"]}, key=version_key)
        root = {"id": f"{repo}|{source}|{family}|{subject}", "repo": repo, "source": source, "family": family,
                "subject": subject,
                "severity": max((m["severity"] for m in open_ms), key=lambda s: RANK.get(s, -1)) if open_ms else None,
                "outstanding": counts["outstanding"], "closed": counts["closed"], "deferred": counts["deferred"],
                "paths": sorted({m["path"] for m in open_ms if m["path"]}),
                "advisories": sorted({m["advisory"] for m in open_ms if m["advisory"]}),
                "alerts": sorted(m["number"] for m in open_ms)}
        if source == "dependabot" and open_ms:
            root["fix"] = (f"upgrade {subject} to >= {patched[-1]}" if patched
                           else f"no patched {subject} release yet: remove, replace or defer with a reason")
        elif source == "code_scanning" and open_ms:
            root["fix"] = f"fix or dismiss with a reason: {family} {subject} at {len(root['paths'])} path(s)"
        elif source == "secret_scanning" and open_ms:
            root["fix"] = "revoke and rotate the secret, then resolve as revoked"
        elif source == "review_threads" and open_ms:
            root["fix"] = (f"one follow-up PR: deep-read {len(open_ms)} unresolved {subject} finding(s) from "
                           f"{' '.join(root['advisories'])} on the default branch, fix failing-before then passing-after, "
                           "reply on each thread")
        roots.append(root)
    return sorted(roots, key=lambda r: (-RANK.get(r["severity"], -1), -r["outstanding"], r["id"]))


def lanes_of(roots: list[dict]) -> list[dict]:
    """Disjoint lanes: one repository and one source family each, outstanding roots only.

    Dependabot lanes are per ecosystem (one lockfile family), code-scanning lanes per tool, so two
    lanes never edit the same manifest. Code-scanning lanes can share source files with each other in
    the same repository; ``shared_paths`` names any overlap so a worker can sequence them."""
    groups: dict[tuple, list[dict]] = collections.defaultdict(list)
    for r in roots:
        if r["outstanding"]:
            groups[(r["repo"], r["source"], r["family"])].append(r)
    lanes = []
    for (repo, source, family), rs in groups.items():
        prefix = {"dependabot": "deps", "code_scanning": "code", "secret_scanning": "secrets",
                  "review_threads": "review"}[source]
        lanes.append({"id": re.sub(r"[^a-z0-9:._-]+", "-", f"{repo.split('/')[-1]}:{prefix}-{family}".lower()), "repo": repo, "source": source,
                      "family": family, "severity": rs[0]["severity"], "roots": [r["id"] for r in rs],
                      "outstanding": sum(r["outstanding"] for r in rs),
                      "paths": sorted({p for r in rs for p in r["paths"]})})
    by_repo = collections.defaultdict(list)
    for lane in lanes:
        if lane["source"] in ("code_scanning", "review_threads"):
            by_repo[lane["repo"]].append(lane)
    for group in by_repo.values():
        for lane in group:
            others = {p for o in group if o is not lane for p in o["paths"]}
            lane["shared_paths"] = sorted(set(lane["paths"]) & others)
    return sorted(lanes, key=lambda l: (-RANK.get(l["severity"], -1), -l["outstanding"], l["id"]))


def apply_review_overrides(review: dict | None, overrides: dict | None) -> dict | None:
    """Copy of the review read with deep-read corrections applied: `{thread id: {"theme": ...}}`.

    A deep read can show that the heuristic theme is wrong (a wave-claim "alias" is not a file-path
    alias). The correction must reach the roots and lanes, or the fix list sends work to the wrong root."""
    if not review or not overrides:
        return review
    review = json.loads(json.dumps(review))
    for entry in review.get("repos", {}).values():
        for a in entry.get("alerts", []):
            theme = (overrides.get(str(a["number"])) or {}).get("theme")
            if theme:
                a["theme"] = theme
    return review


def review_scope(review: dict | None) -> dict:
    """Per repository: the PRs the review read sampled. Lets `diff` tell an eviction from a fix."""
    return {repo: {"prs": sorted(p["number"] for p in entry.get("prs", [])), "window": entry.get("window"),
                   "head_sha": entry.get("head_sha")}
            for repo, entry in (review or {}).get("repos", {}).items() if "prs" in entry}


def build(raw: dict, review: dict | None = None, overrides: dict | None = None) -> dict:
    """Receipt from raw alerts and, optionally, raw review threads (review_threads.py fetch).

    Every repository gets a coverage entry for every source: a repository outside the review read is
    `not_in_scope`, and one only in the review read is `absent` for the alert sources."""
    manifestations, coverage = [], {}
    review = apply_review_overrides(review, overrides)
    review_repos = (review or {}).get("repos", {})
    entries = {repo: dict(entry["sources"], visibility=entry["visibility"]) for repo, entry in raw["repos"].items()}
    for repo in review_repos:
        entries.setdefault(repo, {"visibility": "unknown"})
    for repo, entry in entries.items():
        coverage[repo] = {"visibility": entry["visibility"]}
        for source in SOURCES:
            if source == "review_threads":
                got = review_repos.get(repo, {"coverage": "not_in_scope"})
            else:
                got = entry.get(source, {"coverage": "absent"})
            coverage[repo][source] = got["coverage"]
            manifestations += [manifestation(repo, source, a) for a in got.get("alerts", [])]
    roots = roots_of(manifestations)
    thread_prs = {(m["repo"], m["number"]): int(m["advisory"][1:]) for m in manifestations if m["source"] == "review_threads"}
    for r in roots:
        if r["source"] == "review_threads":
            r["alert_prs"] = {str(n): thread_prs[(r["repo"], n)] for n in r["alerts"]}
    totals = collections.Counter()
    for m in manifestations:
        totals[(m["source"], m["disposition"])] += 1
    fetched_at = raw["fetched_at"] if raw["repos"] or not review else review["fetched_at"]  # a review-only read
    receipt = {
        "schema": SCHEMA, "programme": "CODE_MAROON", "owner": raw["owner"], "fetched_at": fetched_at,
        "closes_findings": False, "merge_authority": False,
        "totals": {s: {d: totals[(s, d)] for d in ("outstanding", "closed", "deferred")} for s in SOURCES},
        "roots_outstanding": sum(1 for r in roots if r["outstanding"]),
        "coverage": coverage, "roots": roots, "lanes": lanes_of(roots),
    }
    if review:
        receipt["review_scope"] = review_scope(review)
    return receipt


def public_projection(receipt: dict) -> dict:
    """Counts only: no package, rule, advisory or path, so it can be committed to a public repository."""
    repos = {}
    for repo, cov in receipt["coverage"].items():
        rs = [r for r in receipt["roots"] if r["repo"] == repo]
        row = {"visibility": cov["visibility"]}
        for source in SOURCES:
            src = [r for r in rs if r["source"] == source]
            row[source] = {"coverage": cov[source],
                           "roots_outstanding_by_severity": dict(collections.Counter(r["severity"] for r in src if r["outstanding"])),
                           "manifestations": {d: sum(r[d] for r in src) for d in ("outstanding", "closed", "deferred")}}
        row["lanes"] = sum(1 for l in receipt["lanes"] if l["repo"] == repo)
        repos[repo] = row
    return {"schema": PUBLIC_SCHEMA, "programme": "CODE_MAROON", "owner": receipt["owner"],
            "fetched_at": receipt["fetched_at"], "closes_findings": False, "merge_authority": False,
            "totals": receipt["totals"], "roots_outstanding": receipt["roots_outstanding"],
            "lanes": len(receipt["lanes"]), "repos": repos,
            "detail": "Roots, fix list and lanes are kept in a private repository; this file holds counts only."}


def write_outputs(receipt: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    dump = lambda o: json.dumps(o, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    (out / "MAROON_RECEIPT.json").write_text(dump(receipt), encoding="utf-8", newline="\n")
    (out / "MAROON_PUBLIC.json").write_text(dump(public_projection(receipt)), encoding="utf-8", newline="\n")
    with open(out / "MAROON_FIXLIST.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rank", "severity", "repo", "source", "family", "subject", "outstanding", "closed", "deferred",
                    "fix", "advisories", "paths"])
        for i, r in enumerate([r for r in receipt["roots"] if r["outstanding"]], 1):
            w.writerow([i, r["severity"], r["repo"], r["source"], r["family"], r["subject"], r["outstanding"],
                        r["closed"], r["deferred"], r.get("fix", ""), " ".join(r["advisories"]), " ".join(r["paths"])])
    lines = ["# CODE MAROON lanes", "",
             f"Read {receipt['fetched_at']} for {receipt['owner']}. {receipt['roots_outstanding']} outstanding roots in "
             f"{len(receipt['lanes'])} lanes. Each lane is one repository and one source family; Dependabot lanes "
             "never share a manifest. Work lanes top-down; this file closes nothing.", "",
             "| # | Lane | Worst | Roots | Alerts | Shared paths |", "|---|---|---|---|---|---|"]
    for i, l in enumerate(receipt["lanes"], 1):
        lines.append(f"| {i} | `{l['id']}` | {l['severity']} | {len(l['roots'])} | {l['outstanding']} | "
                     f"{len(l.get('shared_paths', []))} |")
    (out / "MAROON_LANES.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def diff(old: dict, new: dict) -> dict:
    """What moved between two receipts: roots and alerts that left or joined the outstanding set.

    An alert leaves when GitHub marks it fixed (for example after a merged PR lands the fix on the
    default branch), dismissed or resolved, or when its repository drops out of the read. Coverage
    changes are listed so a source that became unreadable is not mistaken for a fix.

    Review threads are read from a moving window of recent PRs. A thread whose PR is no longer in the
    new receipt's sample was evicted, not resolved: it is listed under `evicted` and never counted as
    left or as clearing its root. A thread moved to another root is reclassified, not resolved or new.
    Without a recorded sample on both sides, nothing is called evicted."""
    def outstanding(receipt):
        return {r["id"]: r for r in receipt["roots"] if r["outstanding"]}
    a, b = outstanding(old), outstanding(new)
    old_scope, new_scope = old.get("review_scope"), new.get("review_scope")

    def review_assignments(roots):
        return {(r["repo"], alert): rid for rid, r in roots.items() if r["source"] == "review_threads"
                for alert in r["alerts"]}
    old_assignments, new_assignments = review_assignments(a), review_assignments(b)
    reclassified = {key for key, rid in old_assignments.items()
                    if key in new_assignments and new_assignments[key] != rid}
    left, joined, evicted = [], [], []
    for rid in sorted(set(a) | set(b)):
        was, now = set(a.get(rid, {}).get("alerts", [])), set(b.get(rid, {}).get("alerts", []))
        root = b.get(rid) or a[rid]
        moved_from = ({alert for repo, alert in reclassified if repo == root["repo"]
                       and old_assignments[(repo, alert)] == rid}
                      if root["source"] == "review_threads" else set())
        moved_to = ({alert for repo, alert in reclassified if repo == root["repo"]
                     and new_assignments[(repo, alert)] == rid}
                    if root["source"] == "review_threads" else set())
        gone, aged_out = was - now - moved_from, set()
        if (root["source"] == "review_threads" and old_scope is not None and new_scope is not None
                and root["repo"] in old_scope and root["repo"] in new_scope):
            sampled = set((new_scope.get(root["repo"]) or {}).get("prs", []))
            prs = a[rid].get("alert_prs", {}) if rid in a else {}
            aged_out = {n for n in gone if str(n) in prs and prs[str(n)] not in sampled}
        if aged_out:
            evicted.append({"id": rid, "repo": root["repo"], "source": root["source"], "alerts": sorted(aged_out)})
        if gone - aged_out:
            left.append({"id": rid, "repo": root["repo"], "source": root["source"], "alerts": sorted(gone - aged_out),
                         "root_cleared": rid not in b and not aged_out and not moved_from})
        if now - was - moved_to:
            joined.append({"id": rid, "repo": root["repo"], "source": root["source"],
                           "alerts": sorted(now - was - moved_to),
                           "root_new": rid not in a})
    coverage = []
    for repo in sorted(set(old["coverage"]) | set(new["coverage"])):
        for source in SOURCES:
            o = old["coverage"].get(repo, {}).get(source, "absent")
            n = new["coverage"].get(repo, {}).get(source, "absent")
            if o != n:
                coverage.append({"repo": repo, "source": source, "old": o, "new": n})
    return {"schema": DELTA_SCHEMA, "programme": "CODE_MAROON", "owner": new["owner"],
            "old_fetched_at": old["fetched_at"], "new_fetched_at": new["fetched_at"],
            "closes_findings": False, "merge_authority": False,
            "alerts_left": sum(len(x["alerts"]) for x in left), "alerts_joined": sum(len(x["alerts"]) for x in joined),
            "alerts_evicted": sum(len(x["alerts"]) for x in evicted),
            "roots_cleared": sum(x["root_cleared"] for x in left), "roots_new": sum(x["root_new"] for x in joined),
            "roots_outstanding": {"old": old["roots_outstanding"], "new": new["roots_outstanding"]},
            "coverage_changes": coverage, "left": left, "joined": joined, "evicted": evicted}


def delta_counts(delta: dict) -> dict:
    """Counts only, with no root ids, so the delta can be shown wherever MAROON_PUBLIC.json can."""
    keep = ("schema", "programme", "owner", "old_fetched_at", "new_fetched_at", "closes_findings", "merge_authority",
            "alerts_left", "alerts_joined", "alerts_evicted", "roots_cleared", "roots_new", "roots_outstanding")
    return {**{k: delta[k] for k in keep}, "coverage_changes": len(delta["coverage_changes"])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="read raw alerts for every non-archived source repository of an owner")
    f.add_argument("--owner", required=True)
    f.add_argument("--out", required=True, type=Path)
    b = sub.add_parser("build", help="build receipt, fix list, lanes and public projection from raw alerts")
    b.add_argument("--raw", required=True, type=Path)
    b.add_argument("--review", type=Path, help="raw_review.json from review_threads.py fetch")
    b.add_argument("--review-overrides", type=Path, help='JSON {thread id: {"theme": ...}} from a deep read')
    b.add_argument("--out", required=True, type=Path)
    d = sub.add_parser("diff", help="alerts and roots that left or joined the outstanding set between two receipts")
    d.add_argument("--old", required=True, type=Path)
    d.add_argument("--new", required=True, type=Path)
    d.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "fetch":
        args.out.mkdir(parents=True, exist_ok=True)
        raw = fetch(args.owner)
        (args.out / "raw.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8", newline="\n")
        print("MAROON_FETCH=PASS", "repos=%d" % len(raw["repos"]), "out=%s" % (args.out / "raw.json"))
        return 0
    if args.cmd == "diff":
        delta = diff(*(json.loads(x.read_text(encoding="utf-8")) for x in (args.old, args.new)))
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "MAROON_DELTA.json").write_text(json.dumps(delta, indent=1, sort_keys=True) + "\n",
                                                    encoding="utf-8", newline="\n")
        print("MAROON_DIFF=PASS", *("%s=%s" % (k, delta[k]) for k in
                                    ("alerts_left", "alerts_joined", "alerts_evicted", "roots_cleared", "roots_new")),
              "coverage_changes=%d" % len(delta["coverage_changes"]), "out=%s" % (args.out / "MAROON_DELTA.json"))
        return 0
    review = json.loads(args.review.read_text(encoding="utf-8")) if args.review else None
    overrides = json.loads(args.review_overrides.read_text(encoding="utf-8")) if args.review_overrides else None
    receipt = build(json.loads(args.raw.read_text(encoding="utf-8")), review, overrides)
    write_outputs(receipt, args.out)
    print("MAROON_BUILD=PASS", "roots_outstanding=%d" % receipt["roots_outstanding"], "lanes=%d" % len(receipt["lanes"]),
          "out=%s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
