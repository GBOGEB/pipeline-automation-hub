#!/usr/bin/env python3
"""J03 pilot: qualify the hosted PAH GitHub Pages HTML (read-only).

Thin CLI over the canonical owners (AGENTS.md L4): hosted readback is
``mission-control/html_qa/hosted_pages_verify.py`` (``check_base``, ``fetch_status``,
``local_links``, ``qualify``); link parsing is ``html_contract.PageParser``.
This file only chooses the path population, supplies expected bytes (the served
publisher manifest and git blobs at the deployment commit) and writes the receipt.

It never deploys, never writes to GitHub and confers no merge or engineering credit.
Viewport proof is not produced here; it stays null (UNKNOWN) until supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "jade.temple.j03_hosted_html.v1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
REPO = Path(__file__).resolve().parents[3]
DEFAULT_BASE = "https://gbogeb.github.io/pipeline-automation-hub/"


def owner():
    path = REPO / "mission-control/html_qa/hosted_pages_verify.py"
    spec = importlib.util.spec_from_file_location("hosted_pages_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_blobs(repo: Path, commit: str, prefix: str = "") -> dict[str, bytes]:
    """path -> bytes for every blob at ``commit`` (optionally under ``prefix``)."""
    listing = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "-z", commit, "--", prefix or "."],
                             check=True, capture_output=True).stdout.decode("utf-8")
    entries = []
    for item in listing.split("\0"):
        if not item:
            continue
        meta, path = item.split("\t", 1)
        mode, kind, oid = meta.split()
        if kind == "blob" and mode != "120000":
            entries.append((path, oid))
    if not entries:
        return {}
    batch = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"],
                           input="".join(oid + "\n" for _, oid in entries).encode(),
                           check=True, capture_output=True).stdout
    out, pos = {}, 0
    for path, _ in entries:
        header_end = batch.index(b"\n", pos)
        size = int(batch[pos:header_end].split()[2])
        out[path] = batch[header_end + 1:header_end + 1 + size]
        pos = header_end + 1 + size + 1
    return out


def sha_index(blobs: dict[str, bytes]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for path, data in blobs.items():
        index.setdefault(hashlib.sha256(data).hexdigest(), []).append(path)
    return index


def probe(base: str, deployment: dict, repo: Path, *, repeat: int = 2, hv=None) -> dict:
    hv = hv or owner()
    hv.check_base(base)
    dep_sha = deployment.get("sha")
    if not (isinstance(dep_sha, str) and SHA40.fullmatch(dep_sha)):
        raise ValueError("deployment sha must be a 40-hex commit")
    fetch = hv.fetch_status

    # Publisher seal served by the same deployment.
    status, body, _ = fetch(base + "site-manifest.json")
    manifest = None
    if status == 200 and body is not None:
        try:
            manifest = json.loads(body.decode("utf-8"))
        except ValueError:
            manifest = None
    declared = (manifest or {}).get("public_files_sha256") or {}
    served_sha = (manifest or {}).get("source_git_sha")
    if not (isinstance(served_sha, str) and SHA40.fullmatch(served_sha)):
        served_sha = None

    # Population: root, its local links, the manifest itself.
    status, body, _ = fetch(base)
    linked = [hv._relative(base, u) for u in hv.local_links(body, base, base)] if status == 200 and body else []
    portal_paths = ["", "index.html", "site-manifest.json"]
    portal_paths += [p for p in linked if p not in portal_paths]
    expected = {p: declared[p] for p in portal_paths if p in declared}
    if "index.html" in declared:
        expected[""] = declared["index.html"]
    # site-manifest.json is the seal itself; its expected bytes are the deployment-commit
    # publisher output, not a git blob, so parity there stays UNKNOWN by construction.
    portal = hv.qualify(base, portal_paths, expected=expected, repeat=repeat, fetch=fetch)

    try:
        blobs = git_blobs(repo, dep_sha)
    except (subprocess.CalledProcessError, OSError):
        blobs = None  # deployment commit not in the local clone: blob matches stay UNKNOWN
    git_available = blobs is not None
    blobs = blobs or {}
    by_sha = sha_index(blobs)
    docs = {p: b for p, b in blobs.items() if p.startswith("docs/") and p.endswith(".html")}
    docs_paths = sorted(p[len("docs/"):] for p in docs)
    docs_expected = {p[len("docs/"):]: hashlib.sha256(b).hexdigest() for p, b in docs.items()}
    docs_probe = hv.qualify(base, docs_paths, expected=docs_expected, repeat=repeat,
                            follow_links=False, fetch=fetch)
    for row in docs_probe["results"]:
        row["git_source"] = "docs/" + row["path"]

    for row in portal["results"] + docs_probe["results"]:
        row["git_blob_paths_at_deployment"] = (by_sha.get(row["served_sha256"]) or None
                                               if row["served_sha256"] and git_available else None)

    s = portal["summary"]
    d = docs_probe["summary"]
    served_matches = (served_sha == dep_sha) if served_sha else None

    def verdict(ok):
        return "PASS" if ok else "FAIL"

    criteria = {
        "http_status": verdict(s["paths"] > 0 and s["http_200_converged"] == s["paths"]),
        "served_sha": None if served_matches is None else verdict(served_matches),
        # every probed path except the seal itself has a declared digest and matches it
        "content_parity": verdict(s["parity_mismatch"] == 0 and s["parity_match"] == s["paths"] - 1),
        "asset_links": verdict(not s["links_broken"]),
        "viewports": None,
    }
    ladder_met = all(criteria[k] == "PASS" for k in ("http_status", "served_sha", "content_parity"))
    known = [v for v in criteria.values() if v is not None]
    if "FAIL" in known:
        j03 = "NOT_QUALIFIED"
    elif len(known) == len(criteria):
        j03 = "QUALIFIED"
    else:
        j03 = "UNKNOWN"
    docs_deployed = d["paths"] > 0 and d["parity_match"] == d["paths"]
    passing = sorted({r["url"] for r in portal["results"] if r["parity"] == "MATCH"})
    broken = [{"page": r["path"], "link": link["path"], "status": link["status"]}
              for r in portal["results"] for link in (r["links"] or []) if link["status"] != 200]
    return {
        "schema": SCHEMA,
        "bd_item": "J03",
        "repo": "GBOGEB/pipeline-automation-hub",
        "probe_time_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "base_url": base,
        "deployment": deployment,
        "served_manifest": {"schema": (manifest or {}).get("schema"),
                            "source_git_sha": served_sha,
                            "declared_files": len(declared) if manifest else None},
        "served_sha": served_sha,
        "git_commit_available": git_available,
        "served_sha_equals_deployment_sha": served_matches,
        "portal": portal,
        "committed_docs_html": docs_probe,
        "docs_tree_deployed": docs_deployed,
        "docs_note": ("Pages build_type is workflow; the served site is the pages_portal.py artifact, "
                      "so committed docs/**/*.html are probed at their /docs-relative URL and are "
                      "expected to be absent or different unless the owner chooses the docs path"),
        "broken_links": broken,
        "hosted_urls_passing_parity": passing,
        "viewports": None,
        "viewports_note": "UNKNOWN: viewport proof supplied separately (no browser in this probe)",
        "criteria": criteria,
        "html_qa_ladder": {
            "level": "PAGES_HOSTED" if ladder_met else "HOSTED_NOT_PROVEN",
            "observations": ("2 consecutive HTTP 200 fetches with exact publisher-manifest SHA256 "
                             "parity for every root-linked page/asset; deployment sha equals served sha"),
            "owner_review": None,
        },
        "evidence_level": "HOSTED_HTTP_CONTENT_PARITY" if ladder_met else "HOSTED_NOT_PROVEN",
        "verdict": j03,
        # PARTIAL only when every machine-checkable criterion passed and viewports are pending.
        "j03_pilot_status": "PARTIAL" if j03 == "UNKNOWN" and ladder_met else "PENDING",
        "merge_admission": "HOLD",
        "authority_transfer": False,
        "engineering_credit_delta": 0,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--deployment-sha", required=True)
    ap.add_argument("--deployment-id", type=int)
    ap.add_argument("--deployment-run-id", type=int)
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--receipt", type=Path, required=True)
    a = ap.parse_args(argv)
    deployment = {"sha": a.deployment_sha, "id": a.deployment_id, "run_id": a.deployment_run_id,
                  "environment": "github-pages"}
    receipt = probe(a.base_url, deployment, a.repo, repeat=a.repeat)
    a.receipt.write_bytes((json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": receipt["verdict"], "criteria": receipt["criteria"],
                      "served_sha": receipt["served_sha"],
                      "portal": receipt["portal"]["summary"],
                      "docs": receipt["committed_docs_html"]["summary"]}, sort_keys=True))
    return 0 if receipt["verdict"] != "NOT_QUALIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
