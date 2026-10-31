#!/usr/bin/env python3
"""JQ-04: read-only, exact-blob source -> view selection validation.

This is not an editor, SyncTeX substitute, PDF-coordinate extractor, admission
predicate, or new source of CI timing/graph authority. It validates selected
source objects and the exact existing HTML renderer bytes without network I/O.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MANIFEST = HERE / "POINTER_MAP_v1.json"
NAV = HERE / "index.html"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED = {
    "docs/ci-spine/LOGICAL_BUNDLE_DAG_v1.json",
    "docs/ci-spine/RUN_TIMING_SAMPLES_20261028.json",
    "docs/ci-spine/explorer.html",
}
VIEWS = {"graph": "dag", "sipoc": "sipoc-body", "timing": "timing-rows"}
# The explorer router only shows a bundle on graph/SIPOC and a run on timing; any
# other lens silently falls back to bundle B05, so it is not a pointer to the object.
KIND_LENSES = {"bundle": {"graph", "sipoc"}, "run": {"timing"}}
# A branch commit SHA is not a stable binding: rebases and squash merges orphan it.
# Pointers bind content (git blob OIDs) and are checked against the checked-out tree.
MUTABLE_COMMIT_FIELDS = ("source_commit", "head_sha", "output_commit")


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError("CI_SPINE_POINTER_FIRST_RED:" + code)


def file_bytes(path: str, root: Path = ROOT) -> bytes:
    require(isinstance(path, str) and path in ALLOWED, "PATH_NOT_ALLOWLISTED")
    p = (root / path).resolve()
    require(p.is_relative_to(root.resolve()) and p.is_file(), "SOURCE_MISSING_OR_ESCAPE")
    return p.read_bytes()


def git_blob_oid(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def git_out(*args: str) -> str:
    """Run a read-only git query without a shell; any failure is a first red."""
    try:
        proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              check=False, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("CI_SPINE_POINTER_FIRST_RED:UNRESOLVED_CHECKOUT") from exc
    require(proc.returncode == 0, "UNRESOLVED_CHECKOUT")
    return proc.stdout.decode("ascii").strip()


def checkout_head() -> str:
    head = git_out("rev-parse", "--verify", "HEAD")
    require(SHA40.fullmatch(head) is not None, "UNRESOLVED_CHECKOUT")
    return head


def tree_blob(path: str) -> str:
    """Blob OID committed at the checked-out HEAD for an allowlisted path."""
    require(path in ALLOWED, "UNTRUSTED_COMMIT_PATH")
    return git_out("rev-parse", "--verify", "HEAD:" + path)


class Anchors(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.links = set()
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("href"):
            self.links.add(attrs["href"])
        if tag == "script":
            self.scripts.append(attrs.get("src"))


def json_pointer(doc, ptr: str):
    """Support only deterministic array index pointers from the audited source files."""
    require(isinstance(ptr, str) and re.fullmatch(r"/(nodes|runs)/[0-9]+", ptr) is not None,
            "INVALID_JSON_POINTER")
    collection, idx = ptr[1:].split("/")
    require(isinstance(doc, dict) and isinstance(doc.get(collection), list), "POINTER_NO_COLLECTION")
    index = int(idx)
    require(index < len(doc[collection]), "POINTER_OUT_OF_RANGE")
    return doc[collection][index]


def validate(doc: dict, root: Path = ROOT) -> dict:
    require(isinstance(doc, dict) and doc.get("schema") == "gbo.ci-spine.pointer-map.v1",
            "SCHEMA")
    frozen = doc.get("catalog_snapshot_commit")
    viewer = doc.get("viewer") or {}
    rows = doc.get("pointers")
    require(isinstance(frozen, str) and SHA40.fullmatch(frozen) is not None, "HEAD_IDENTITY")
    require(not any(k in d for d in [doc, viewer, *(rows if isinstance(rows, list) else [])]
                    for k in MUTABLE_COMMIT_FIELDS), "MUTABLE_COMMIT_BINDING")
    head = checkout_head()
    require(doc.get("repository") == "GBOGEB/pipeline-automation-hub"
            and viewer.get("authority") == "FROZEN_ADVISORY", "NO_APPROVAL_AUTHORITY")
    vb = file_bytes(viewer.get("path"), root)
    require(SHA40.fullmatch(str(viewer.get("blob_oid"))) is not None
            and git_blob_oid(vb) == viewer["blob_oid"], "OUTPUT_BLOB_STALE")
    require(SHA256.fullmatch(str(viewer.get("sha256"))) is not None
            and hashlib.sha256(vb).hexdigest() == viewer["sha256"], "OUTPUT_SHA256_STALE")
    require(tree_blob(viewer["path"]) == viewer["blob_oid"], "OUTPUT_NOT_AT_CHECKOUT")
    require(viewer.get("build_workflow_run_id") is None
            and viewer.get("build_receipt_state") == "NATIVE_EXACT_HEAD_RUN_PENDING",
            "MISSING_OR_FALSE_RENDER_RECEIPT")
    html_text = vb.decode("utf-8")
    anchors = Anchors()
    anchors.feed(html_text)
    require(all(x in anchors.ids for x in VIEWS.values()), "MISSING_HTML_ANCHORS")
    require("function restore()" in html_text and "function setSelected(" in html_text,
            "MISSING_ROUTING_CONTRACT")
    require(isinstance(rows, list) and len(rows) == 3, "POINTER_POPULATION")
    require(len({r["id"] for r in rows}) == len(rows), "DUPLICATE_POINTER")
    source_cache = {}
    result = []
    for row in rows:
        source, target = row.get("source") or {}, row.get("output") or {}
        path = source.get("path")
        raw = file_bytes(path, root)
        require(SHA40.fullmatch(str(source.get("blob_oid"))) is not None
                and git_blob_oid(raw) == source["blob_oid"], "SOURCE_BLOB_STALE")
        require(tree_blob(path) == source["blob_oid"], "SOURCE_NOT_AT_CHECKOUT")
        if path not in source_cache:
            source_cache[path] = json.loads(raw)
        obj = json_pointer(source_cache[path], source.get("json_pointer"))
        oid = source.get("object_id")
        if path.endswith("LOGICAL_BUNDLE_DAG_v1.json"):
            require(isinstance(obj, dict) and oid == obj.get("id"), "OBJECT_SEMANTIC_MISMATCH")
            require(target.get("kind") == "bundle"
                    and target.get("selection_id") == obj.get("short_id"), "BUNDLE_ROUTE_MISMATCH")
        else:
            require(isinstance(obj, dict) and isinstance(obj.get("run_id"), int)
                    and oid == "run:" + str(obj["run_id"]), "RUN_SEMANTIC_MISMATCH")
            require(target.get("kind") == "run"
                    and str(target.get("selection_id")) == str(obj["run_id"]), "RUN_ROUTE_MISMATCH")
        require(row.get("state") == "CANDIDATE_PENDING_NATIVE_DOV"
                and row.get("authority") == "ADVISORY"
                and row.get("precision") == "VIEW_SELECTION", "CLAIMED_EXACTNESS_OR_AUTHORITY")
        require(target.get("path") == viewer["path"]
                and target.get("blob_oid") == viewer["blob_oid"]
                and target.get("sha256") == viewer["sha256"], "MISMATCHED_OUTPUT")
        lens = target.get("lens")
        require(lens in VIEWS and target.get("dom_id") == VIEWS[lens]
                and target["dom_id"] in anchors.ids, "MISSING_VIEW_ANCHOR")
        require(lens in KIND_LENSES.get(target.get("kind"), ()), "LENS_KIND_MISMATCH")
        href = target.get("href")
        require(isinstance(href, str), "NO_NAVIGATION")
        url = urlsplit(href)
        require(url.path == "../explorer.html" and not url.scheme and not url.netloc
                and not url.query and not url.username, "UNTRUSTED_OUTPUT_URL")
        args = parse_qs(url.fragment, keep_blank_values=True, strict_parsing=True)
        expected = {"lens": [lens], "kind": [target["kind"]],
                    "id": [str(target["selection_id"])]}
        require(args == expected, "WRONG_SELECTION_HASH")
        result.append({"id": row["id"], "precision": "VIEW_SELECTION",
                       "source_object": oid, "output_anchor": target["dom_id"],
                       "source_blob_oid": source["blob_oid"], "output_sha256": target["sha256"],
                       "state": "VALIDATED_AGAINST_PINNED_BYTES"})
    # Small static companion UI is a navigation projection, not a second metric owner.
    # It must expose only links from the fully validated map and contain no scripts.
    require(NAV.is_file(), "NAV_PAGE_MISSING")
    nav_bytes = NAV.read_bytes()
    nav = Anchors()
    nav.feed(nav_bytes.decode("utf-8"))
    require(not nav.scripts and b"script-src 'none'" in nav_bytes
            and b"connect-src 'none'" in nav_bytes, "NAV_REMOTE_EXECUTION")
    require(all(row["output"]["href"] in nav.links for row in rows),
            "NAV_BROKEN_POINTER_LINK")
    approved_links = {"../explorer.html", "../README.md",
                      "../JACQUARD_CROSSWALK.md"}
    approved_links.update(row["output"]["href"] for row in rows)
    approved_links.update(source_href(row["source"]["path"]) for row in rows)
    require(nav.links <= approved_links, "NAV_UNDECLARED_LINK")
    require(nav_bindings(nav_bytes.decode("utf-8")) == declared_bindings(doc),
            "NAV_STALE_PROVENANCE")
    require("FROZEN" in nav_bytes.decode("utf-8")
            and "0 PDF RECTANGLES VERIFIED" in nav_bytes.decode("utf-8"),
            "NAV_FALSE_AUTHORITY")
    pending = doc.get("pending")
    require(isinstance(pending, list) and len(pending) == 1, "UNVERIFIED_POPULATION")
    for p in pending:
        require(p.get("kind") == "PDF_PAGE_RECT_OR_OCG"
                and p.get("state") == "UNMAPPED_NO_VERIFIED_BINARY"
                and p.get("output") is None and p.get("href") is None
                and p.get("precision") == "UNKNOWN", "FALSE_PDF_PROVENANCE")
    return {"schema": "gbo.ci-spine.pointer-qualification.v1",
            "verdict": "SOURCE_BOUND_VIEW_SELECTION_ONLY",
            "head_sha": head, "catalog_snapshot_sha": frozen,
            "viewer_sha256": viewer["sha256"], "qualifying_run_id": viewer["build_workflow_run_id"],
            "mapped": result, "pdf_rectangles_verified": 0,
            "unknown_pdf_pointers": len(pending), "merge_authorized": False}


def source_href(path: str) -> str:
    """Atlas source links stay local, so they exist wherever the atlas is opened."""
    return "../" + path.rsplit("/", 1)[-1]


def nav_bindings(text: str) -> dict:
    """Every digest, blob OID and run number the atlas displays."""
    return {"sha256": set(re.findall(r"\b[0-9a-f]{64}\b", text)),
            "oid": set(re.findall(r"\b[0-9a-f]{40}\b", text)),
            "run": set(re.findall(r"\b[0-9]{9,}\b", text))}


def declared_bindings(doc: dict) -> dict:
    """The only values the atlas may display; anything else is stale metadata."""
    build = doc["viewer"].get("build_workflow_run_id")
    return {"sha256": {doc["viewer"]["sha256"]},
            "oid": {r["source"]["blob_oid"] for r in doc["pointers"]}
                   | {doc["catalog_snapshot_commit"]},
            "run": {str(r["output"]["selection_id"]) for r in doc["pointers"]
                    if r["output"]["kind"] == "run"} | ({str(build)} if build else set())}


def rebind(doc: dict, nav_text: str, root: Path = ROOT):
    """Re-pin content digests from current bytes after a deterministic explorer rebuild.

    Only content identities move. Routes, claims and states are unchanged, and the
    result must still pass validate() at the committed head before it qualifies.
    """
    doc = json.loads(json.dumps(doc))
    viewer = doc["viewer"]
    vb = file_bytes(viewer["path"], root)
    moved = {viewer["sha256"]: hashlib.sha256(vb).hexdigest(),
             viewer["blob_oid"]: git_blob_oid(vb)}
    viewer["blob_oid"], viewer["sha256"] = git_blob_oid(vb), hashlib.sha256(vb).hexdigest()
    for row in doc["pointers"]:
        new_oid = git_blob_oid(file_bytes(row["source"]["path"], root))
        moved[row["source"]["blob_oid"]] = new_oid
        row["source"]["blob_oid"] = new_oid
        row["output"]["blob_oid"], row["output"]["sha256"] = viewer["blob_oid"], viewer["sha256"]
    for before, after in moved.items():
        nav_text = nav_text.replace(before, after)
    return doc, nav_text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--rebind", action="store_true",
                    help="re-pin manifest and atlas digests from current bytes (no validation)")
    a = ap.parse_args(argv)
    doc = json.loads(a.manifest.read_text("utf-8"))
    if a.rebind:
        doc, nav_text = rebind(doc, NAV.read_text("utf-8"))
        a.manifest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
        NAV.write_text(nav_text, encoding="utf-8", newline="\n")
        print("CI_SPINE_POINTER_REBOUND: commit, then validate at the new head")
        return 0
    report = validate(doc)
    if a.out is not None:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in report.items() if k != "mapped"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
