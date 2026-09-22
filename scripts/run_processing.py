#!/usr/bin/env python3
"""Run the bounded MAIN pipeline with optional Excel schedule-table ingestion.

The legacy PPTX path remains metadata-only and feeds canonical recursive-build
indexing. When explicitly requested, the governed Excel schedule engine runs as an
additional bounded phase and its manifest is hash-bound into the joined pipeline
receipt. No phase transfers engineering/document authority.
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
DEFAULT_EXCEL_OUTPUT_ROOT = REPO_ROOT
EXCEL_ENGINE = REPO_ROOT / "excel_schedule_engine" / "src" / "excel_schedule_engine.py"
AUTHORITY = "METADATA_ONLY_NOT_DOCUMENT_TRUTH"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run bounded PPTX metadata processing, canonical recursive-build indexing, "
            "and optional Excel schedule-table ingestion"
        )
    )
    parser.add_argument(
        "--input-dir",
        default=os.environ.get("PIPELINE_INPUT_DIR", str(DEFAULT_INPUT_DIR)),
        help="PPTX input directory",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("PIPELINE_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)),
        help="PPTX/recursive output directory",
    )
    parser.add_argument(
        "--excel-input",
        default=os.environ.get("PIPELINE_EXCEL_INPUT"),
        help="Optional .xlsx/.xlsm planning/scheduling workbook",
    )
    parser.add_argument(
        "--excel-output-root",
        default=os.environ.get(
            "PIPELINE_EXCEL_OUTPUT_ROOT",
            str(DEFAULT_EXCEL_OUTPUT_ROOT),
        ),
        help="Root receiving Outputs/excel and Reports schedule indexes",
    )
    parser.add_argument(
        "--excel-cell-mode",
        choices=["formula", "cached"],
        default=os.environ.get("PIPELINE_EXCEL_CELL_MODE", "formula"),
        help="Excel schedule-engine formula/cached cell read mode",
    )
    parser.add_argument(
        "--excel-tables-only",
        action="store_true",
        default=_env_bool("PIPELINE_EXCEL_TABLES_ONLY", False),
        help="Export only defined Excel Tables, not tableless used ranges",
    )
    parser.add_argument(
        "--excel-schedule-as-of",
        default=os.environ.get("PIPELINE_EXCEL_SCHEDULE_AS_OF"),
        help="Optional deterministic schedule dashboard as-of date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--excel-due-soon-days",
        type=int,
        default=int(os.environ.get("PIPELINE_EXCEL_DUE_SOON_DAYS", "14")),
        help="Yellow planning due-soon horizon in calendar days",
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


def run_excel_schedule_engine(
    excel_input: Path,
    excel_output_root: Path,
    cell_mode: str = "formula",
    tables_only: bool = False,
    schedule_as_of: str | None = None,
    due_soon_days: int = 14,
) -> Path | None:
    """Run the governed Excel schedule engine and return its manifest on PASS."""
    print("Phase 3: governed Excel schedule/data table engine")
    command = [
        sys.executable,
        str(EXCEL_ENGINE),
        str(excel_input),
        "--output-root",
        str(excel_output_root),
        "--cell-mode",
        cell_mode,
    ]
    if tables_only:
        command.append("--tables-only")
    if schedule_as_of:
        command.extend(["--schedule-as-of", schedule_as_of])
    command.extend(["--schedule-due-soon-days", str(due_soon_days)])

    result = subprocess.run(
        command,
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

    manifest_path = excel_output_root / "Outputs" / "excel" / "table_manifest.json"
    if not manifest_path.exists():
        print(f"Excel table manifest missing: {manifest_path}", file=sys.stderr)
        return None

    try:
        manifest = _load_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Cannot read Excel table manifest: {exc}", file=sys.stderr)
        return None

    summary = manifest.get("summary", {})
    authority = manifest.get("authority", {})
    if summary.get("errors", 0) != 0:
        print("Excel table manifest reports export errors", file=sys.stderr)
        return None
    if authority.get("authority_transfer") is not False:
        print("Excel table manifest authority guardrail failed", file=sys.stderr)
        return None

    schedule_manifest_path = (
        excel_output_root / "Outputs" / "excel" / "schedule" / "schedule_manifest.json"
    )
    if not schedule_manifest_path.exists():
        print(f"Schedule projection manifest missing: {schedule_manifest_path}", file=sys.stderr)
        return None
    try:
        schedule_manifest = _load_json(schedule_manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Cannot read schedule projection manifest: {exc}", file=sys.stderr)
        return None
    schedule_authority = schedule_manifest.get("authority", {})
    schedule_summary = schedule_manifest.get("summary", {})
    if schedule_authority.get("authority_transfer") is not False:
        print("Schedule projection authority guardrail failed", file=sys.stderr)
        return None
    if schedule_summary.get("process_status") != "PASS":
        print("Schedule projection process status is not PASS", file=sys.stderr)
        return None
    return manifest_path


def _receipt_path(path: Path, output_dir: Path) -> dict[str, str]:
    resolved = path.resolve()
    roots = (("output_dir", output_dir.resolve()), ("repo_root", REPO_ROOT.resolve()))
    for label, root in roots:
        try:
            return {"path": str(resolved.relative_to(root)), "path_base": label}
        except ValueError:
            continue
    return {"path": str(resolved), "path_base": "absolute"}


def write_pipeline_receipt(
    output_dir: Path,
    recursive_receipt_path: Path,
    excel_manifest_path: Path | None = None,
    excel_requested: bool = False,
) -> Path | None:
    """Bind bounded phase receipts through hashes without creating source authority."""
    summary_path = output_dir / "processing_summary.json"
    if not summary_path.exists() or not recursive_receipt_path.exists():
        print("Cannot write pipeline receipt: required phase receipt missing", file=sys.stderr)
        return None

    try:
        summary = _load_json(summary_path)
        recursive = _load_json(recursive_receipt_path)
        excel_manifest = _load_json(excel_manifest_path) if excel_manifest_path else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Cannot read phase receipt: {exc}", file=sys.stderr)
        return None

    metadata_ok = summary.get("failed", 0) == 0
    recursive_status = str(recursive.get("status", ""))
    recursive_ok = recursive_status.startswith("PASS")
    generated_at = recursive.get("generated_at")

    phases: dict[str, Any] = {
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
    }

    excel_ok = True
    if excel_requested:
        if excel_manifest_path is None or excel_manifest is None:
            excel_ok = False
            phases["excel_schedule"] = {"status": "FAIL", "requested": True}
        else:
            excel_summary = excel_manifest.get("summary", {})
            excel_authority = excel_manifest.get("authority", {})
            excel_ok = (
                excel_summary.get("errors", 0) == 0
                and excel_authority.get("authority_transfer") is False
            )
            schedule_manifest_path = (
                excel_manifest_path.parent / "schedule" / "schedule_manifest.json"
            )
            schedule_projection = None
            if schedule_manifest_path.exists():
                schedule_manifest = _load_json(schedule_manifest_path)
                schedule_summary = schedule_manifest.get("summary", {})
                schedule_authority = schedule_manifest.get("authority", {})
                schedule_projection = {
                    "status": schedule_summary.get("process_status"),
                    **_receipt_path(schedule_manifest_path, output_dir),
                    "sha256": sha256_file(schedule_manifest_path),
                    "activities": schedule_summary.get("activities", 0),
                    "red": schedule_summary.get("red", 0),
                    "yellow": schedule_summary.get("yellow", 0),
                    "green": schedule_summary.get("green", 0),
                    "validation_pass_rate_pct": schedule_summary.get(
                        "validation_pass_rate_pct", 100.0
                    ),
                    "authority_transfer": schedule_authority.get("authority_transfer"),
                }
                excel_ok = excel_ok and (
                    schedule_projection["status"] == "PASS"
                    and schedule_projection["authority_transfer"] is False
                )
            else:
                excel_ok = False

            phases["excel_schedule"] = {
                "status": "PASS" if excel_ok else "FAIL",
                "requested": True,
                **_receipt_path(excel_manifest_path, output_dir),
                "sha256": sha256_file(excel_manifest_path),
                "tables_exported": excel_summary.get("tables_exported", 0),
                "schedule_candidates": excel_summary.get("schedule_candidates", 0),
                "errors": excel_summary.get("errors", 0),
                "authority_transfer": excel_authority.get("authority_transfer"),
                "schedule_projection": schedule_projection,
            }
    else:
        phases["excel_schedule"] = {"status": "NOT_REQUESTED", "requested": False}

    overall_ok = metadata_ok and recursive_ok and excel_ok
    payload = {
        "schema": "pipeline_automation_hub.pipeline_run_receipt.v3",
        "generated_at": generated_at,
        "authority": AUTHORITY,
        "status": "PASS" if overall_ok else "FAIL",
        "phases": phases,
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
    excel_input_raw = getattr(args, "excel_input", None)
    excel_requested = bool(excel_input_raw)
    excel_input = Path(excel_input_raw) if excel_requested else None
    excel_output_root = Path(getattr(args, "excel_output_root", str(DEFAULT_EXCEL_OUTPUT_ROOT)))
    excel_cell_mode = getattr(args, "excel_cell_mode", "formula")
    excel_tables_only = bool(getattr(args, "excel_tables_only", False))
    excel_schedule_as_of = getattr(args, "excel_schedule_as_of", None)
    excel_due_soon_days = int(getattr(args, "excel_due_soon_days", 14))

    print("Pipeline Automation Hub - bounded MAIN pipeline")
    print(f"input={input_dir.resolve()}")
    print(f"output={output_dir.resolve()}")
    if excel_requested and excel_input is not None:
        print(f"excel_input={excel_input.resolve()}")
        print(f"excel_output_root={excel_output_root.resolve()}")

    if not run_ppt_processing(input_dir, output_dir):
        return 2
    if not summarize(output_dir):
        return 3

    recursive_receipt = run_recursive_build(output_dir)
    if recursive_receipt is None:
        return 4

    excel_manifest = None
    if excel_requested and excel_input is not None:
        excel_manifest = run_excel_schedule_engine(
            excel_input,
            excel_output_root,
            cell_mode=excel_cell_mode,
            tables_only=excel_tables_only,
            schedule_as_of=excel_schedule_as_of,
            due_soon_days=excel_due_soon_days,
        )
        if excel_manifest is None:
            return 5

    pipeline_receipt = write_pipeline_receipt(
        output_dir,
        recursive_receipt,
        excel_manifest_path=excel_manifest,
        excel_requested=excel_requested,
    )
    if pipeline_receipt is None:
        return 6

    print(
        json.dumps(
            {
                "status": "PASS",
                "authority": AUTHORITY,
                "excel_requested": excel_requested,
                "pipeline_receipt": str(pipeline_receipt.resolve()),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
