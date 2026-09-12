#!/usr/bin/env python3
"""Run the bounded legacy PPTX metadata pipeline.

M09 boundary: this runner validates PPTX packages and emits metadata/hash/template
twins. It does not claim slide-content extraction, PDF conversion, or semantic
cross-reference extraction.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parent
DEFAULT_INPUT_DIR = REPO_ROOT / "app" / "public" / "master_input"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "app" / "public" / "outputs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded legacy metadata-only PPTX pipeline")
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
                "authority": "METADATA_ONLY_NOT_DOCUMENT_TRUTH",
                "summary_path": str(summary_path.resolve()),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return summary.get("failed", 0) == 0


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    print("Pipeline Automation Hub - bounded legacy document metadata pipeline")
    print(f"input={input_dir.resolve()}")
    print(f"output={output_dir.resolve()}")
    if not run_ppt_processing(input_dir, output_dir):
        return 2
    return 0 if summarize(output_dir) else 3


if __name__ == "__main__":
    raise SystemExit(main())
