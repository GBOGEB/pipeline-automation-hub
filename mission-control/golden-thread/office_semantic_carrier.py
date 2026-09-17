#!/usr/bin/env python3
"""OOXML semantic carrier for Golden Thread truth.

DOCX, XLSX and PPTX are OPC/ZIP packages. This module embeds a canonical
Golden Thread truth object and manifest into the package, then extracts and
verifies them independently of volatile Office ZIP/package metadata.

Scope: semantic identity only. This does not claim visual/render equivalence.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple
from xml.etree import ElementTree as ET

SCHEMA = "missioncontrol.golden_thread_office_semantic_carrier.v1"
TRUTH_PART = "customXml/goldenThread/truth.json"
MANIFEST_PART = "customXml/goldenThread/manifest.json"
CONTENT_TYPES = "[Content_Types].xml"
ROOT_RELS = "_rels/.rels"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_TYPE_TRUTH = "urn:gbogeb:golden-thread:relationship:truth"
REL_TYPE_MANIFEST = "urn:gbogeb:golden-thread:relationship:manifest"
FORMAT_MAIN_PART = {
    ".docx": "word/document.xml",
    ".xlsx": "xl/workbook.xml",
    ".pptx": "ppt/presentation.xml",
}


class OfficeSemanticError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def truth_bytes(truth: Dict[str, Any]) -> bytes:
    if not isinstance(truth, dict):
        raise OfficeSemanticError("truth must be an object")
    return canonical_json(truth).encode("utf-8")


def truth_digest(truth: Dict[str, Any]) -> str:
    return sha256_bytes(truth_bytes(truth))


def detect_format(path: Path) -> Tuple[str, str]:
    ext = path.suffix.lower()
    if ext not in FORMAT_MAIN_PART:
        raise OfficeSemanticError("supported Office formats are .docx, .xlsx and .pptx")
    return ext[1:], FORMAT_MAIN_PART[ext]


def _read_package(path: Path) -> Dict[str, bytes]:
    if not zipfile.is_zipfile(path):
        raise OfficeSemanticError(f"not an OOXML ZIP package: {path}")
    with zipfile.ZipFile(path, "r") as zf:
        parts = {name: zf.read(name) for name in zf.namelist()}
    fmt, main_part = detect_format(path)
    for required in (CONTENT_TYPES, ROOT_RELS, main_part):
        if required not in parts:
            raise OfficeSemanticError(f"{fmt}: missing required package part {required}")
    return parts


def _xml_root(data: bytes, expected_local_name: str) -> ET.Element:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise OfficeSemanticError(f"invalid XML in package control part: {exc}") from exc
    if root.tag.split("}")[-1] != expected_local_name:
        raise OfficeSemanticError(f"unexpected XML root {root.tag}")
    return root


def _serialize_xml(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _update_content_types(data: bytes) -> bytes:
    root = _xml_root(data, "Types")
    ns = f"{{{CONTENT_TYPES_NS}}}"
    wanted = {
        "/" + TRUTH_PART: "application/json",
        "/" + MANIFEST_PART: "application/json",
    }
    existing = {
        child.attrib.get("PartName"): child
        for child in root.findall(f"{ns}Override")
    }
    for part_name, content_type in wanted.items():
        node = existing.get(part_name)
        if node is None:
            ET.SubElement(root, f"{ns}Override", PartName=part_name, ContentType=content_type)
        else:
            node.set("ContentType", content_type)
    return _serialize_xml(root)


def _update_root_rels(data: bytes) -> bytes:
    root = _xml_root(data, "Relationships")
    ns = f"{{{RELS_NS}}}"
    rels = list(root.findall(f"{ns}Relationship"))
    for rel in rels:
        if rel.attrib.get("Type") in {REL_TYPE_TRUTH, REL_TYPE_MANIFEST}:
            root.remove(rel)
    used_ids = {rel.attrib.get("Id") for rel in root.findall(f"{ns}Relationship")}

    def next_id(base: str) -> str:
        if base not in used_ids:
            used_ids.add(base)
            return base
        i = 2
        while f"{base}{i}" in used_ids:
            i += 1
        value = f"{base}{i}"
        used_ids.add(value)
        return value

    ET.SubElement(
        root,
        f"{ns}Relationship",
        Id=next_id("rIdGoldenThreadTruth"),
        Type=REL_TYPE_TRUTH,
        Target=TRUTH_PART,
    )
    ET.SubElement(
        root,
        f"{ns}Relationship",
        Id=next_id("rIdGoldenThreadManifest"),
        Type=REL_TYPE_MANIFEST,
        Target=MANIFEST_PART,
    )
    return _serialize_xml(root)


def _manifest(truth: Dict[str, Any], fmt: str, parent_truth_digest: Optional[str]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema": SCHEMA,
        "format": fmt,
        "truth_part": TRUTH_PART,
        "truth_digest": truth_digest(truth),
        "semantic_identity_excludes": [
            "zip_entry_order",
            "zip_timestamps",
            "compression_method",
            "office_application_metadata",
            "render_layout_metadata_not_in_truth",
        ],
        "visual_fidelity_credit": False,
        "authority_transfer": False,
    }
    if parent_truth_digest is not None:
        payload["parent_truth_digest"] = parent_truth_digest
    payload["manifest_digest"] = sha256_bytes(canonical_json(payload).encode("utf-8"))
    return payload


def extract(path: Path) -> Dict[str, Any]:
    parts = _read_package(path)
    fmt, _ = detect_format(path)
    if TRUTH_PART not in parts or MANIFEST_PART not in parts:
        raise OfficeSemanticError("Golden Thread semantic carrier parts are missing")
    try:
        truth = json.loads(parts[TRUTH_PART].decode("utf-8"))
        manifest = json.loads(parts[MANIFEST_PART].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfficeSemanticError(f"invalid Golden Thread JSON part: {exc}") from exc
    if not isinstance(truth, dict) or not isinstance(manifest, dict):
        raise OfficeSemanticError("Golden Thread truth/manifest must be objects")
    if manifest.get("schema") != SCHEMA:
        raise OfficeSemanticError("semantic carrier schema mismatch")
    if manifest.get("format") != fmt:
        raise OfficeSemanticError("semantic carrier format mismatch")
    if manifest.get("authority_transfer") is not False:
        raise OfficeSemanticError("semantic carrier authority_transfer must remain false")
    if manifest.get("visual_fidelity_credit") is not False:
        raise OfficeSemanticError("semantic carrier may not grant visual fidelity credit")
    observed_truth_digest = truth_digest(truth)
    if manifest.get("truth_digest") != observed_truth_digest:
        raise OfficeSemanticError("truth digest mismatch")
    check = copy.deepcopy(manifest)
    claimed_manifest_digest = check.pop("manifest_digest", None)
    if claimed_manifest_digest != sha256_bytes(canonical_json(check).encode("utf-8")):
        raise OfficeSemanticError("manifest digest mismatch")
    return {
        "schema": "missioncontrol.golden_thread_office_semantic_extraction.v1",
        "format": fmt,
        "truth": truth,
        "truth_digest": observed_truth_digest,
        "manifest": manifest,
        "authority_transfer": False,
    }


def inject(
    source: Path,
    destination: Path,
    truth: Dict[str, Any],
    *,
    parent_truth_digest: Optional[str] = None,
) -> Dict[str, Any]:
    if source.resolve() == destination.resolve():
        raise OfficeSemanticError("source and destination must be different paths")
    parts = _read_package(source)
    fmt, _ = detect_format(source)
    if destination.suffix.lower() != source.suffix.lower():
        raise OfficeSemanticError("destination extension must match source Office format")

    new_truth_digest = truth_digest(truth)
    if TRUTH_PART in parts and MANIFEST_PART in parts:
        current = extract(source)
        if current["truth_digest"] == new_truth_digest and current["truth"] == truth:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            return {
                "status": "UNCHANGED_REPLAY",
                "format": fmt,
                "truth_digest": new_truth_digest,
                "package_sha256": sha256_bytes(destination.read_bytes()),
                "authority_transfer": False,
            }
        if parent_truth_digest is None:
            parent_truth_digest = current["truth_digest"]

    manifest = _manifest(truth, fmt, parent_truth_digest)
    replacements = {
        CONTENT_TYPES: _update_content_types(parts[CONTENT_TYPES]),
        ROOT_RELS: _update_root_rels(parts[ROOT_RELS]),
        TRUTH_PART: truth_bytes(truth),
        MANIFEST_PART: canonical_json(manifest).encode("utf-8"),
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for name, data in parts.items():
            if name in replacements:
                continue
            out.writestr(name, data)
        for name in (CONTENT_TYPES, ROOT_RELS, TRUTH_PART, MANIFEST_PART):
            out.writestr(name, replacements[name])

    verified = extract(destination)
    if verified["truth_digest"] != new_truth_digest or verified["truth"] != truth:
        raise OfficeSemanticError("post-injection semantic verification failed")
    return {
        "status": "WRITTEN",
        "format": fmt,
        "truth_digest": new_truth_digest,
        "parent_truth_digest": parent_truth_digest,
        "package_sha256": sha256_bytes(destination.read_bytes()),
        "authority_transfer": False,
    }


def verify(path: Path, expected_truth: Dict[str, Any]) -> Dict[str, Any]:
    extracted = extract(path)
    expected_digest = truth_digest(expected_truth)
    if extracted["truth_digest"] != expected_digest or extracted["truth"] != expected_truth:
        raise OfficeSemanticError("Office semantic delta detected")
    return {
        "schema": "missioncontrol.golden_thread_office_semantic_verification.v1",
        "status": "PASS",
        "format": extracted["format"],
        "truth_digest": expected_digest,
        "visual_fidelity_credit": False,
        "authority_transfer": False,
    }


def _load_truth(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OfficeSemanticError("truth JSON must be an object")
    return value


def _dump(value: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inject")
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path)
    p.add_argument("truth", type=Path)
    p.add_argument("--parent-truth-digest")

    p = sub.add_parser("extract")
    p.add_argument("office_file", type=Path)

    p = sub.add_parser("verify")
    p.add_argument("office_file", type=Path)
    p.add_argument("truth", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "inject":
            result = inject(
                args.source,
                args.destination,
                _load_truth(args.truth),
                parent_truth_digest=args.parent_truth_digest,
            )
        elif args.command == "extract":
            result = extract(args.office_file)
        else:
            result = verify(args.office_file, _load_truth(args.truth))
        _dump(result)
        return 0
    except (OfficeSemanticError, OSError, zipfile.BadZipFile) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
