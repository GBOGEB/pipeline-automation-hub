#!/usr/bin/env python3
"""HV-03 private, read-only worktree custody inventory.

Complements Invoke-WorkspaceAudit.ps1 (disk/token/prune owner); does not invoke
its -Apply path. No network, token inspection, commit, push, deletion, restore,
PR-state attestation or automatic upload. Private file paths never hit stdout.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

SCHEMA = "gbo.hv03.local-custody.v1"
BINARY_EXTS = {".pdf", ".docx", ".pptx", ".xlsx", ".xls", ".zip", ".png",
               ".jpg", ".jpeg", ".svg", ".exe", ".dll", ".bin", ".parquet"}
MAX_BYTES = 64 * 1024 * 1024

def git(repo: Path, *args: str) -> bytes:
    env = dict(os.environ)
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    env["GIT_NO_LAZY_FETCH"] = "1"
    env["GIT_ALLOW_PROTOCOL"] = ""
    p = subprocess.run(["git", "-C", str(repo), *args], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode:
        raise ValueError("HV03_HOLD: git read failed: " + " ".join(args[:2]))
    return p.stdout

def as_text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="surrogateescape")

def canonical(obj: object) -> bytes:
    return (json.dumps(obj, ensure_ascii=True, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")

def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def worktrees(repo: Path) -> list[Path]:
    data = as_text(git(repo, "worktree", "list", "--porcelain", "-z"))
    entries = []
    for field in data.split("\0"):
        if field.startswith("worktree "):
            path = Path(field[9:])
            if not path.is_absolute():
                raise ValueError("HV03_HOLD: nonabsolute worktree path")
            entries.append(path)
    if not entries or len(entries) != len(set(entries)):
        raise ValueError("HV03_HOLD: missing or duplicate worktrees")
    return sorted(entries, key=lambda p: str(p).casefold())

def paths_status(wt: Path) -> list[dict]:
    tokens = git(wt, "status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0")
    records = []
    i = 0
    while i < len(tokens):
        item = tokens[i]
        i += 1
        if not item:
            continue
        if len(item) < 4 or item[2:3] != b" ":
            raise ValueError("HV03_HOLD: unknown porcelain record")
        flag, path = as_text(item[:2]), as_text(item[3:])
        old = None
        if "R" in flag or "C" in flag:
            if i >= len(tokens) or not tokens[i]:
                raise ValueError("HV03_HOLD: incomplete rename/copy")
            old = as_text(tokens[i])
            i += 1
        records.append({"status": flag, "path": path, "previous_path": old})
    return sorted(records, key=lambda r: (r["path"], r["status"]))

def hash_file(wt: Path, rel: str, max_bytes: int) -> dict:
    if (not rel or Path(rel).is_absolute() or rel.startswith(("/", "\\"))
            or re.match(r"^[A-Za-z]:[\\/]", rel) or ".." in Path(rel).parts
            or ".." in rel.replace("\\", "/").split("/") or "\x00" in rel):
        return {"state": "UNSAFE_PATH", "bytes": None, "sha256": None}
    path = wt / rel
    if path.is_symlink():
        return {"state": "SYMLINK_UNTRUSTED", "bytes": None, "sha256": None}
    if not path.resolve().is_relative_to(wt.resolve()):
        return {"state": "OUTSIDE_WORKTREE", "bytes": None, "sha256": None}
    if not path.is_file():
        return {"state": "MISSING", "bytes": None, "sha256": None}
    try:
        size = path.stat().st_size
        if size > max_bytes:
            return {"state": "SIZE_LIMIT", "bytes": size, "sha256": None}
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        if path.stat().st_size != size:
            return {"state": "CHANGED_DURING_SCAN", "bytes": size, "sha256": None}
        return {"state": "HASHED", "bytes": size, "sha256": h.hexdigest()}
    except OSError:
        return {"state": "UNREADABLE", "bytes": None, "sha256": None}

def staged_index(wt: Path, max_bytes: int) -> dict[str, list[dict]]:
    """Record staged blobs, including conflicts, without writing or modifying index."""
    result: dict[str, list[dict]] = {}
    for raw in git(wt, "ls-files", "--stage", "-z").split(b"\0"):
        if not raw:
            continue
        try:
            head, name = raw.split(b"\t", 1)
            mode, oid, stage = as_text(head).split(" ")
            if not re.fullmatch("[0-9a-f]{40,64}", oid) or not stage.isdecimal():
                raise ValueError("invalid staged blob")
            rel = as_text(name)
            result.setdefault(rel, []).append({"mode": mode, "oid": oid, "stage": int(stage)})
        except ValueError as exc:
            raise ValueError("HV03_HOLD: invalid index entry") from exc
    for entries in result.values():
        for entry in entries:
            # Exact Git object ID is the nonmutable index receipt. SHA-256
            # of index bytes is only collected for relevant staged files below.
            entry["index_sha256"] = None
            entry["index_sha_state"] = "NOT_REQUESTED"
    return result

def hash_index_stage(wt: Path, entry: dict, max_bytes: int) -> dict:
    if entry["mode"] == "160000":
        return {"index_sha_state": "GITLINK_NONBLOB", "index_sha256": None}
    size_raw = git(wt, "cat-file", "-s", entry["oid"])
    try:
        size = int(size_raw.strip())
    except ValueError as exc:
        raise ValueError("HV03_HOLD: staged object size") from exc
    if size > max_bytes:
        return {"index_sha_state": "SIZE_LIMIT", "index_sha256": None}
    raw = git(wt, "cat-file", "blob", entry["oid"])
    if len(raw) != size:
        return {"index_sha_state": "SIZE_CHANGED", "index_sha256": None}
    return {"index_sha_state": "HASHED", "index_sha256": sha(raw)}

def owners(path: str, rules: list[dict]) -> dict:
    matches = [r for r in rules if fnmatch.fnmatchcase(path, r["glob"])]
    if len(matches) > 1:
        return {"owner_state": "COLLISION", "owner": None, "pr": None}
    if not matches:
        return {"owner_state": "UNKNOWN", "owner": None, "pr": None}
    return {"owner_state": "DECLARED_UNVERIFIED", "owner": matches[0]["owner"],
            "pr": matches[0].get("pr")}

def load_owner_rules(path: Path | None) -> list[dict]:
    if path is None:
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "gbo.hv03.owner-allowlist.v1" or not isinstance(data.get("rules"), list):
        raise ValueError("HV03_HOLD: owner allowlist schema")
    for row in data["rules"]:
        if (not isinstance(row, dict) or not isinstance(row.get("glob"), str)
                or not row["glob"] or not isinstance(row.get("owner"), str)
                or not row["owner"] or not (row.get("pr") is None or
                        isinstance(row["pr"], int) and not isinstance(row["pr"], bool))):
            raise ValueError("HV03_HOLD: owner rule")
    return data["rules"]

def scan(repo: Path, *, rules: list[dict] | None = None,
         max_bytes: int = MAX_BYTES) -> dict:
    repo = Path(as_text(git(repo, "rev-parse", "--show-toplevel")).strip()).resolve()
    source_refs = []
    for line in as_text(git(repo, "for-each-ref",
                   "--format=%(refname) %(objectname)", "refs/heads")).splitlines():
        ref, obj = line.rsplit(" ", 1)
        if not re.fullmatch("[a-f0-9]{40,64}", obj):
            raise ValueError("HV03_HOLD: invalid branch ref")
        source_refs.append({"ref": ref, "oid": obj})
    outputs = []
    for wt in worktrees(repo):
        if not wt.exists():
            outputs.append({"path": str(wt), "state": "MISSING_WORKTREE"})
            continue
        head = as_text(git(wt, "rev-parse", "HEAD")).strip()
        # Detached HEAD makes symbolic-ref fail, so use a tolerant local rev-parse.
        branch_probe = subprocess.run(["git", "-C", str(wt), "symbolic-ref", "-q",
                                       "--short", "HEAD"], capture_output=True, check=False)
        branch = as_text(branch_probe.stdout).strip() if branch_probe.returncode == 0 else None
        changed = paths_status(wt)
        index = staged_index(wt, max_bytes)
        found = {r["path"] for r in changed}
        binary_paths = [as_text(raw) for raw in
                        git(wt, "ls-files", "-z").split(b"\0") if raw and
                        Path(as_text(raw)).suffix.lower() in BINARY_EXTS and
                        as_text(raw) not in found]
        records = []
        for record in changed:
            rel = record["path"]
            stages = [dict(row) for row in index.get(rel, [])] if record["status"][0] not in (" ", "?") else []
            for stage in stages:
                stage.update(hash_index_stage(wt, stage, max_bytes))
            records.append({**record, "kind": "DIRTY_OR_UNTRACKED",
                            "staged_index": stages,
                            **hash_file(wt, rel, max_bytes),
                            **owners(rel, rules or [])})
        for rel in sorted(set(binary_paths)):
            records.append({"status": "  ", "path": rel, "previous_path": None,
                            "kind": "TRACKED_BINARY",
                            **hash_file(wt, rel, max_bytes),
                            **owners(rel, rules or [])})
        outputs.append({"path": str(wt), "state": "OBSERVED", "branch": branch,
                        "head": head, "remote_head": "UNKNOWN_OFFLINE",
                        "files": sorted(records, key=lambda r: (r["path"], r["kind"]))})
    return {"schema": SCHEMA, "repository_root": str(repo),
            "remote_credential_or_api_use": False, "source_refs": sorted(source_refs, key=lambda r: r["ref"]),
            "worktrees": outputs, "merge_admission": "HOLD", "upload_authorized": False}

def public_summary(data: dict) -> dict:
    files = [f for wt in data["worktrees"] for f in wt.get("files", [])]
    incomplete = sum(f["state"] != "HASHED" for f in files)
    collisions = sum(f["owner_state"] == "COLLISION" for f in files)
    return {"schema": "gbo.hv03.private-scan-summary.v1",
            "worktrees": len(data["worktrees"]), "files": len(files),
            "dirty": sum(f["kind"] == "DIRTY_OR_UNTRACKED" for f in files),
            "tracked_binaries": sum(f["kind"] == "TRACKED_BINARY" for f in files),
            "incomplete_hashes": incomplete, "owner_collisions": collisions,
            "private_manifest_sha256": sha(canonical(data)),
            "remote_heads_verified": False, "owner_approval": "PENDING",
            "merge_admission": "HOLD", "publication": "NOT_AUTHORIZED"}

def write_private(out_dir: Path, data: dict, summary: dict) -> None:
    # Explicit destination only, and never beneath a worktree; no automatic upload.
    target = out_dir.resolve()
    if any((parent / ".git").exists() for parent in (target, *target.parents)):
        raise ValueError("HV03_HOLD: cannot write receipts into a git worktree")
    for wt in data["worktrees"]:
        root = Path(wt["path"]).resolve()
        if target == root or target.is_relative_to(root):
            raise ValueError("HV03_HOLD: cannot write receipts into a git worktree")
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target, 0o700)
    for name, payload in (("HV03_PRIVATE.json", data), ("HV03_SUMMARY.json", summary)):
        fd, temp = tempfile.mkstemp(prefix=".hv03-", dir=target)
        try:
            os.chmod(temp, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(canonical(payload))
            os.replace(temp, target / name)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only local Git/worktree custody; never uploads")
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--owner-map", type=Path, help="Private explicit per-glob ownership")
    ap.add_argument("--out-dir", type=Path, help="Explicit private directory outside repo")
    ap.add_argument("--compare", type=Path, help="Previous private receipt for repeat-scan parity")
    ap.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    a = ap.parse_args(argv)
    if a.max_bytes < 1 or a.max_bytes > 1024 * 1024 * 1024:
        raise SystemExit("HV03_HOLD: invalid hash size cap")
    data = scan(a.repo, rules=load_owner_rules(a.owner_map), max_bytes=a.max_bytes)
    summary = public_summary(data)
    if a.compare:
        previous = json.loads(a.compare.read_text(encoding="utf-8"))
        summary["repeat_scan_equal"] = sha(canonical(previous)) == summary["private_manifest_sha256"]
    if a.out_dir:
        write_private(a.out_dir, data, summary)
    summary["private_files_written"] = bool(a.out_dir)
    print(json.dumps(summary, sort_keys=True))

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit("HV03_HOLD: local collection incomplete; inspect private logs")
