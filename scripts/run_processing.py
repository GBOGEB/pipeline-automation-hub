#!/usr/bin/env python3
"""Run the bounded legacy PPTX metadata pipeline plus recursive-build indexing.

M09 boundary: the PPTX processor validates packages and emits metadata/hash/template
views. The recursive-build phase indexes only those bounded outputs. Neither phase
claims slide-content extraction, semantic cross-reference truth, or engineering
authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
DEFAULT_INPUT_DIR = REPO_ROOT / "app" / "public" / "master_input"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "app" / "public" / "outputs"
AUTHORITY = "METADATA_ONLY_NOT_DOCUMENT_TRUTH"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run bounded PPTX metadata processing plus canonical recursive-build indexing"
    )
    parser.add_argument(
        "--input-dir",
        default=os.environ.get("PIPELINE_INPUT_DIR", str(DEFAULT_INPUT_DIR)),
        help="PPTX input directory",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("PIPELINE_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)),
        help="Output directory",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_ppt_processing(input_dir: Path, output_dir: Path) -> bool:
    print("Phase 1: bounded legacy PPTX metadata processor")
    result = subprocess.run(
        [
            sys.executable,
            str(CURRENT_DIR / "ppt_processor.py"),
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        return False
    return True


def summarize(output_dir: Path) -> bool:
    summary_path = output_dir / "processing_summary.json"
    if not summary_path.exists():
        print(f"Summary missing: {summary_path}", file=sys.stderr)
        return False
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "processing_scope": summary.get("processing_scope"),
                "total_files": summary.get("total_files", 0),
                "successful": summary.get("successful", 0),
                "failed": summary.get("failed", 0),
                "candidate_cross_references": len(summary.get("cross_references_global", [])),
                "authority": AUTHORITY,
                "summary_path": str(summary_path.resolve()),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return summary.get("failed", 0) == 0


def run_recursive_build(output_dir: Path) -> Path | None:
    """Execute the canonical recursive-build engine after metadata processing passes."""
    print("Phase 2: canonical recursive-build indexing and lineage")
    result = subprocess.run(
        [
            sys.executable,
            str(CURRENT_DIR / "Recursive_Build_Master.py"),
            "--outputs-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        return None

    receipt = output_dir / "recursive_build" / "build_receipt.json"
    if not receipt.exists():
        print(f"Recursive-build receipt missing: {receipt}", file=sys.stderr)
        return None
    return receipt


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def write_pipeline_receipt(output_dir: Path, recursive_receipt_path: Path) -> Path | None:
    """Bind the two bounded phases through hashes without creating new source authority."""
    summary_path = output_dir / "processing_summary.json"
    if not summary_path.exists() or not recursive_receipt_path.exists():
        print("Cannot write pipeline receipt: required phase receipt missing", file=sys.stderr)
        return None

    try:
        summary = _load_json(summary_path)
        recursive = _load_json(recursive_receipt_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Cannot read phase receipt: {exc}", file=sys.stderr)
        return None

    metadata_ok = summary.get("failed", 0) == 0
    recursive_status = str(recursive.get("status", ""))
    recursive_ok = recursive_status.startswith("PASS")
    generated_at = recursive.get("generated_at")

    payload = {
        "schema": "pipeline_automation_hub.pipeline_run_receipt.v1",
        "generated_at": generated_at,
        "authority": AUTHORITY,
        "status": "PASS" if metadata_ok and recursive_ok else "FAIL",
        "phases": {
            "metadata": {
                "status": "PASS" if metadata_ok else "FAIL",
                "path": str(summary_path.relative_to(output_dir)),
                "sha256": sha256_file(summary_path),
                "total_files": summary.get("total_files", 0),
                "successful": summary.get("successful", 0),
                "failed": summary.get("failed", 0),
            },
            "recursive_build": {
                "status": recursive_status,
                "path": str(recursive_receipt_path.relative_to(output_dir)),
                "sha256": sha256_file(recursive_receipt_path),
                "record_count": recursive.get("record_count", 0),
            },
        },
        "authority_guardrail": (
            "Hashes and PASS state prove execution/provenance only; they do not create "
            "engineering, compliance, procurement, acceptance, or document-truth authority."
        ),
    }

    target = output_dir / "pipeline_run_receipt.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    print("Pipeline Automation Hub - bounded metadata + recursive-build pipeline")
    print(f"input={input_dir.resolve()}")
    print(f"output={output_dir.resolve()}")

    if not run_ppt_processing(input_dir, output_dir):
        return 2
    if not summarize(output_dir):
        return 3

    recursive_receipt = run_recursive_build(output_dir)
    if recursive_receipt is None:
        return 4

    pipeline_receipt = write_pipeline_receipt(output_dir, recursive_receipt)
    if pipeline_receipt is None:
        return 5

    print(
        json.dumps(
            {
                "status": "PASS",
                "authority": AUTHORITY,
                "pipeline_receipt": str(pipeline_receipt.resolve()),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
