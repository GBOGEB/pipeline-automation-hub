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
RANK = {"critical": 6, "high": 5, "medium": 4, "low": 3, "error": 2, "warning": 1, "note": 0}
SOURCES = {
    # source -> (API path, states to read, state -> disposition)
    "dependabot": ("dependabot/alerts", ("open", "fixed", "dismissed", "auto_dismissed"),
                   {"open": "outstanding", "fixed": "closed", "dismissed": "deferred", "auto_dismissed": "deferred"}),
    "code_scanning": ("code-scanning/alerts", ("open", "fixed", "dismissed"),
                      {"open": "outstanding", "fixed": "closed", "dismissed": "deferred"}),
    "secret_scanning": ("secret-scanning/alerts", ("open", "resolved"),
                        {"open": "outstanding", "resolved": "closed"}),
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
        prefix = {"dependabot": "deps", "code_scanning": "code", "secret_scanning": "secrets"}[source]
        lanes.append({"id": f"{repo.split('/')[-1]}:{prefix}-{family}".lower(), "repo": repo, "source": source,
                      "family": family, "severity": rs[0]["severity"], "roots": [r["id"] for r in rs],
                      "outstanding": sum(r["outstanding"] for r in rs),
                      "paths": sorted({p for r in rs for p in r["paths"]})})
    by_repo = collections.defaultdict(list)
    for lane in lanes:
        if lane["source"] == "code_scanning":
            by_repo[lane["repo"]].append(lane)
    for group in by_repo.values():
        for lane in group:
            others = {p for o in group if o is not lane for p in o["paths"]}
            lane["shared_paths"] = sorted(set(lane["paths"]) & others)
    return sorted(lanes, key=lambda l: (-RANK.get(l["severity"], -1), -l["outstanding"], l["id"]))


def build(raw: dict) -> dict:
    manifestations, coverage = [], {}
    for repo, entry in raw["repos"].items():
        coverage[repo] = {"visibility": entry["visibility"]}
        for source, got in entry["sources"].items():
            coverage[repo][source] = got["coverage"]
            manifestations += [manifestation(repo, source, a) for a in got.get("alerts", [])]
    roots = roots_of(manifestations)
    totals = collections.Counter()
    for m in manifestations:
        totals[(m["source"], m["disposition"])] += 1
    return {
        "schema": SCHEMA, "programme": "CODE_MAROON", "owner": raw["owner"], "fetched_at": raw["fetched_at"],
        "closes_findings": False, "merge_authority": False,
        "totals": {s: {d: totals[(s, d)] for d in ("outstanding", "closed", "deferred")} for s in SOURCES},
        "roots_outstanding": sum(1 for r in roots if r["outstanding"]),
        "coverage": coverage, "roots": roots, "lanes": lanes_of(roots),
    }


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="read raw alerts for every non-archived source repository of an owner")
    f.add_argument("--owner", required=True)
    f.add_argument("--out", required=True, type=Path)
    b = sub.add_parser("build", help="build receipt, fix list, lanes and public projection from raw alerts")
    b.add_argument("--raw", required=True, type=Path)
    b.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "fetch":
        args.out.mkdir(parents=True, exist_ok=True)
        raw = fetch(args.owner)
        (args.out / "raw.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8", newline="\n")
        print("MAROON_FETCH=PASS", "repos=%d" % len(raw["repos"]), "out=%s" % (args.out / "raw.json"))
        return 0
    receipt = build(json.loads(args.raw.read_text(encoding="utf-8")))
    write_outputs(receipt, args.out)
    print("MAROON_BUILD=PASS", "roots_outstanding=%d" % receipt["roots_outstanding"], "lanes=%d" % len(receipt["lanes"]),
          "out=%s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
