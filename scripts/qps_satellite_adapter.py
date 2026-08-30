#!/usr/bin/env python3
"""Deterministic, metadata-only adapter for QPS satellite federation.

This utility deliberately does not dispatch ABACUS/CODEX workflows and does not
modify any engineering SSOT. It projects a legacy processing manifest into a
bounded QPS child intake envelope and can import sanitized child feedback as
regression-learning data for the satellite repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ENVELOPE_SCHEMA = "qps-satellite-envelope/v0.1"
FEEDBACK_SCHEMA = "qps-satellite-feedback/v0.1"
LEARNING_SCHEMA = "qps-satellite-learning/v0.1"
SATELLITE_REPOSITORY = "GBOGEB/pipeline-automation-hub"
QPS_REPOSITORY = "GBOGEB/cryoplant-project"
ALLOWED_DISPOSITIONS = {"ACCEPT", "REJECT", "DEFER"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class AdapterError(ValueError):
    """Raised when an adapter payload violates the bounded contract."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stable_id(source_path: str, source_sha256: str) -> str:
    seed = f"{SATELLITE_REPOSITORY}|{source_path}|{source_sha256}".encode("utf-8")
    return f"SAT-{hashlib.sha256(seed).hexdigest()[:16]}"


def _normalize_cross_references(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    refs: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        reference = str(item.get("reference", "")).strip()
        if not reference:
            continue
        refs.append({
            "reference": reference,
            "context": str(item.get("context", "")).strip(),
            "type": str(item.get("type", "unknown")).strip() or "unknown",
        })
    return sorted(refs, key=lambda x: (x["reference"], x["context"], x["type"]))


def export_manifest(manifest_path: Path, output_path: Path, source_ref: str, source_sha: str) -> dict[str, Any]:
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw.decode("utf-8"))
    if not isinstance(manifest, dict):
        raise AdapterError("processing manifest must be a JSON object")
    summary = manifest.get("processing_summary")
    if not isinstance(summary, dict) or not isinstance(summary.get("files_processed"), list):
        raise AdapterError("processing_summary.files_processed must be an array")

    artifacts: list[dict[str, Any]] = []
    for record in summary["files_processed"]:
        if not isinstance(record, dict):
            continue
        metadata = record.get("metadata")
        if not isinstance(metadata, dict):
            continue
        source_path = str(metadata.get("original_filename") or record.get("filename") or "").strip()
        source_hash = str(metadata.get("file_hash", "")).lower().strip()
        if not source_path or not HEX64.fullmatch(source_hash):
            continue
        artifacts.append({
            "stable_id": _stable_id(source_path, source_hash),
            "source_path": source_path,
            "source_sha256": source_hash,
            "artifact_type": str(metadata.get("file_type", "UNKNOWN")).upper(),
            "authority_class": "SATELLITE_METADATA_ADVISORY",
            "category": str(metadata.get("category", "UNKNOWN")),
            "priority": str(metadata.get("priority", "UNSET")),
            "cross_references": _normalize_cross_references(record.get("cross_references")),
            "validation_status": str(record.get("processing_status", "UNKNOWN")),
            "generated_from": "PROCESSING_MANIFEST.json",
        })
    artifacts.sort(key=lambda x: (x["source_path"].lower(), x["source_sha256"]))

    payload: dict[str, Any] = {
        "schema": ENVELOPE_SCHEMA,
        "correlation_id": "QPS-SAT-W01-PIPELINE-AUTOMATION-HUB",
        "source": {
            "repository": SATELLITE_REPOSITORY,
            "ref": source_ref,
            "sha": source_sha,
            "manifest_path": manifest_path.name,
            "manifest_sha256": _sha256_bytes(raw),
        },
        "authority": "SATELLITE_METADATA_ADVISORY",
        "confidential": False,
        "artifact_records": artifacts,
        "routing": {
            "disposition_owner": QPS_REPOSITORY,
            "analysis_parent": "GBOGEB/ABACUS",
            "exchange_parent": "GBOGEB/CODEX",
            "direct_parent_dispatch_allowed": False,
        },
        "governance": {
            "engineering_ssot_mutation_allowed": False,
            "parent_findings_are_candidates_only": True,
            "child_disposition_required": True,
            "allowed_child_dispositions": sorted(ALLOWED_DISPOSITIONS),
        },
    }
    payload["bridge_id"] = _sha256_bytes(_canonical_bytes(payload))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def import_feedback(feedback_path: Path, output_path: Path) -> dict[str, Any]:
    feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
    if not isinstance(feedback, dict) or feedback.get("schema") != FEEDBACK_SCHEMA:
        raise AdapterError(f"feedback schema must be {FEEDBACK_SCHEMA}")
    source = feedback.get("source")
    if not isinstance(source, dict) or source.get("repository") != QPS_REPOSITORY:
        raise AdapterError("feedback source must be GBOGEB/cryoplant-project")
    if feedback.get("target_repository") != SATELLITE_REPOSITORY:
        raise AdapterError("feedback target_repository does not match this satellite")
    findings = feedback.get("findings")
    if not isinstance(findings, list):
        raise AdapterError("findings must be an array")

    learnings: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise AdapterError("each finding must be an object")
        disposition = finding.get("disposition")
        if disposition not in ALLOWED_DISPOSITIONS:
            raise AdapterError(f"invalid disposition: {disposition!r}")
        if disposition != "ACCEPT":
            continue
        if finding.get("reusable_learning") is not True:
            continue
        if finding.get("confidential") is not False:
            raise AdapterError("accepted reusable learning must explicitly declare confidential=false")
        learnings.append({
            "finding_id": str(finding.get("finding_id", "")),
            "learning_type": str(finding.get("learning_type", "REGRESSION")),
            "summary": str(finding.get("summary", "")),
            "source_reference": str(finding.get("source_reference", "")),
            "authority": "REGRESSION_LEARNING_ONLY",
            "qps_disposition": "ACCEPT",
        })

    learning_payload: dict[str, Any] = {
        "schema": LEARNING_SCHEMA,
        "source": source,
        "target_repository": SATELLITE_REPOSITORY,
        "correlation_id": str(feedback.get("correlation_id", "")),
        "authority": "REGRESSION_LEARNING_ONLY",
        "engineering_ssot_mutation_allowed": False,
        "learnings": sorted(learnings, key=lambda x: x["finding_id"]),
    }
    learning_payload["learning_sha256"] = _sha256_bytes(_canonical_bytes(learning_payload))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(learning_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return learning_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="project PROCESSING_MANIFEST.json into a QPS child intake envelope")
    export.add_argument("--manifest", default="PROCESSING_MANIFEST.json")
    export.add_argument("--output", required=True)
    export.add_argument("--source-ref", default="master")
    export.add_argument("--source-sha", default="UNBOUND")

    feedback = sub.add_parser("import-feedback", help="import sanitized QPS child feedback as regression learning")
    feedback.add_argument("--feedback", required=True)
    feedback.add_argument("--output", required=True)

    args = parser.parse_args()
    if args.command == "export":
        result = export_manifest(Path(args.manifest), Path(args.output), args.source_ref, args.source_sha)
    else:
        result = import_feedback(Path(args.feedback), Path(args.output))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
