#!/usr/bin/env python3
"""Golden Thread P2: real GitHub Git-object round-trip proof for all renditions.

One governed truth is rendered to JSON/YAML/Markdown/HTML/DOCX/XLSX/PPTX,
written as Git blobs, assembled into a Git tree and deterministic unattached
commit, fetched back from GitHub, re-extracted, and verified for zero semantic
delta. No ref is updated. Visual fidelity remains explicitly uncredited.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, Tuple

import golden_thread as gt
import office_semantic_carrier as osc
import rendition_family as rf

SCHEMA = "missioncontrol.golden_thread_github_roundtrip.v1"
ROUNDTRIP_PREFIX = "mission-control/golden-thread/roundtrip-proof"
FIXED_ZIP_DT = (1980, 1, 1, 0, 0, 0)


class RoundTripError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _zip_bytes(parts: Dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(parts):
            info = zipfile.ZipInfo(name, FIXED_ZIP_DT)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, parts[name])
    return out.getvalue()


def _minimal_office(fmt: str) -> bytes:
    if fmt == "docx":
        main = "word/document.xml"
        main_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
        rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
        body = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>'
    elif fmt == "xlsx":
        main = "xl/workbook.xml"
        main_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
        rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
        body = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets/></workbook>'
    elif fmt == "pptx":
        main = "ppt/presentation.xml"
        main_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
        rel_type = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
        body = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldIdLst/></p:presentation>'
    else:
        raise RoundTripError(f"unsupported Office format: {fmt}")
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/{main}" ContentType="{main_type}"/>'
        '</Types>'
    ).encode()
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{rel_type}" Target="{main}"/>'
        '</Relationships>'
    ).encode()
    return _zip_bytes({"[Content_Types].xml": content_types, "_rels/.rels": rels, main: body})


def _normalize_office(path: Path) -> bytes:
    with zipfile.ZipFile(path, "r") as zf:
        parts = {name: zf.read(name) for name in zf.namelist()}
    return _zip_bytes(parts)


def build_bundle(truth: Dict[str, Any]) -> Tuple[Dict[str, bytes], Dict[str, Any]]:
    truth_digest = gt.digest(truth)
    text_family = rf.render_family(truth)
    files: Dict[str, bytes] = {
        "GOLDEN_THREAD_TRUTH.json": text_family["renditions"]["json"]["content"].encode("utf-8"),
        "GOLDEN_THREAD_TRUTH.yaml": text_family["renditions"]["yaml"]["content"].encode("utf-8"),
        "GOLDEN_THREAD_TRUTH.md": text_family["renditions"]["markdown"]["content"].encode("utf-8"),
        "GOLDEN_THREAD_TRUTH.html": text_family["renditions"]["html"]["content"].encode("utf-8"),
    }
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for fmt in ("docx", "xlsx", "pptx"):
            src = root / f"base.{fmt}"
            dst = root / f"GOLDEN_THREAD_TRUTH.{fmt}"
            src.write_bytes(_minimal_office(fmt))
            osc.inject(src, dst, truth)
            files[dst.name] = _normalize_office(dst)
    manifest = {
        "schema": "missioncontrol.golden_thread_roundtrip_bundle.v1",
        "canonical_truth_digest": truth_digest,
        "authority_transfer": False,
        "visual_fidelity_credit": False,
        "files": {
            name: {"sha256": sha256_bytes(data), "size": len(data)}
            for name, data in sorted(files.items())
        },
    }
    manifest["bundle_digest"] = gt.digest(manifest)
    return files, manifest


def verify_bundle(truth: Dict[str, Any], files: Dict[str, bytes]) -> Dict[str, Any]:
    expected = gt.digest(truth)
    results: Dict[str, Any] = {}
    mapping = {
        "GOLDEN_THREAD_TRUTH.json": "json",
        "GOLDEN_THREAD_TRUTH.yaml": "yaml",
        "GOLDEN_THREAD_TRUTH.md": "markdown",
        "GOLDEN_THREAD_TRUTH.html": "html",
    }
    for name, kind in mapping.items():
        observed = gt.digest(rf.extract_rendition(kind, files[name].decode("utf-8")))
        results[name] = {"status": "PASS" if observed == expected else "FAIL", "truth_digest": observed}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for fmt in ("docx", "xlsx", "pptx"):
            name = f"GOLDEN_THREAD_TRUTH.{fmt}"
            path = root / name
            path.write_bytes(files[name])
            observed = osc.extract(path)["truth_digest"]
            results[name] = {"status": "PASS" if observed == expected else "FAIL", "truth_digest": observed}
    status = "PASS" if all(v["status"] == "PASS" for v in results.values()) else "FAIL"
    return {
        "schema": "missioncontrol.golden_thread_roundtrip_bundle_verification.v1",
        "status": status,
        "canonical_truth_digest": expected,
        "rendition_count": len(results),
        "results": results,
        "visual_fidelity_credit": False,
        "authority_transfer": False,
    }


class GitHubGitData:
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.token = token
        self.base = f"https://api.github.com/repos/{repo}"

    def request(self, method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "GBOGEB-Golden-Thread-P2",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RoundTripError(f"GitHub API {method} {path} failed {exc.code}: {detail}") from exc

    def get_commit(self, sha: str) -> Dict[str, Any]:
        return self.request("GET", f"/git/commits/{sha}")

    def create_blob(self, data: bytes) -> str:
        out = self.request("POST", "/git/blobs", {"content": base64.b64encode(data).decode("ascii"), "encoding": "base64"})
        return out["sha"]

    def create_tree(self, base_tree: str, blobs: Dict[str, str]) -> str:
        entries = [
            {"path": f"{ROUNDTRIP_PREFIX}/{name}", "mode": "100644", "type": "blob", "sha": sha}
            for name, sha in sorted(blobs.items())
        ]
        return self.request("POST", "/git/trees", {"base_tree": base_tree, "tree": entries})["sha"]

    def create_commit(self, tree: str, parent: str, timestamp: str) -> str:
        who = {"name": "MissionControl Golden Thread", "email": "golden-thread@users.noreply.github.com", "date": timestamp}
        payload = {
            "message": "Golden Thread P2 deterministic rendition round-trip object",
            "tree": tree,
            "parents": [parent],
            "author": who,
            "committer": who,
        }
        return self.request("POST", "/git/commits", payload)["sha"]

    def get_tree(self, sha: str) -> Dict[str, Any]:
        return self.request("GET", f"/git/trees/{sha}?recursive=1")

    def get_blob(self, sha: str) -> bytes:
        obj = self.request("GET", f"/git/blobs/{sha}")
        if obj.get("encoding") != "base64":
            raise RoundTripError("GitHub blob encoding is not base64")
        return base64.b64decode(obj["content"].replace("\n", ""))


def remote_roundtrip(truth: Dict[str, Any], repo: str, source_sha: str, token: str, timestamp: str) -> Dict[str, Any]:
    files, local_manifest = build_bundle(truth)
    local_check = verify_bundle(truth, files)
    if local_check["status"] != "PASS":
        raise RoundTripError("local preflight rendition verification failed")

    api = GitHubGitData(repo, token)
    source_commit = api.get_commit(source_sha)
    source_tree_sha = source_commit["tree"]["sha"]
    blob_shas = {name: api.create_blob(data) for name, data in sorted(files.items())}
    tree_sha = api.create_tree(source_tree_sha, blob_shas)
    commit_sha = api.create_commit(tree_sha, source_sha, timestamp)

    remote_commit = api.get_commit(commit_sha)
    if remote_commit["tree"]["sha"] != tree_sha:
        raise RoundTripError("remote commit tree identity mismatch")
    remote_tree = api.get_tree(tree_sha)
    tree_map = {item["path"]: item for item in remote_tree.get("tree", [])}

    returned: Dict[str, bytes] = {}
    for name, expected_blob_sha in sorted(blob_shas.items()):
        path = f"{ROUNDTRIP_PREFIX}/{name}"
        item = tree_map.get(path)
        if not item or item.get("sha") != expected_blob_sha or item.get("type") != "blob":
            raise RoundTripError(f"tree/blob identity mismatch for {name}")
        returned[name] = api.get_blob(expected_blob_sha)
        if returned[name] != files[name]:
            raise RoundTripError(f"GitHub blob byte round-trip mismatch for {name}")

    remote_check = verify_bundle(truth, returned)
    if remote_check["status"] != "PASS":
        raise RoundTripError("remote post-roundtrip semantic verification failed")

    receipt = {
        "schema": SCHEMA,
        "status": "PASS",
        "repository": repo,
        "source_commit_sha": source_sha,
        "source_tree_sha": source_tree_sha,
        "roundtrip_commit_sha": commit_sha,
        "roundtrip_tree_sha": tree_sha,
        "blob_shas": blob_shas,
        "local_bundle_digest": local_manifest["bundle_digest"],
        "canonical_truth_digest": gt.digest(truth),
        "rendition_count": 7,
        "semantic_delta": 0,
        "unexplained_semantic_delta": 0,
        "ref_updated": False,
        "content_addressed_idempotency": True,
        "visual_fidelity_credit": False,
        "authority_transfer": False,
    }
    receipt["receipt_digest"] = gt.digest(receipt)
    return receipt


def _load_truth(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RoundTripError("truth must be a JSON object")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build-local")
    p.add_argument("truth", type=Path)
    p.add_argument("outdir", type=Path)
    p = sub.add_parser("roundtrip")
    p.add_argument("truth", type=Path)
    p.add_argument("--repo", required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--timestamp", required=True)
    p.add_argument("--token-env", default="GITHUB_TOKEN")
    p.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        truth = _load_truth(args.truth)
        if args.cmd == "build-local":
            files, manifest = build_bundle(truth)
            args.outdir.mkdir(parents=True, exist_ok=True)
            for name, data in files.items():
                (args.outdir / name).write_bytes(data)
            result = {"manifest": manifest, "verification": verify_bundle(truth, files)}
        else:
            token = os.environ.get(args.token_env)
            if not token:
                raise RoundTripError(f"missing token environment variable {args.token_env}")
            result = remote_roundtrip(truth, args.repo, args.source_sha, token, args.timestamp)
            if args.out:
                args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, RoundTripError, osc.OfficeSemanticError, gt.GoldenThreadError) as exc:
        print(f"FAIL: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
