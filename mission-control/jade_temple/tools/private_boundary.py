#!/usr/bin/env python3
"""Aggregate-only projection of private repositories for every public JADE output.

The hub is public; a private repo (declared in gogreen/token_census/REGISTRY.json,
the owner of that list) may appear in JADE only as counts and statuses. project()
keeps every row, list length, gate status, count and percentage, and replaces each
row-level identifier with MARK:

  * any URL into a private repo, anywhere in the document;
  * the private repo's commit and blob SHAs (read from SHA-named keys inside a
    private row, from private commit URLs and from oids of private file paths),
    wherever they occur, including 7+ character prefixes inside text;
  * inside a private row: run, job, issue and PR numbers, and `#123` and long
    numeric references in text.

Repo names, workflow names and file paths are kept: they are the JADE cohort's
structure, not row-level evidence.

A missing private identifier is UNKNOWN downstream, never PASS or zero. project()
is pure and idempotent, so a committed output must be a fixed point of it.

  python tools/private_boundary.py --write data/X.json ...   purge recorded receipts
  python tools/private_boundary.py --check                   every committed JSON is projected
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT.parent / "gogreen" / "token_census" / "REGISTRY.json"
MARK = "PRIVATE_AGGREGATE_ONLY"

SHA_KEYS = {"sha", "head_sha", "source_sha", "current_head", "nplus1_sha", "head_readback", "focus_sha",
            "census_sha", "gate_sha", "observed_head", "at", "candidate_sha", "head", "default_sha",
            "main_sha", "commit", "commit_sha", "head_oid", "base_sha", "merge_sha"}
ID_KEYS = {"id", "run_id", "job_id", "check_run_id", "number", "pr", "pr_number", "issue", "issue_number",
           "workflow_id", "check_suite_id", "run_number"}
OWNER_KEYS = ("repo", "repository", "full_name", "name", "label", "id", "scope")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX_TOKEN = re.compile(r"\b[0-9a-f]{7,40}\b")
ISSUE_REF = re.compile(r"#\d+\b")
LONG_ID = re.compile(r"\b\d{8,}\b")


def sha_key(k) -> bool:
    return isinstance(k, str) and (k in SHA_KEYS or "sha" in k or k.endswith("oid"))


def id_key(k) -> bool:
    return isinstance(k, str) and (k in ID_KEYS or k.endswith(("_run", "_run_id", "_job_id", "_pr", "_issue")))


def private_repos(registry: Path = REGISTRY) -> tuple[str, ...]:
    return tuple(json.loads(registry.read_text(encoding="utf-8"))["private_repos"])


class Boundary:
    def __init__(self, repos=None):
        self.repos = tuple(repos if repos is not None else private_repos())
        names = "|".join(re.escape(r.split("/", 1)[1]) for r in self.repos)
        full = "|".join(re.escape(r) for r in self.repos)
        self.url = re.compile(r"https?://(?:www\.)?github\.com/(?:" + full + r")(?![A-Za-z0-9._-])[^\s\"'<>|,)]*", re.I)
        # A row or key belongs to a private repo when it IS the repo: "cryoplant-project",
        # "GBOGEB/cryoplant-project" or a JADE node id "S.cryoplant-project". A public repo's
        # workflow named "cryoplant-project Federation Check" does not.
        self.owner = re.compile(r"^(?:[A-Za-z]+\.)?(?:" + full + "|" + names + r")$", re.I) if names else None
        # A path or JADE object id inside the private repo: "GBOGEB/cryoplant-project:controls/x.yaml",
        # "jade:file:cryoplant-project:tests/x.py".
        self.inside = re.compile(r"(?:^|[/:])(?:" + names + r"):", re.I) if names else None

    def names_private(self, value) -> bool:
        return bool(self.owner and isinstance(value, str) and self.owner.match(value))

    def row_is_private(self, d: dict) -> bool:
        return any(self.names_private(d.get(k)) for k in OWNER_KEYS)

    def path_is_private(self, d: dict) -> bool:
        return any(isinstance(d.get(k), str) and self.inside.search(d[k]) for k in ("path", "jade_oid", "oid"))

    # pass 1: the private repo's identifiers. Commit SHAs name the private repo wherever they occur;
    # blob OIDs hash content, so a file copied into a public repo has the same OID there and a blob
    # OID is redacted only inside a private row. Blob entries are kept as "blob:<oid>"; an object id
    # that a public row also records (a GitHub tree "sha" of a shared file) is "public:<oid>" and kept.
    def collect(self, o, priv=False, shas=None) -> set[str]:
        shas = set() if shas is None else shas
        if isinstance(o, dict):
            priv = priv or self.row_is_private(o)
            path_private = bool(self.inside) and self.path_is_private(o)
            for k, v in o.items():
                kp = priv or self.names_private(k)
                if isinstance(v, str) and HEX40.match(v):
                    if (kp or path_private) and isinstance(k, str) and k.endswith("oid"):
                        shas.add("blob:" + v)
                    elif (kp and sha_key(k)) or self.names_private(k):
                        shas.add(v)
                    elif not kp and (sha_key(k) or k == "oid"):
                        shas.add("public:" + v)
                self.collect(v, kp, shas)
        elif isinstance(o, list):
            for v in o:
                self.collect(v, priv, shas)
        elif isinstance(o, str):
            for m in self.url.finditer(o):
                shas.update(re.findall(r"[0-9a-f]{40}", m.group(0)))
        return shas

    # pass 2: replace
    def text(self, s: str, priv: bool, commits: frozenset, blobs: frozenset) -> str:
        s = self.url.sub(MARK, s)
        known = commits | blobs if priv else commits
        if known:
            s = HEX_TOKEN.sub(lambda m: MARK if m.group(0) in known or (len(m.group(0)) < 40 and any(
                x.startswith(m.group(0)) for x in known)) else m.group(0), s)
        if priv:
            s = ISSUE_REF.sub(MARK, s)
            s = LONG_ID.sub(MARK, s)
        return s

    def apply(self, o, priv: bool, commits: frozenset, blobs: frozenset):
        if isinstance(o, dict):
            priv = priv or self.row_is_private(o)
            out = {}
            for k, v in o.items():
                kp = priv or self.names_private(k)
                if kp and id_key(k) and isinstance(v, int) and not isinstance(v, bool):
                    out[k] = None
                else:
                    out[k] = self.apply(v, kp, commits, blobs)
            return out
        if isinstance(o, list):
            return [self.apply(v, priv, commits, blobs) for v in o]
        if isinstance(o, str):
            return self.text(o, priv, commits, blobs)
        return o

    def apply_all(self, docs, shas: set[str]):
        public = {x[7:] for x in shas if x.startswith("public:")}
        blobs = frozenset(x[5:] for x in shas if x.startswith("blob:"))
        commits = frozenset(x for x in shas if ":" not in x) - public
        return [self.apply(d, False, commits, blobs) for d in docs]

    def project(self, doc, extra_shas=()):
        return self.project_many(doc, extra_shas=extra_shas)[0]

    def project_many(self, *docs, extra_shas=()):
        """Project documents that cross-reference each other with one shared SHA set."""
        shas = set(extra_shas)
        for d in docs:
            self.collect(d, shas=shas)
        return self.apply_all(docs, shas)


_DEFAULT: Boundary | None = None


def boundary() -> Boundary:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Boundary()
    return _DEFAULT


def project(doc, extra_shas=()):
    """Aggregate-only projection with the declared private repos (see module docstring)."""
    return boundary().project(doc, extra_shas)


def project_many(*docs, extra_shas=()):
    return boundary().project_many(*docs, extra_shas=extra_shas)


def committed_json(root: Path = ROOT) -> list[Path]:
    return sorted(p for d in ("data", "site") for p in (root / d).glob("*.json"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", nargs="+", metavar="FILE", help="project these JSON files in place (paths under jade_temple)")
    mode.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.write:
        for rel in a.write:
            p = ROOT / rel
            doc = json.loads(p.read_text(encoding="utf-8"))
            new = project(doc)
            if new != doc:
                raw = p.read_text(encoding="utf-8")
                indent = None if raw.lstrip().startswith("{\"") and "\n" not in raw.strip() else 2
                p.write_text(json.dumps(new, indent=indent, ensure_ascii="\\u" in raw) + "\n", encoding="utf-8", newline="\n")
                print("PROJECTED", rel)
        return 0
    bad = [p.relative_to(ROOT).as_posix() for p in committed_json()
           if (d := json.loads(p.read_text(encoding="utf-8"))) != project(d)]
    print(("FAIL private rows not aggregate-only: " + ", ".join(bad)) if bad else "PASS private boundary")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
