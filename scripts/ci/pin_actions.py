#!/usr/bin/env python3
"""Pin GitHub Actions `uses:` references to full commit SHAs.

Rewrite mode (default):
    uses: owner/repo[/path]@<tag>   ->   uses: owner/repo[/path]@<40-hex sha> # <tag>

Tags and branches are resolved with `gh api repos/{owner}/{repo}/commits/{ref} --jq .sha`.
The commits endpoint peels annotated tags, so the pin is always the commit, never the tag object.
Resolutions are cached per (owner/repo, ref) for the run.

Skipped: local actions (`./...`), `docker://` images, references already pinned to a 40-hex SHA,
and reusable workflows that live in this repository (they move with the repo itself).

Check mode (`--check`): no network; lists every unpinned reference as `file:line: ref` and exits 1
when any exist. Used as a CI ratchet on changed workflow files.

Only the `uses:` lines are touched; every other byte (indentation, quotes, line endings, comments
on other lines) is preserved. Comment lines (`# uses: ...@<40-hex>`) are never rewritten.

Exit codes: 0 ok / nothing unpinned, 1 unpinned refs found (--check), 2 resolution or usage error.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF_REPO = "GBOGEB/pipeline-automation-hub"
SHA40 = re.compile(r"^[0-9a-f]{40}$")

# Classification is shared with the JADE DevOps census (mission-control/jade_temple/devops/workflows.py)
# so "pinned" means the same thing here as in the census metric. That module needs PyYAML; when it is
# not importable (bare runner python) an equivalent stdlib definition is used. A test asserts parity.
try:  # pragma: no cover - exercised by the parity test when PyYAML is present
    sys.path.insert(0, str(ROOT / "mission-control" / "jade_temple" / "devops"))
    from workflows import action_ref  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover
    def action_ref(uses: str) -> dict:
        u = (uses or "").strip()
        if u.startswith("./"):
            return {"uses": u, "kind": "local", "third_party": False, "pinned": True}
        if u.startswith("docker://"):
            return {"uses": u, "kind": "docker", "third_party": True, "pinned": "@sha256:" in u}
        name, _, ref = u.partition("@")
        kind = "reusable" if "/.github/workflows/" in name else "action"
        return {"uses": u, "kind": kind, "third_party": True, "pinned": bool(SHA40.match(ref)),
                "name": name.lower()}
finally:
    if sys.path and sys.path[0].endswith("devops"):
        sys.path.pop(0)

# A `uses:` key at the start of a line (optionally a list item), optionally quoted, optional trailing comment.
USES_LINE = re.compile(
    r"^(?P<lead>[ \t]*(?:-[ \t]+)?uses:[ \t]*)"
    r"(?P<q>[\"']?)(?P<ref>[^\s\"'#]+)(?P=q)"
    r"(?P<gap>[ \t]*)(?P<comment>#[^\r\n]*)?"
    r"(?P<eol>[ \t]*\r?\n?)$"
)


class ResolveError(RuntimeError):
    pass


def gh_resolve(repo: str, ref: str) -> str:
    """Resolve owner/repo@ref to a commit SHA with the GitHub CLI."""
    path = f"repos/{repo}/commits/{urllib.parse.quote(ref, safe='')}"
    try:
        out = subprocess.run(["gh", "api", path, "--jq", ".sha"], capture_output=True, text=True,
                             timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ResolveError(f"{repo}@{ref}: {exc}") from exc
    sha = out.stdout.strip()
    if out.returncode != 0 or not SHA40.match(sha):
        raise ResolveError(f"{repo}@{ref}: gh api failed ({out.returncode}): {out.stderr.strip() or sha}")
    return sha


class Resolver:
    """Caching wrapper around a resolve(repo, ref) -> sha function."""

    def __init__(self, resolve=gh_resolve):
        self._resolve = resolve
        self.cache: dict[tuple[str, str], str] = {}

    def __call__(self, repo: str, ref: str) -> str:
        key = (repo.lower(), ref)
        if key not in self.cache:
            sha = self._resolve(repo, ref)
            if not SHA40.match(sha or ""):
                raise ResolveError(f"{repo}@{ref}: resolver returned {sha!r}")
            self.cache[key] = sha
        return self.cache[key]


def needs_pin(uses: str, self_repo: str = SELF_REPO) -> bool:
    """True when `uses` is a remote action/reusable workflow on a mutable ref."""
    info = action_ref(uses)
    if info["kind"] in ("local", "docker") or info["pinned"]:
        return False
    name, sep, ref = uses.partition("@")
    if not sep or not ref:
        return False
    if info["kind"] == "reusable" and name.lower().startswith(self_repo.lower() + "/"):
        return False
    return True


def split_uses(uses: str) -> tuple[str, str, str]:
    """owner/repo[/path]@ref -> (owner/repo, owner/repo[/path], ref)."""
    name, _, ref = uses.partition("@")
    parts = name.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ResolveError(f"cannot parse action reference {uses!r}")
    return f"{parts[0]}/{parts[1]}", name, ref


def scan_text(text: str, self_repo: str = SELF_REPO) -> list[tuple[int, str]]:
    """(1-based line number, uses value) for each unpinned reference."""
    found = []
    for n, line in enumerate(text.splitlines(keepends=True), 1):
        m = USES_LINE.match(line)
        if m and needs_pin(m["ref"], self_repo):
            found.append((n, m["ref"]))
    return found


def pin_text(text: str, resolve, self_repo: str = SELF_REPO) -> tuple[str, list[tuple[int, str, str]]]:
    """Return (new text, [(line, old uses, new uses)]). Only matching `uses:` lines change."""
    out, changes = [], []
    for n, line in enumerate(text.splitlines(keepends=True), 1):
        m = USES_LINE.match(line)
        if not m or not needs_pin(m["ref"], self_repo):
            out.append(line)
            continue
        repo, name, ref = split_uses(m["ref"])
        sha = resolve(repo, ref)
        new_ref = f"{name}@{sha}"
        old_comment = (m["comment"] or "").lstrip("#").strip()
        comment = f"# {ref}" + (f" ({old_comment})" if old_comment else "")
        out.append(f"{m['lead']}{m['q']}{new_ref}{m['q']} {comment}{m['eol']}")
        changes.append((n, m["ref"], new_ref))
    return "".join(out), changes


def read_text(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write_text(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def shown(path: Path) -> str:
    """Repo-relative POSIX path when possible (stable output and annotation paths)."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def expand(paths: list[str], excludes: list[str]) -> list[Path]:
    if not paths:
        paths = [str(ROOT / ".github" / "workflows" / "*.yml"), str(ROOT / ".github" / "workflows" / "*.yaml")]
    files: list[Path] = []
    for p in paths:
        hits = sorted(glob.glob(p)) if any(c in p for c in "*?[") else [p]
        files.extend(Path(h) for h in hits)
    ex = {Path(e).resolve() for e in excludes}
    ex_names = {Path(e).name for e in excludes if "/" not in e and "\\" not in e}
    seen, result = set(), []
    for f in files:
        r = f.resolve()
        if r in seen or r in ex or f.name in ex_names:
            continue
        seen.add(r)
        result.append(f)
    return result


def main(argv=None, resolve=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*", help="workflow files or globs (default: .github/workflows/*.y*ml)")
    ap.add_argument("--check", action="store_true", help="list unpinned refs and exit 1 if any (no network)")
    ap.add_argument("--exclude", action="append", default=[], help="file path or basename to skip (repeatable)")
    ap.add_argument("--self-repo", default=SELF_REPO, help="owner/repo whose reusable workflows are not pinned")
    ap.add_argument("--json", action="store_true", help="with --check: JSON list of unpinned refs on stdout")
    args = ap.parse_args(argv)

    files = expand(args.files, args.exclude)
    missing = [str(f) for f in files if not f.is_file()]
    if missing:
        print("error: not a file: " + ", ".join(missing), file=sys.stderr)
        return 2

    if args.check:
        bad = [(shown(f), n, ref) for f in files for n, ref in scan_text(read_text(f), args.self_repo)]
        if args.json:
            print(json.dumps({"files": len(files), "unpinned": [{"file": f, "line": n, "uses": r} for f, n, r in bad]},
                             indent=2))
        for f, n, ref in bad:
            print(f"{f}:{n}: unpinned action reference: {ref}")
            if os.environ.get("GITHUB_ACTIONS") == "true":
                print(f"::error file={f},line={n}::Pin '{ref}' to a 40-hex commit SHA "
                      f"(python scripts/ci/pin_actions.py {f})")
        if not bad:
            print(f"ok: {len(files)} file(s), every remote action is pinned to a commit SHA")
        return 1 if bad else 0

    resolver = Resolver(resolve or gh_resolve)
    total = 0
    try:
        for f in files:
            text = read_text(f)
            new, changes = pin_text(text, resolver, args.self_repo)
            if changes:
                write_text(f, new)
                total += len(changes)
                for n, old, ref in changes:
                    print(f"{shown(f)}:{n}: {old} -> {ref}")
    except ResolveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"pinned {total} reference(s) in {len(files)} file(s); {len(resolver.cache)} distinct resolution(s)")
    for (repo, ref), sha in sorted(resolver.cache.items()):
        print(f"  {repo}@{ref} = {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
